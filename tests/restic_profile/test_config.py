"""Tests for restic_profile.config — load_config()."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from restic_profile.config import (
    BackupConfig,
    HooksConfig,
    Profile,
    Repository,
    ResticProfileConfig,
    RetentionConfig,
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

    assert myapp.resolved_repository is not None
    assert myapp.resolved_repository.repository == "rest:https://backup.example.com/"
    assert myapp.resolved_repository.password == "secret"
    assert myapp.backup is not None
    assert "/home/alice/myapp" in myapp.backup.sources


def test_load_config_runtime_model_contains_profiles_only(
    config_toml_file: Path,
) -> None:
    """load_config() keeps global defaults as input-only and exposes profiles/repositories at runtime."""
    result = load_config(config_toml_file)

    assert set(result.model_dump().keys()) == {
        "profiles",
        "repositories",
        "notify",
        "template_dir",
    }


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
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "pw"\n'
        "[profiles.demo]\n"
        'repository_ref = "r1"\n'
        "[profiles.demo.backup]\n"
        'sources = ["/data"]\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert "demo" in result.profiles


# Profile defaults — tag


def test_profile_tag_defaults_to_name_when_empty(tmp_path: Path) -> None:
    """When 'tag' is an empty string in the TOML, the profile's tag is set to its name."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.server]\n"
        'repository_ref = "r1"\n'
        'tag = ""\n'
        "[profiles.server.backup]\n"
        'sources = ["/data"]\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["server"].tag == "server"


def test_profile_tag_preserved_when_explicitly_set(tmp_path: Path) -> None:
    """When 'tag' is set in TOML, its value is kept as-is."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        'tag = "custom-tag"\n'
        "[profiles.myapp.backup]\n"
        'sources = ["/data"]\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].tag == "custom-tag"


def test_profile_forget_current_host_defaults_to_true(tmp_path: Path) -> None:
    """forget_current_host defaults to True when omitted from TOML."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        "[profiles.myapp.retention]\n"
        "keep_daily = 7\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].retention.forget_current_host is True


def test_profile_forget_current_host_parsed_from_toml(tmp_path: Path) -> None:
    """forget_current_host is parsed from TOML when explicitly overridden."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        "[profiles.myapp.retention]\n"
        "keep_daily = 7\n"
        "forget_current_host = false\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].retention.forget_current_host is False


# Profile defaults — retry_lock inheritance


def test_profile_retry_lock_inherits_from_global(tmp_path: Path) -> None:
    """A profile with empty retry_lock inherits the global retry_lock value."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        '[global]\nretry_lock = "5m"\n\n'
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        "[profiles.myapp.retention]\n"
        "keep_daily = 7\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].retry_lock == "5m"


def test_profile_retry_lock_overrides_global_when_set(tmp_path: Path) -> None:
    """A profile with its own non-empty retry_lock does not inherit from global."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        '[global]\nretry_lock = "5m"\n\n'
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        'retry_lock = "2m"\n'
        "[profiles.myapp.retention]\n"
        "keep_daily = 7\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].retry_lock == "2m"


def test_profile_no_cache_inherits_from_global(tmp_path: Path) -> None:
    """A profile without no_cache inherits the global no_cache value."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[global]\nno_cache = true\n\n"
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        "[profiles.myapp.retention]\n"
        "keep_daily = 7\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].no_cache is True


def test_profile_no_cache_overrides_global_when_set(tmp_path: Path) -> None:
    """A profile can explicitly disable no_cache even when the global setting is true."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[global]\nno_cache = true\n\n"
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        "no_cache = false\n"
        "[profiles.myapp.retention]\n"
        "keep_daily = 7\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].no_cache is False


# Profile defaults — unlock inheritance


def test_profile_unlock_inherits_from_global(tmp_path: Path) -> None:
    """A profile without unlock inherits the global unlock value."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[global]\nunlock = true\n\n"
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        "[profiles.myapp.retention]\n"
        "keep_daily = 7\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].unlock is True


def test_profile_unlock_overrides_global_when_set(tmp_path: Path) -> None:
    """A profile can explicitly disable unlock even when the global setting is true."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[global]\nunlock = true\n\n"
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        "unlock = false\n"
        "[profiles.myapp.retention]\n"
        "keep_daily = 7\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].unlock is False


def test_profile_unlock_defaults_to_false(tmp_path: Path) -> None:
    """unlock defaults to False when not specified in global or profile."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        "[profiles.myapp.retention]\n"
        "keep_daily = 7\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].unlock is False


