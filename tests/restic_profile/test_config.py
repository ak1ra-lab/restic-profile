"""Tests for restic_profile.config — load_config()."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from restic_profile.config import (
    HooksConfig,
    Profile,
    ResticProfileConfig,
    RetentionPolicy,
    load_config,
)

# load_config — file not found


def test_load_config_raises_file_not_found_for_missing_file(tmp_path: Path) -> None:
    """load_config() raises FileNotFoundError with the path and 'not found' in the message."""
    missing = tmp_path / "nonexistent.toml"

    with pytest.raises(FileNotFoundError, match="not found") as exc_info:
        load_config(missing)

    assert str(missing) in str(exc_info.value)


# load_config — happy path


def test_load_config_returns_restic_profile_config(config_toml_file: Path) -> None:
    """load_config() returns a ResticProfileConfig for a valid TOML file."""
    result = load_config(config_toml_file)

    assert isinstance(result, ResticProfileConfig)


def test_load_config_returns_profiles_dict(config_toml_file: Path) -> None:
    """load_config() populates the profiles dict from the TOML file."""
    result = load_config(config_toml_file)

    assert isinstance(result.profiles, dict)
    assert "myapp" in result.profiles
    assert "server_prune" in result.profiles


def test_load_config_profile_fields_match_toml(config_toml_file: Path) -> None:
    """load_config() correctly parses profile fields from TOML."""
    result = load_config(config_toml_file)
    myapp = result.profiles["myapp"]

    assert myapp.repository == "rest:https://backup.example.com/"
    assert myapp.password == "secret"
    assert "/home/alice/myapp" in myapp.sources


def test_load_config_runtime_model_contains_profiles_only(
    config_toml_file: Path,
) -> None:
    """load_config() keeps global defaults as input-only and exposes profiles at runtime."""
    result = load_config(config_toml_file)

    assert set(result.model_dump()) == {"profiles"}


def test_load_config_empty_profiles_section(tmp_path: Path) -> None:
    """load_config() handles a TOML file with no [profiles] section."""
    toml_file = tmp_path / "empty-profiles.toml"
    toml_file.write_text('[global]\nretry_lock = ""\n', encoding="utf-8")

    result = load_config(toml_file)

    assert result.profiles == {}


def test_load_config_missing_global_section(tmp_path: Path) -> None:
    """load_config() handles a TOML file with no [global] section."""
    toml_file = tmp_path / "no-global.toml"
    toml_file.write_text(
        '[profiles.demo]\nrepository = "rest:https://example.com/"\npassword = "pw"\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert "demo" in result.profiles


# Profile defaults — tag


def test_profile_tag_defaults_to_name_when_empty(tmp_path: Path) -> None:
    """When 'tag' is an empty string in the TOML, the profile's tag is set to its name."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.server]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        'tag = ""\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["server"].tag == "server"


def test_profile_tag_preserved_when_explicitly_set(tmp_path: Path) -> None:
    """When 'tag' is set in TOML, its value is kept as-is."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.myapp]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        'tag = "custom-tag"\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].tag == "custom-tag"


def test_profile_forget_current_host_defaults_to_false(tmp_path: Path) -> None:
    """forget_current_host defaults to False when omitted from TOML."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.myapp]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].forget_current_host is False


def test_profile_forget_current_host_parsed_from_toml(tmp_path: Path) -> None:
    """forget_current_host is parsed from TOML when explicitly set."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.myapp]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "forget_current_host = true\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].forget_current_host is True


# Profile defaults — retry_lock inheritance


def test_profile_retry_lock_inherits_from_global(tmp_path: Path) -> None:
    """A profile with empty retry_lock inherits the global retry_lock value."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        '[global]\nretry_lock = "5m"\n\n'
        "[profiles.myapp]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].retry_lock == "5m"


def test_profile_retry_lock_overrides_global_when_set(tmp_path: Path) -> None:
    """A profile with its own non-empty retry_lock does not inherit from global."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        '[global]\nretry_lock = "5m"\n\n'
        "[profiles.myapp]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        'retry_lock = "2m"\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].retry_lock == "2m"


def test_profile_no_cache_inherits_from_global(tmp_path: Path) -> None:
    """A profile without no_cache inherits the global no_cache value."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[global]\nno_cache = true\n\n"
        "[profiles.myapp]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].no_cache is True