def test_profile_restic_binary_inherits_from_global(tmp_path: Path) -> None:
    """A profile without restic_binary inherits the global executable setting."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[global]\n"
        'restic_binary = "/usr/local/bin/restic"\n\n'
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        "[profiles.myapp.retention]\n"
        "keep_daily = 7\n",
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
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        'restic_binary = ""\n'
        "[profiles.myapp.retention]\n"
        "keep_daily = 7\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].restic_binary == ""


def test_profile_one_file_system_defaults_to_false(tmp_path: Path) -> None:
    """one_file_system defaults to False when omitted from TOML."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        "[profiles.myapp.backup]\n"
        'sources = ["/data"]\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].backup.one_file_system is False


def test_profile_one_file_system_parsed_from_toml(tmp_path: Path) -> None:
    """one_file_system is parsed from TOML when explicitly set."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        "[profiles.myapp.backup]\n"
        'sources = ["/data"]\n'
        "one_file_system = true\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].backup.one_file_system is True


def test_profile_on_calendar_defaults_to_empty(tmp_path: Path) -> None:
    """on_calendar defaults to an empty string when omitted from TOML."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        "[profiles.myapp.retention]\n"
        "keep_daily = 7\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)

    assert result.profiles["myapp"].on_calendar == ""


def test_profile_schedule_fields_are_parsed_from_profile_root(tmp_path: Path) -> None:
    """Profile-level schedule fields are parsed from the profile root."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        'on_calendar = "daily"\n'
        'randomized_delay_sec = "30m"\n'
        "[profiles.myapp.backup]\n"
        'sources = ["/data"]\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)
    profile = result.profiles["myapp"]

    assert profile.on_calendar == "daily"
    assert profile.randomized_delay_sec == "30m"


def test_profile_keep_values_default_when_absent(tmp_path: Path) -> None:
    """keep_* fields use the RetentionConfig dataclass defaults when not in TOML."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.myapp]\n"
        'repository_ref = "r1"\n'
        "[profiles.myapp.retention]\n"
        "keep_daily = 7\n",
        encoding="utf-8",
    )

    result = load_config(toml_file)
    ret = result.profiles["myapp"].retention

    assert ret.keep_hourly == 0
    assert ret.keep_daily == 7
    assert ret.keep_weekly == 0
    assert ret.keep_monthly == 0
    assert ret.keep_last == 0
    assert ret.keep_yearly == 0


# Profile.is_backup / is_retention_only properties


def test_profile_is_backup_when_sources_non_empty(backup_profile: Profile) -> None:
    """Profile.is_backup is True and is_retention_only is False when sources is non-empty."""
    assert backup_profile.is_backup is True
    assert backup_profile.is_retention_only is False


def test_profile_is_retention_only_when_sources_empty(prune_profile: Profile) -> None:
    """Profile.is_retention_only is True and is_backup is False when sources is empty."""
    assert prune_profile.is_retention_only is True
    assert prune_profile.is_backup is False


def test_profile_runs_retention_when_retention_is_configured(
    prune_profile: Profile,
) -> None:
    """Profile.runs_retention is True when a retention block exists."""
    assert prune_profile.runs_retention is True


def test_profile_runs_retention_when_backup_and_retention_exist(
    backup_profile: Profile,
) -> None:
    """Mixed backup profiles still report that they run retention."""
    assert backup_profile.runs_retention is True


# Profile validation — invalid profiles raise ValidationError


def test_profile_empty_repository_raises_validation_error() -> None:
    """Repository model raises ValidationError when repository is empty."""
    with pytest.raises(ValidationError, match="repository"):
        Repository(name="badrepo", repository="", password="secret")


def test_profile_empty_password_raises_validation_error() -> None:
    """Repository model raises ValidationError when password is empty."""
    with pytest.raises(ValidationError, match="password"):
        Repository(name="nopw", repository="rest:https://example.com/", password="")


def test_retention_only_profile_with_no_retention_action_raises_validation_error() -> (
    None
):
    """Profile raises ValidationError for retention-only profile with no keep_* and prune=false."""
    repo = Repository(name="r1", repository="rest:https://example.com/", password="pw")
    with pytest.raises(ValidationError, match="retention"):
        Profile(
            name="badprune",
            repository_ref="r1",
            resolved_repository=repo,
            retention=RetentionConfig(
                keep_last=0,
                keep_hourly=0,
                keep_daily=0,
                keep_weekly=0,
                keep_monthly=0,
                keep_yearly=0,
                prune=False,
            ),
        )


def test_retention_only_profile_with_single_keep_is_valid() -> None:
    """A retention-only profile with at least one keep_* > 0 passes validation."""
    repo = Repository(name="r1", repository="rest:https://example.com/", password="pw")
    profile = Profile(
        name="okprune",
        repository_ref="r1",
        resolved_repository=repo,
        retention=RetentionConfig(
            keep_last=0,
            keep_hourly=0,
            keep_daily=7,
            keep_weekly=0,
            keep_monthly=0,
            keep_yearly=0,
        ),
    )
    assert profile.is_retention_only is True


def test_retention_only_profile_with_prune_only_is_valid() -> None:
    """A retention-only profile with prune=true and no keep_* policy passes validation."""
    repo = Repository(name="r1", repository="rest:https://example.com/", password="pw")
    profile = Profile(
        name="pruneonly",
        repository_ref="r1",
        resolved_repository=repo,
        retention=RetentionConfig(
            keep_last=0,
            keep_hourly=0,
            keep_daily=0,
            keep_weekly=0,
            keep_monthly=0,
            keep_yearly=0,
            prune=True,
        ),
    )
    assert profile.is_retention_only is True


def test_backup_profile_with_all_keep_zero_is_valid() -> None:
    """A backup profile with all keep_* == 0 does not trigger the retention error."""
    repo = Repository(name="r1", repository="rest:https://example.com/", password="pw")
    profile = Profile(
        name="backuponly",
        repository_ref="r1",
        resolved_repository=repo,
        backup=BackupConfig(sources=["/data"]),
    )
    assert profile.is_backup is True


def test_empty_profiles_config_is_valid() -> None:
    """ResticProfileConfig with no profiles is valid."""
    cfg = ResticProfileConfig(profiles={})

    assert cfg.profiles == {}


# Profile — S3-compatible backend fields


def test_profile_aws_fields_default_to_empty() -> None:
    """S3 credential fields default to empty strings."""
    repo = Repository(name="r1")
    assert repo.aws_default_region == ""
    assert repo.aws_access_key_id == ""
    assert repo.aws_secret_access_key == ""


def test_profile_aws_fields_are_stored_when_set(tmp_path: Path) -> None:
    """load_config() correctly parses S3 credential fields from TOML."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[repositories.r1]\n"
        'repository = "s3:s3.amazonaws.com/my-bucket"\n'
        'password = "secret"\n'
        'aws_default_region = "us-east-1"\n'
        'aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"\n'
        'aws_secret_access_key = "wJalrXUtnFEMI"\n'
        "[profiles.s3_backup]\n"
        'repository_ref = "r1"\n'
        "[profiles.s3_backup.backup]\n"
        'sources = ["/data"]\n',
        encoding="utf-8",
    )

    result = load_config(toml_file)
    repo = result.repositories["r1"]

    assert repo.aws_default_region == "us-east-1"
    assert repo.aws_access_key_id == "AKIAIOSFODNN7EXAMPLE"
    assert repo.aws_secret_access_key == "wJalrXUtnFEMI"


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
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.app]\n"
        'repository_ref = "r1"\n'
        "[profiles.app.backup]\n"
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
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.app]\n"
        'repository_ref = "r1"\n'
        "[profiles.app.backup]\n"
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
        "[repositories.r1]\n"
        'repository = "rest:https://example.com/"\n'
        'password = "secret"\n'
        "[profiles.app]\n"
        'repository_ref = "r1"\n'
        "[profiles.app.backup]\n"
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


def test_load_config_with_notify_section(tmp_path: Path) -> None:
    """load_config() parses [notify.*] entries and resolves notify_ref."""
    from restic_profile.config import TelegramNotifyConfig

    toml = """\
[repositories.r1]
repository = "rest:https://backup.example.com/"
password = "secret"

[notify.tg]
type = "telegram"
token = "123:abc"
chat_id = 123456

[profiles.myapp]
repository_ref = "r1"
notify_ref = "tg"
notify_top_files_limit = 5
[profiles.myapp.backup]
sources = ["/data"]
"""
    toml_file = tmp_path / "notify.toml"
    toml_file.write_text(toml, encoding="utf-8")

    result = load_config(toml_file)

    assert "tg" in result.notify
    assert isinstance(result.notify["tg"], TelegramNotifyConfig)
    assert result.notify["tg"].token == "123:abc"
    assert result.notify["tg"].chat_id == 123456

    profile = result.profiles["myapp"]
    assert profile.notify_ref == "tg"
    assert profile.notify_top_files_limit == 5
    assert profile.resolved_notifier is not None
    assert isinstance(profile.resolved_notifier, TelegramNotifyConfig)


def test_load_config_notify_ref_defaults_to_zero(tmp_path: Path) -> None:
    """notify_ref is empty by default, resolved_notifier stays None."""
    toml = """\
[repositories.r1]
repository = "rest:https://backup.example.com/"
password = "secret"

[profiles.myapp]
repository_ref = "r1"
[profiles.myapp.backup]
sources = ["/data"]
"""
    toml_file = tmp_path / "no-notify.toml"
    toml_file.write_text(toml, encoding="utf-8")

    result = load_config(toml_file)

    profile = result.profiles["myapp"]
    assert profile.notify_ref == ""
    assert profile.notify_top_files_limit == 3
    assert profile.resolved_notifier is None


def test_load_config_notify_ref_missing_target_raises(tmp_path: Path) -> None:
    """notify_ref pointing to a missing notify entry raises ValueError."""
    toml = """\