def test_profile_no_cache_overrides_global_when_set(tmp_path: Path) -> None:
    """A profile can explicitly disable no_cache even when the global setting is true."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[global]\nno_cache = true\n\n"
        "[profiles.myapp]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "no_cache = false\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].no_cache is False


def test_profile_restic_binary_inherits_from_global(tmp_path: Path) -> None:
    """A profile without restic_binary inherits the global executable setting."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[global]\n"
        'restic_binary = "/usr/local/bin/restic"\n\n'
        "[profiles.myapp]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].restic_binary == "/usr/local/bin/restic"


def test_profile_restic_binary_preserves_explicit_empty_override(
    tmp_path: Path,
) -> None:
    """A profile can explicitly set restic_binary to empty and fall back to PATH."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[global]\n"
        'restic_binary = "/usr/local/bin/restic"\n\n'
        "[profiles.myapp]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        'restic_binary = ""\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].restic_binary == ""


def test_profile_one_file_system_defaults_to_false(tmp_path: Path) -> None:
    """one_file_system defaults to False when omitted from TOML."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.myapp]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].one_file_system is False


def test_profile_one_file_system_parsed_from_toml(tmp_path: Path) -> None:
    """one_file_system is parsed from TOML when explicitly set."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.myapp]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "one_file_system = true\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].one_file_system is True


def test_profile_keep_values_default_when_absent(tmp_path: Path) -> None:
    """keep_* fields use the Profile dataclass defaults when not in TOML."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.myapp]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)
    p = result.profiles["myapp"]

    assert p.keep_hourly == 6
    assert p.keep_daily == 7
    assert p.keep_weekly == 4
    assert p.keep_monthly == 3
    assert p.keep_last == 0
    assert p.keep_yearly == 0


# Profile.is_backup / is_retention_only properties


def test_profile_is_backup_when_sources_non_empty(backup_profile: Profile) -> None:
    """Profile.is_backup is True and is_retention_only is False when sources is non-empty."""
    assert backup_profile.is_backup is True
    assert backup_profile.is_retention_only is False


def test_profile_is_retention_only_when_sources_empty(prune_profile: Profile) -> None:
    """Profile.is_retention_only is True and is_backup is False when sources is empty."""
    assert prune_profile.is_retention_only is True
    assert prune_profile.is_backup is False


def test_profile_retention_property(backup_profile: Profile) -> None:
    """Profile.retention returns a RetentionPolicy reflecting the keep_* fields."""
    rp = backup_profile.retention

    assert isinstance(rp, RetentionPolicy)
    assert rp.keep_daily == backup_profile.keep_daily
    assert rp.keep_weekly == backup_profile.keep_weekly


# Profile validation — invalid profiles raise ValidationError


def test_profile_empty_repository_raises_validation_error() -> None:
    """Profile raises ValidationError (with profile name) when repository is empty."""
    with pytest.raises(ValidationError, match="repository is required") as exc_info:
        Profile(name="badrepo", repository="", password="secret")

    assert "badrepo" in str(exc_info.value)


def test_profile_empty_password_raises_validation_error() -> None:
    """Profile raises ValidationError when password is empty."""
    with pytest.raises(ValidationError, match="password is required"):
        Profile(name="nopw", repository="rest:https://example.com/", password="")


def test_retention_only_profile_with_no_retention_raises_validation_error() -> None:
    """Profile raises ValidationError for retention-only profile with all keep_* == 0."""
    with pytest.raises(ValidationError, match="retention"):
        Profile(
            name="badprune",
            repository="rest:https://example.com/",
            password="secret",
            sources=[],
            keep_last=0,
            keep_hourly=0,
            keep_daily=0,
            keep_weekly=0,
            keep_monthly=0,
            keep_yearly=0,
        )


def test_retention_only_profile_with_single_keep_is_valid() -> None:
    """A retention-only profile with at least one keep_* > 0 passes validation."""
    profile = Profile(
        name="okprune",
        repository="rest:https://example.com/",
        password="secret",
        sources=[],
        keep_last=0,
        keep_hourly=0,
        keep_daily=7,
        keep_weekly=0,
        keep_monthly=0,
        keep_yearly=0,
    )
    assert profile.is_retention_only is True