[repositories.r1]
repository = "rest:https://backup.example.com/"
password = "secret"

[profiles.myapp]
repository_ref = "r1"
notify_ref = "nonexistent"
[profiles.myapp.backup]
sources = ["/data"]
"""
    toml_file = tmp_path / "bad-notify-ref.toml"
    toml_file.write_text(toml, encoding="utf-8")

    with pytest.raises(ValueError, match="notifier 'nonexistent' not found"):
        load_config(toml_file)


def test_load_config_notify_invalid_type_raises(tmp_path: Path) -> None:
    """An unknown notify type raises pydantic ValidationError."""
    toml = """\
[repositories.r1]
repository = "rest:https://backup.example.com/"
password = "secret"

[notify.bad]
type = "unknown_platform"

[profiles.myapp]
repository_ref = "r1"
[profiles.myapp.backup]
sources = ["/data"]
"""
    toml_file = tmp_path / "bad-type.toml"
    toml_file.write_text(toml, encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(toml_file)


def test_load_config_empty_notify_section(tmp_path: Path) -> None:
    """An empty [notify] table produces an empty dict."""
    toml = """\
[repositories.r1]
repository = "rest:https://backup.example.com/"
password = "secret"

[profiles.myapp]
repository_ref = "r1"
[profiles.myapp.backup]
sources = ["/data"]
"""
    toml_file = tmp_path / "no-notify.toml"
    toml_file.write_text(toml, encoding="utf-8")

    result = load_config(toml_file)
    assert result.notify == {}


def test_load_config_notify_multiple_channels(tmp_path: Path) -> None:
    """Multiple notify channels are parsed correctly."""
    toml = """\
[repositories.r1]
repository = "rest:https://backup.example.com/"
password = "secret"

[notify.tg]
type = "telegram"
token = "tg-token"
chat_id = -100

[notify.dd]
type = "dingtalk"
access_token = "dd-token"

[profiles.a]
repository_ref = "r1"
notify_ref = "dd"
[profiles.a.backup]
sources = ["/data"]

[profiles.b]
repository_ref = "r1"
notify_ref = "tg"
[profiles.b.backup]
sources = ["/data"]
"""
    toml_file = tmp_path / "multi.toml"
    toml_file.write_text(toml, encoding="utf-8")

    result = load_config(toml_file)
    assert len(result.notify) == 2
    assert "tg" in result.notify
    assert "dd" in result.notify

    assert result.profiles["a"].resolved_notifier is not None
    assert result.profiles["b"].resolved_notifier is not None


def test_load_config_telegram_chat_id_int(tmp_path: Path) -> None:
    """chat_id as an integer is accepted."""
    toml = """\
[repositories.r1]
repository = "rest:https://backup.example.com/"
password = "secret"

[notify.tg]
type = "telegram"
token = "tg-token"
chat_id = -1001234567890

[profiles.myapp]
repository_ref = "r1"
[profiles.myapp.backup]
sources = ["/data"]
"""
    toml_file = tmp_path / "int-chat-id.toml"
    toml_file.write_text(toml, encoding="utf-8")

    result = load_config(toml_file)
    assert result.notify["tg"].chat_id == -1001234567890


def test_repository_env_parsed_from_toml(tmp_path: Path) -> None:
    """Repository.env is parsed as a dict[str, str] from a nested TOML table."""
    toml = """\
[repositories.r1]
repository = "rest:https://backup.example.com/"
password = "secret"

[repositories.r1.env]
HTTP_PROXY = "http://proxy:7890"
HTTPS_PROXY = "http://proxy:7890"
RESTIC_COMPRESSION = "max"

[profiles.myapp]
repository_ref = "r1"
[profiles.myapp.backup]
sources = ["/data"]
"""
    toml_file = tmp_path / "repo-env.toml"
    toml_file.write_text(toml, encoding="utf-8")

    result = load_config(toml_file)
    repo = result.repositories["r1"]

    assert repo.env == {
        "HTTP_PROXY": "http://proxy:7890",
        "HTTPS_PROXY": "http://proxy:7890",
        "RESTIC_COMPRESSION": "max",
    }


def test_repository_env_defaults_to_empty(tmp_path: Path) -> None:
    """Repository.env defaults to an empty dict when not specified in TOML."""
    toml = """\
[repositories.r1]
repository = "rest:https://backup.example.com/"
password = "secret"

[profiles.myapp]
repository_ref = "r1"
[profiles.myapp.backup]
sources = ["/data"]
"""
    toml_file = tmp_path / "no-env.toml"
    toml_file.write_text(toml, encoding="utf-8")

    result = load_config(toml_file)
    repo = result.repositories["r1"]

    assert repo.env == {}