def test_backup_profile_with_all_keep_zero_is_valid() -> None:
    """A backup profile with all keep_* == 0 does not trigger the retention error."""
    profile = Profile(
        name="backuponly",
        repository="rest:https://example.com/",
        password="secret",
        sources=["/data"],
        keep_last=0,
        keep_hourly=0,
        keep_daily=0,
        keep_weekly=0,
        keep_monthly=0,
        keep_yearly=0,
    )
    assert profile.is_backup is True


def test_empty_profiles_config_is_valid() -> None:
    """ResticProfileConfig with no profiles is valid."""
    cfg = ResticProfileConfig(retry_lock="", profiles={})

    assert cfg.profiles == {}


# Profile — S3-compatible backend fields


def test_profile_aws_fields_default_to_empty() -> None:
    """S3 credential fields default to empty strings."""
    profile = Profile(
        name="s3_default",
        repository="s3:s3.amazonaws.com/my-bucket",
        password="secret",
        sources=["/data"],
    )

    assert profile.aws_default_region == ""
    assert profile.aws_access_key_id == ""
    assert profile.aws_secret_access_key == ""


def test_profile_aws_fields_are_stored_when_set(tmp_path: Path) -> None:
    """load_config() correctly parses S3 credential fields from TOML."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.s3_backup]\n"
        'repository = "s3:s3.amazonaws.com/my-bucket"\n'
        'password = "secret"\n'
        'sources = ["/data"]\n'
        'aws_default_region = "us-east-1"\n'
        'aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"\n'
        'aws_secret_access_key = "wJalrXUtnFEMI"\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)
    p = result.profiles["s3_backup"]

    assert p.aws_default_region == "us-east-1"
    assert p.aws_access_key_id == "AKIAIOSFODNN7EXAMPLE"
    assert p.aws_secret_access_key == "wJalrXUtnFEMI"


def test_profile_s3_repository_is_valid(tmp_path: Path) -> None:
    """A profile with an s3: repository URL is accepted."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.s3_backup]\n"
        'repository = "s3:s3.amazonaws.com/my-bucket"\n'
        'password = "secret"\n'
        'sources = ["/data"]\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)
    p = result.profiles["s3_backup"]

    assert p.repository == "s3:s3.amazonaws.com/my-bucket"
    assert p.is_backup is True


# Profile — GCS / SFTP / rclone backend fields


def test_profile_gcs_fields_default_to_empty() -> None:
    """GCS credential fields default to empty strings."""
    profile = Profile(
        name="gcs_default",
        repository="gs:my-bucket:/",
        password="secret",
        sources=["/data"],
    )

    assert profile.google_project_id == ""
    assert profile.google_application_credentials == ""
    assert profile.google_access_token == ""


def test_profile_gcs_fields_are_stored_when_set(tmp_path: Path) -> None:
    """load_config() correctly parses GCS credential fields from TOML."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.gcs_backup]\n"
        'repository = "gs:my-bucket:/"\n'
        'password = "secret"\n'
        'sources = ["/data"]\n'
        'google_project_id = "my-project-123"\n'
        'google_application_credentials = "/etc/gcs/key.json"\n'
        'google_access_token = ""\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)
    p = result.profiles["gcs_backup"]

    assert p.google_project_id == "my-project-123"
    assert p.google_application_credentials == "/etc/gcs/key.json"
    assert p.google_access_token == ""


def test_profile_gcs_access_token_stored_when_set(tmp_path: Path) -> None:
    """load_config() stores google_access_token when provided."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.gcs_token]\n"
        'repository = "gs:my-bucket:/"\n'
        'password = "secret"\n'
        'sources = ["/data"]\n'
        'google_project_id = "my-project-123"\n'
        'google_access_token = "ya29.some-token"\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)
    p = result.profiles["gcs_token"]

    assert p.google_project_id == "my-project-123"
    assert p.google_access_token == "ya29.some-token"
    assert p.google_application_credentials == ""


def test_profile_gcs_adc_environment_no_credentials_required(tmp_path: Path) -> None:
    """A gs: profile with only google_project_id set is valid (ADC environment)."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.gcs_adc]\n"
        'repository = "gs:my-bucket:/"\n'
        'password = "secret"\n'
        'sources = ["/data"]\n'
        'google_project_id = "my-project-123"\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)
    p = result.profiles["gcs_adc"]

    assert p.google_project_id == "my-project-123"
    assert p.google_application_credentials == ""
    assert p.google_access_token == ""


def test_profile_sftp_repository_is_valid(tmp_path: Path) -> None:
    """A profile with an sftp: repository URL is accepted without extra credential fields."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.sftp_backup]\n"
        'repository = "sftp:user@backup.example.com:/srv/restic-repo"\n'
        'password = "secret"\n'
        'sources = ["/home/user"]\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)
    p = result.profiles["sftp_backup"]

    assert p.repository == "sftp:user@backup.example.com:/srv/restic-repo"
    assert p.is_backup is True


def test_profile_rclone_repository_is_valid(tmp_path: Path) -> None:
    """A profile with a rclone: repository URL is accepted without extra credential fields."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.rclone_backup]\n"
        'repository = "rclone:b2prod:yggdrasil/backups"\n'
        'password = "secret"\n'
        'sources = ["/data"]\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)
    p = result.profiles["rclone_backup"]

    assert p.repository == "rclone:b2prod:yggdrasil/backups"
    assert p.is_backup is True


# HooksConfig — defaults


def test_hooks_config_defaults_to_empty_lists_and_sh_shell() -> None:
    """HooksConfig defaults to empty hook lists and shell='/bin/sh'."""
    hooks = HooksConfig()

    assert hooks.shell == "/bin/sh"
    assert hooks.prevalidate == []
    assert hooks.before == []
    assert hooks.after == []
    assert hooks.failure == []
    assert hooks.success == []


def test_profile_hooks_defaults_to_empty_hooks_config(backup_profile: Profile) -> None:
    """Profile.hooks defaults to an empty HooksConfig with no hook commands."""
    hooks = backup_profile.hooks

    assert isinstance(hooks, HooksConfig)
    assert hooks.prevalidate == []
    assert hooks.before == []
    assert hooks.after == []
    assert hooks.failure == []
    assert hooks.success == []


# HooksConfig — TOML parsing


def test_load_config_parses_hooks_from_toml(tmp_path: Path) -> None:
    """load_config() parses [profiles.*.hooks] into a HooksConfig instance."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.app]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        'sources = ["/data"]\n'
        "\n"
        "[profiles.app.hooks]\n"
        'shell = "/bin/bash"\n'
        'prevalidate = ["mount /mnt/data"]\n'
        'before = ["echo before", "service stop myapp"]\n'
        'after = ["service start myapp"]\n'
        'failure = ["echo backup failed"]\n'
        'success = ["echo backup done"]\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)
    hooks = result.profiles["app"].hooks

    assert isinstance(hooks, HooksConfig)
    assert hooks.shell == "/bin/bash"
    assert hooks.prevalidate == ["mount /mnt/data"]
    assert hooks.before == ["echo before", "service stop myapp"]
    assert hooks.after == ["service start myapp"]
    assert hooks.failure == ["echo backup failed"]
    assert hooks.success == ["echo backup done"]


def test_load_config_hooks_shell_defaults_to_sh_when_absent(tmp_path: Path) -> None:
    """HooksConfig.shell defaults to '/bin/sh' when not set in TOML."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.app]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        'sources = ["/data"]\n'
        "\n"
        "[profiles.app.hooks]\n"
        'before = ["echo hi"]\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["app"].hooks.shell == "/bin/sh"


def test_load_config_hooks_absent_gives_empty_hooks_config(tmp_path: Path) -> None:
    """A profile with no [hooks] section gets a default empty HooksConfig."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[profiles.app]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        'sources = ["/data"]\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)
    hooks = result.profiles["app"].hooks

    assert isinstance(hooks, HooksConfig)
    assert hooks.before == []
    assert hooks.success == []


def test_hooks_config_supports_multiline_script() -> None:
    """A hook command can be a multi-line shell script string."""
    script = "set -e\necho starting\nservice stop myapp"
    hooks = HooksConfig(before=[script])

    assert hooks.before[0] == script
