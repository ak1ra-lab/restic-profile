"""Tests for restic_profile.runner execution and environment helpers."""

from __future__ import annotations

import os
import pwd
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from restic_profile import runner as runner_module
from restic_profile.config import Profile
from restic_profile.runner import (
    WorkflowError,
    build_env,
    build_forget_args,
    build_global_args,
    run_backup,
    run_hooks,
    run_profile,
    run_retention,
)

# Helpers


def _success_run(args: list[str], **kwargs: object) -> MagicMock:
    """subprocess.run side-effect that always returns exit code 0."""
    return MagicMock(returncode=0, stdout="", stderr="")


# build_env — basic credentials


def test_build_env_sets_required_credentials(backup_profile: Profile) -> None:
    """build_env() sets RESTIC_REPOSITORY and RESTIC_PASSWORD from the profile."""
    env = build_env(backup_profile)

    assert env["RESTIC_REPOSITORY"] == backup_profile.resolved_repository.repository
    assert env["RESTIC_PASSWORD"] == backup_profile.resolved_repository.password


def test_build_env_sets_home_and_xdg_cache_home_fallbacks(
    backup_profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_env() derives HOME and XDG_CACHE_HOME when the parent env lacks them."""
    current_user = pwd.getpwuid(os.getuid())
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    env = build_env(backup_profile)

    assert env["HOME"] == current_user.pw_dir
    assert env["XDG_CACHE_HOME"] == f"{current_user.pw_dir}/.cache"


def test_build_env_uses_existing_home_for_xdg_cache_home_fallback(
    backup_profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_env() preserves HOME and derives XDG_CACHE_HOME from it when needed."""
    monkeypatch.setenv("HOME", "/tmp/restic-home")
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    env = build_env(backup_profile)

    assert env["HOME"] == "/tmp/restic-home"
    assert env["XDG_CACHE_HOME"] == "/tmp/restic-home/.cache"


# build_env — REST backend credentials


def test_build_env_rest_credentials(backup_profile: Profile) -> None:
    """build_env() sets REST vars when rest_username is set; omits them when empty."""
    backup_profile.resolved_repository.rest_username = "alice"
    backup_profile.resolved_repository.rest_password = "restpassword"
    env = build_env(backup_profile)
    assert env["RESTIC_REST_USERNAME"] == "alice"
    assert env["RESTIC_REST_PASSWORD"] == "restpassword"

    backup_profile.resolved_repository.rest_username = ""
    backup_profile.resolved_repository.rest_password = ""
    env = build_env(backup_profile)
    assert "RESTIC_REST_USERNAME" not in env
    assert "RESTIC_REST_PASSWORD" not in env


def test_build_env_cacert(backup_profile: Profile) -> None:
    """build_env() sets RESTIC_CACERT when cacert is non-empty; omits it when empty."""
    backup_profile.resolved_repository.cacert = "/etc/ssl/certs/my-ca.crt"
    assert build_env(backup_profile)["RESTIC_CACERT"] == "/etc/ssl/certs/my-ca.crt"

    backup_profile.resolved_repository.cacert = ""
    assert "RESTIC_CACERT" not in build_env(backup_profile)


# build_env — AWS credentials


def test_build_env_aws_credentials(backup_profile: Profile) -> None:
    """build_env() sets all AWS_* vars when aws_access_key_id is set; omits them when empty."""
    backup_profile.resolved_repository.aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"
    backup_profile.resolved_repository.aws_secret_access_key = (
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    )
    backup_profile.resolved_repository.aws_default_region = "us-east-1"
    env = build_env(backup_profile)
    assert env["AWS_ACCESS_KEY_ID"] == "AKIAIOSFODNN7EXAMPLE"
    assert env["AWS_SECRET_ACCESS_KEY"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    assert env["AWS_DEFAULT_REGION"] == "us-east-1"

    backup_profile.resolved_repository.aws_default_region = ""
    env = build_env(backup_profile)
    assert env["AWS_ACCESS_KEY_ID"] == "AKIAIOSFODNN7EXAMPLE"
    assert env["AWS_SECRET_ACCESS_KEY"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    assert "AWS_DEFAULT_REGION" not in env

    backup_profile.resolved_repository.aws_access_key_id = ""
    env = build_env(backup_profile)
    assert "AWS_ACCESS_KEY_ID" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "AWS_DEFAULT_REGION" not in env


# build_env — GCS credentials


def test_build_env_gcs_project_id_only(backup_profile: Profile) -> None:
    """build_env() sets GOOGLE_PROJECT_ID when google_project_id is set (ADC environment)."""
    backup_profile.resolved_repository.google_project_id = "my-project-123"
    env = build_env(backup_profile)
    assert env["GOOGLE_PROJECT_ID"] == "my-project-123"
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in env
    assert "GOOGLE_ACCESS_TOKEN" not in env


def test_build_env_gcs_application_credentials(backup_profile: Profile) -> None:
    """build_env() sets GOOGLE_APPLICATION_CREDENTIALS when credentials file is specified."""
    backup_profile.resolved_repository.google_project_id = "my-project-123"
    backup_profile.resolved_repository.google_application_credentials = (
        "/etc/gcs/key.json"
    )
    env = build_env(backup_profile)
    assert env["GOOGLE_PROJECT_ID"] == "my-project-123"
    assert env["GOOGLE_APPLICATION_CREDENTIALS"] == "/etc/gcs/key.json"
    assert "GOOGLE_ACCESS_TOKEN" not in env


def test_build_env_gcs_access_token_takes_precedence(backup_profile: Profile) -> None:
    """build_env() sets GOOGLE_ACCESS_TOKEN and omits credentials file when token is set."""
    backup_profile.resolved_repository.google_project_id = "my-project-123"
    backup_profile.resolved_repository.google_application_credentials = (
        "/etc/gcs/key.json"
    )
    backup_profile.resolved_repository.google_access_token = "ya29.some-token"
    env = build_env(backup_profile)
    assert env["GOOGLE_PROJECT_ID"] == "my-project-123"
    assert env["GOOGLE_ACCESS_TOKEN"] == "ya29.some-token"
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in env


def test_build_env_gcs_omitted_when_project_id_empty(backup_profile: Profile) -> None:
    """build_env() omits all GOOGLE_* vars when google_project_id is empty."""
    backup_profile.resolved_repository.google_project_id = ""
    backup_profile.resolved_repository.google_application_credentials = ""
    backup_profile.resolved_repository.google_access_token = ""
    env = build_env(backup_profile)
    assert "GOOGLE_PROJECT_ID" not in env
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in env
    assert "GOOGLE_ACCESS_TOKEN" not in env


# build_global_args


def test_build_global_args_returns_retry_lock_when_set(
    backup_profile: Profile,
) -> None:
    """build_global_args() includes --retry-lock when profile.retry_lock is non-empty."""
    backup_profile.retry_lock = "10m"

    args = build_global_args(backup_profile)

    assert "--retry-lock" in args
    assert "10m" in args


def test_build_global_args_returns_empty_when_retry_lock_empty(
    backup_profile: Profile,
) -> None:
    """build_global_args() returns [] when retry_lock is empty."""
    backup_profile.retry_lock = ""

    args = build_global_args(backup_profile)

    assert args == []


def test_build_global_args_includes_no_cache_when_enabled(
    backup_profile: Profile,
) -> None:
    """build_global_args() includes --no-cache when profile.no_cache is true."""
    backup_profile.no_cache = True
    backup_profile.retry_lock = ""

    args = build_global_args(backup_profile)

    assert args == ["--no-cache"]


def test_build_global_args_includes_no_cache_and_retry_lock(
    backup_profile: Profile,
) -> None:
    """build_global_args() keeps all configured restic flags without probing."""
    backup_profile.no_cache = True
    backup_profile.retry_lock = "10m"

    args = build_global_args(backup_profile)

    assert args == ["--no-cache", "--retry-lock", "10m"]


def test_restic_executable_uses_path_resolution_by_default(
    backup_profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner resolves the default restic command to an absolute path from PATH."""
    monkeypatch.setattr(
        "restic_profile.runner.shutil.which",
        lambda command: "/usr/local/bin/restic" if command == "restic" else None,
    )

    assert runner_module._restic_executable(backup_profile) == "/usr/local/bin/restic"


def test_restic_executable_prefers_configured_absolute_path(
    backup_profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner keeps an explicitly configured absolute restic path."""
    monkeypatch.setattr(
        "restic_profile.runner.shutil.which",
        lambda command: "/usr/bin/restic" if command == "restic" else None,
    )
    backup_profile.restic_binary = "/usr/local/bin/restic"

    assert runner_module._restic_executable(backup_profile) == "/usr/local/bin/restic"


def test_repo_initialized_retries_without_internal_no_cache(
    backup_profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repo check retries without internal --no-cache when the first probe fails."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0 if len(calls) == 2 else 1, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert runner_module._repo_initialized(backup_profile, {}) is True
    assert len(calls) == 2
    assert Path(calls[0][0]).name == "restic"
    assert calls[0][-2:] == ["cat", "config"]
    assert "--no-cache" in calls[0]
    assert calls[1][-2:] == ["cat", "config"]
    assert "--no-cache" not in calls[1]


def test_repo_initialized_uses_profile_no_cache_without_plain_retry(
    backup_profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repo check does not retry without --no-cache when the profile requires it."""
    calls: list[list[str]] = []
    backup_profile.no_cache = True

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert runner_module._repo_initialized(backup_profile, {}) is True
    assert len(calls) == 1
    assert "--no-cache" in calls[0]


# build_forget_args — no retention policy


def test_build_forget_args_returns_empty_when_all_keep_zero() -> None:
    """build_forget_args() returns [] when all keep_* fields are 0."""
    from restic_profile.config import BackupConfig, Repository

    repo = Repository(
        name="r1", repository="rest:https://example.com/", password="secret"
    )
    profile = Profile(
        name="nopolicy",
        repository_ref="r1",
        resolved_repository=repo,
        backup=BackupConfig(sources=["/data"]),
    )

    assert build_forget_args(profile) == []


# build_forget_args — retention policy present


def test_build_forget_args_includes_all_nonzero_keep_flags(
    backup_profile: Profile,
) -> None:
    """build_forget_args() scopes forget by tag and includes the configured keep_* flags."""
    backup_profile.retention.keep_hourly = 6
    backup_profile.retention.keep_daily = 7
    backup_profile.retention.keep_weekly = 4
    backup_profile.retention.keep_monthly = 3
    backup_profile.retention.keep_last = 0
    backup_profile.retention.keep_yearly = 0

    args = build_forget_args(backup_profile)

    assert args[0] == "forget"
    assert "--tag" in args
    assert args[args.index("--tag") + 1] == backup_profile.tag
    assert "--keep-hourly" in args and args[args.index("--keep-hourly") + 1] == "6"
    assert "--keep-daily" in args and args[args.index("--keep-daily") + 1] == "7"
    assert "--keep-weekly" in args
    assert "--keep-monthly" in args
    assert "--keep-last" not in args
    assert "--keep-yearly" not in args


def test_build_forget_args_includes_host_when_requested(
    backup_profile: Profile,
) -> None:
    """build_forget_args() includes --host when current_host_only is enabled."""
    args = build_forget_args(
        backup_profile,
        current_host_only=True,
        snapshot_host="test-host",
    )

    assert "--host" in args
    assert args[args.index("--host") + 1] == "test-host"


# run_backup — ValueError for prune-only profile


def test_run_backup_raises_value_error_for_prune_only_profile(
    prune_profile: Profile,
) -> None:
    """run_backup() raises ValueError (mentioning the profile name) for a prune-only profile."""
    with pytest.raises(ValueError, match="has no backup block") as exc_info:
        run_backup(prune_profile)

    assert prune_profile.name in str(exc_info.value)


# run_backup — subprocess calls (normal flow)


def test_run_profile_dispatches_mixed_profiles_to_backup(
    backup_profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_profile() routes mixed profiles through the backup workflow."""
    calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        "restic_profile.runner.run_backup",
        lambda profile, *, dry_run=False: calls.append((profile.name, dry_run)),
    )
    monkeypatch.setattr(
        "restic_profile.runner.run_retention",
        lambda profile, *, dry_run=False: calls.append(
            (f"retention:{profile.name}", dry_run)
        ),
    )

    run_profile(backup_profile, dry_run=True)

    assert calls == [("myapp", True)]


def test_run_profile_dispatches_retention_only_profiles_to_retention(
    prune_profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_profile() routes retention-only profiles to the retention workflow."""
    calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        "restic_profile.runner.run_retention",
        lambda profile, *, dry_run=False: calls.append((profile.name, dry_run)),
    )

    run_profile(prune_profile, dry_run=True)

    assert calls == [("server_prune", True)]


def test_run_backup_invokes_restic_backup_with_correct_args(
    backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() calls restic backup with the tag and source paths."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr("restic_profile.runner._snapshot_host", lambda: "test-host")
    monkeypatch.setattr(subprocess, "run", fake_run)
    run_backup(backup_profile)

    backup_calls = [c for c in calls if "backup" in c]
    assert len(backup_calls) >= 1
    backup_cmd = backup_calls[0]
    assert Path(backup_cmd[0]).name == "restic"
    assert "--host" in backup_cmd
    assert backup_cmd[backup_cmd.index("--host") + 1] == "test-host"
    assert "--tag" in backup_cmd
    assert backup_profile.tag in backup_cmd
    for source in backup_profile.backup.sources:
        assert source in backup_cmd


def test_run_backup_runs_retention_when_profile_has_retention(
    backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() calls restic forget when the profile has retention config."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr("restic_profile.runner._snapshot_host", lambda: "test-host")
    monkeypatch.setattr(subprocess, "run", fake_run)
    run_backup(backup_profile)

    forget_calls = [c for c in calls if "forget" in c]
    assert len(forget_calls) >= 1
    forget_cmd = forget_calls[0]
    assert "--host" in forget_cmd
    assert forget_cmd[forget_cmd.index("--host") + 1] == "test-host"
    assert "--tag" in forget_cmd
    assert forget_cmd[forget_cmd.index("--tag") + 1] == backup_profile.tag


def test_run_backup_skips_retention_when_no_retention_block(
    backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() does not call restic forget when retention is not configured."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    backup_profile.retention = None
    run_backup(backup_profile)

    forget_calls = [c for c in calls if "forget" in c]
    assert len(forget_calls) == 0


def test_run_backup_skips_retention_when_no_retention_policy(
    backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() executes restic prune when retention is prune-only."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    backup_profile.retention.keep_last = 0
    backup_profile.retention.keep_hourly = 0
    backup_profile.retention.keep_daily = 0
    backup_profile.retention.keep_weekly = 0
    backup_profile.retention.keep_monthly = 0
    backup_profile.retention.keep_yearly = 0
    backup_profile.retention.prune = True
    run_backup(backup_profile)

    forget_calls = [c for c in calls if "forget" in c]
    assert len(forget_calls) == 0
    prune_calls = [c for c in calls if "prune" in c]
    assert len(prune_calls) == 1


# run_backup — dry_run


def test_run_backup_dry_run_skips_subprocess_calls(
    backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup(dry_run=True) does not invoke subprocess.run and does not raise."""
    calls: list[list[str]] = []

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kw: calls.append(args) or MagicMock(returncode=0),
    )
    run_backup(backup_profile, dry_run=True)

    assert calls == []


def test_run_backup_skips_missing_sources(
    backup_profile: Profile,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """run_backup() warns and omits any configured source path that does not exist."""
    calls: list[list[str]] = []
    missing_source = tmp_path / "missing"
    existing_source = backup_profile.backup.sources[0]
    backup_profile.backup.sources = [existing_source, str(missing_source)]

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_backup(backup_profile)

    backup_calls = [call for call in calls if "backup" in call]
    assert len(backup_calls) >= 1
    assert existing_source in backup_calls[0]
    assert str(missing_source) not in backup_calls[0]
    assert "skipping missing backup source" in caplog.text.lower()


def test_run_backup_raises_value_error_when_all_sources_missing(
    backup_profile: Profile,
    tmp_path: Path,
) -> None:
    """run_backup() raises ValueError when every configured source path is missing."""
    backup_profile.backup.sources = [str(tmp_path / "missing")]

    with pytest.raises(ValueError, match="no existing sources"):
        run_backup(backup_profile, dry_run=True)


def test_run_backup_passes_one_file_system_when_enabled(
    backup_profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_backup() adds --one-file-system when the profile enables it."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    backup_profile.backup.one_file_system = True
    run_backup(backup_profile)

    backup_calls = [call for call in calls if "backup" in call]
    assert len(backup_calls) >= 1
    assert "--one-file-system" in backup_calls[0]


def test_run_backup_continues_when_init_reports_existing_repository(
    backup_profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_backup() continues when restic init fails because the repo already exists."""
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], env: dict[str, str], *, capture_output: bool = False):
        calls.append(list(cmd))
        if cmd[-1] == "init":
            raise runner_module._CommandError(
                cmd,
                1,
                stderr=("Fatal: create repository failed: config file already exists"),
            )
        return MagicMock(returncode=0)

    monkeypatch.setattr(
        "restic_profile.runner._repo_initialized",
        lambda profile, env: False,
    )
    monkeypatch.setattr("restic_profile.runner._run", fake_run)

    run_backup(backup_profile)

    assert any(call[-1] == "init" for call in calls)
    assert any("backup" in call for call in calls)


# run_forget — ValueError when no retention policy


def test_run_retention_raises_value_error_when_no_retention_block(
    prune_profile: Profile,
) -> None:
    """run_retention() raises ValueError when the profile has no retention block."""
    prune_profile.retention = None

    with pytest.raises(ValueError, match="no retention block") as exc_info:
        run_retention(prune_profile)

    assert prune_profile.name in str(exc_info.value)


def test_run_retention_raises_value_error_when_no_retention_action(
    prune_profile: Profile,
) -> None:
    """run_retention() raises ValueError when keep_* are all 0 and prune is disabled."""
    prune_profile.retention.keep_last = 0
    prune_profile.retention.keep_hourly = 0
    prune_profile.retention.keep_daily = 0
    prune_profile.retention.keep_weekly = 0
    prune_profile.retention.keep_monthly = 0
    prune_profile.retention.keep_yearly = 0
    prune_profile.retention.prune = False

    with pytest.raises(ValueError, match="no retention action") as exc_info:
        run_retention(prune_profile)

    assert prune_profile.name in str(exc_info.value)


# run_forget — subprocess calls


def test_run_retention_invokes_restic_forget_without_prune_by_default(
    prune_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_retention() calls restic forget scoped by host and tag without --prune by default."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_retention(prune_profile)

    assert len(calls) == 1
    cmd = calls[0]
    assert Path(cmd[0]).name == "restic"
    assert "forget" in cmd
    assert "--host" in cmd
    assert "--tag" in cmd
    assert cmd[cmd.index("--tag") + 1] == prune_profile.tag
    assert "--prune" not in cmd
    assert "--keep-daily" in cmd


def test_run_retention_includes_host_when_profile_requests_current_host_only(
    prune_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_retention() appends --host when forget_current_host is enabled."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr("restic_profile.runner._snapshot_host", lambda: "test-host")
    monkeypatch.setattr(subprocess, "run", fake_run)
    prune_profile.retention.forget_current_host = True
    run_retention(prune_profile)

    assert "--host" in calls[0]
    assert calls[0][calls[0].index("--host") + 1] == "test-host"


def test_run_retention_uses_resolved_restic_binary(
    prune_profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_retention() uses the resolved absolute restic executable in commands."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    prune_profile.restic_binary = "/usr/local/bin/restic"
    run_retention(prune_profile)

    assert len(calls) == 1
    assert calls[0][0] == "/usr/local/bin/restic"


def test_run_retention_uses_profile_prune_default(
    prune_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_retention() appends --prune when the profile enables it."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    prune_profile.retention.prune = True
    run_retention(prune_profile)

    assert "--prune" in calls[0]


def test_run_retention_invokes_standalone_prune_when_prune_only(
    prune_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_retention() calls restic prune when prune=true and no keep_* policy exists."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    prune_profile.retention.keep_last = 0
    prune_profile.retention.keep_hourly = 0
    prune_profile.retention.keep_daily = 0
    prune_profile.retention.keep_weekly = 0
    prune_profile.retention.keep_monthly = 0
    prune_profile.retention.keep_yearly = 0
    prune_profile.retention.prune = True
    run_retention(prune_profile)

    assert len(calls) == 1
    assert calls[0][-1] == "prune"
    assert "forget" not in calls[0]


# run_forget — dry_run


def test_run_retention_dry_run_skips_subprocess_calls(
    prune_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_retention(dry_run=True) does not invoke subprocess.run and does not raise."""
    calls: list[list[str]] = []

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kw: calls.append(args) or MagicMock(returncode=0),
    )
    run_retention(prune_profile, dry_run=True)

    assert calls == []


# run_forget — global args propagated


def test_run_retention_includes_retry_lock_in_command(
    prune_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_retention() includes --retry-lock in the command when profile.retry_lock is set."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    prune_profile.retry_lock = "5m"
    run_retention(prune_profile)

    forget_calls = [call for call in calls if "forget" in call]
    assert len(forget_calls) == 1
    assert "--retry-lock" in forget_calls[0]
    idx = forget_calls[0].index("--retry-lock")
    assert forget_calls[0][idx + 1] == "5m"


# run_backup — exclude_file option (--exclude-file flag)


def test_run_backup_passes_exclude_file_flag_when_set(
    backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() adds --exclude-file <path> when exclude_file is non-empty."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    backup_profile.backup.exclude_file = (
        "/etc/restic-profile/restic-profile-myapp.exclude"
    )
    run_backup(backup_profile)

    backup_calls = [c for c in calls if "backup" in c]
    assert len(backup_calls) >= 1
    backup_cmd = backup_calls[0]
    assert "--exclude-file" in backup_cmd
    assert "/etc/restic-profile/restic-profile-myapp.exclude" in backup_cmd


def test_run_backup_exclude_file_path_follows_exclude_file_flag(
    backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() places the path immediately after --exclude-file."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    exclude_path = "/etc/restic-profile/restic-profile-myapp.exclude"
    backup_profile.backup.exclude_file = exclude_path
    run_backup(backup_profile)

    backup_calls = [c for c in calls if "backup" in c]
    backup_cmd = backup_calls[0]
    idx = backup_cmd.index("--exclude-file")
    assert backup_cmd[idx + 1] == exclude_path


def test_run_backup_does_not_pass_exclude_file_when_not_set(
    backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() does not add --exclude-file when exclude_file is empty."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    backup_profile.backup.exclude_file = ""
    run_backup(backup_profile)

    backup_calls = [c for c in calls if "backup" in c]
    assert len(backup_calls) >= 1
    assert "--exclude-file" not in backup_calls[0]


def test_run_backup_passes_both_exclude_patterns_and_exclude_file(
    backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() passes both --exclude flags and --exclude-file when both are set.

    exclude_patterns and exclude_file are independent and additive:
    the former generates multiple ``--exclude pattern`` flags (for inline short lists)
    while the latter generates a single ``--exclude-file path`` flag (for large lists
    rendered by Ansible from exclude_file_content).  Both are passed to the same
    restic backup invocation.
    """
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    backup_profile.backup.exclude_patterns = ["*.log", "*.tmp"]
    backup_profile.backup.exclude_file = (
        "/etc/restic-profile/restic-profile-myapp.exclude"
    )
    run_backup(backup_profile)

    backup_calls = [c for c in calls if "backup" in c]
    assert len(backup_calls) >= 1
    backup_cmd = backup_calls[0]

    # Inline patterns passed as --exclude flags
    assert "--exclude" in backup_cmd
    assert "*.log" in backup_cmd
    assert "*.tmp" in backup_cmd

    # Exclude file passed as --exclude-file
    assert "--exclude-file" in backup_cmd


# run_forget — failure triggers WorkflowError


def test_run_retention_raises_on_restic_failure(
    prune_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_retention() raises WorkflowError when restic exits non-zero."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: MagicMock(returncode=1))

    with pytest.raises(WorkflowError, match="retention command failed"):
        run_retention(prune_profile)


# run_hooks — empty list


def test_run_hooks_empty_list_returns_true_without_subprocess_calls(
    backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_hooks() returns True and makes no subprocess calls for an empty list."""
    env = {"KEY": "val"}
    calls: list = []
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: calls.append(a) or MagicMock(returncode=0)
    )

    result = run_hooks([], env)

    assert result is True
    assert calls == []


# run_hooks — success


def test_run_hooks_all_succeed_returns_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_hooks() returns True when all hook commands exit zero."""
    env: dict[str, str] = {}
    calls: list = []
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: calls.append(a) or MagicMock(returncode=0)
    )

    result = run_hooks(["echo a", "echo b"], env, "/bin/sh")

    assert result is True
    assert len(calls) == 2


def test_run_hooks_invokes_shell_with_dash_c(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_hooks() calls subprocess.run([shell, '-c', command], ...)."""
    env: dict[str, str] = {}
    calls: list = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: calls.append(a[0]) or MagicMock(returncode=0),
    )

    run_hooks(["echo hello"], env, "/bin/bash")

    assert calls[0] == ["/bin/bash", "-c", "echo hello"]


def test_run_hooks_uses_default_shell_when_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_hooks() defaults to /bin/sh when no shell is specified."""
    env: dict[str, str] = {}
    calls: list = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: calls.append(a[0]) or MagicMock(returncode=0),
    )

    run_hooks(["echo hi"], env)

    assert calls[0][0] == "/bin/sh"


# run_hooks — failure


def test_run_hooks_returns_false_on_first_failure_and_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_hooks() returns False on first non-zero exit and does not run subsequent commands."""
    env: dict[str, str] = {}
    calls: list = []

    def fake_run(args: list, **kw: object) -> MagicMock:
        calls.append(args)
        # fail the first command only; second should never be reached
        return MagicMock(returncode=1 if len(calls) == 1 else 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_hooks(["fail cmd", "should not run"], env)

    assert result is False
    assert len(calls) == 1


# run_hooks — dry_run


def test_run_hooks_dry_run_logs_without_executing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_hooks(dry_run=True) returns True and makes no subprocess calls."""
    env: dict[str, str] = {}
    calls: list = []
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: calls.append(a) or MagicMock(returncode=0)
    )

    result = run_hooks(["echo x", "echo y"], env, dry_run=True)

    assert result is True
    assert calls == []


# run_backup — hook phase ordering


def test_run_backup_runs_prevalidate_hooks_before_backup(
    hooks_backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() calls prevalidate hooks before the restic backup command."""
    order: list[str] = []

    def fake_run(args: list[str], **kw: object) -> MagicMock:
        if args[:2] == ["/bin/sh", "-c"]:
            order.append(f"hook:{args[2]}")
        elif "backup" in args:
            order.append("backup")
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_backup(hooks_backup_profile)

    assert "hook:echo prevalidate" in order
    assert order.index("hook:echo prevalidate") < order.index("backup")


def test_run_backup_runs_before_hooks_before_backup(
    hooks_backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() calls before hooks before the restic backup command."""
    order: list[str] = []

    def fake_run(args: list[str], **kw: object) -> MagicMock:
        if args[:2] == ["/bin/sh", "-c"]:
            order.append(f"hook:{args[2]}")
        elif "backup" in args:
            order.append("backup")
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_backup(hooks_backup_profile)

    assert "hook:echo before" in order
    assert order.index("hook:echo before") < order.index("backup")


def test_run_backup_runs_after_hooks_after_backup(
    hooks_backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() calls after hooks after the restic backup command."""
    order: list[str] = []

    def fake_run(args: list[str], **kw: object) -> MagicMock:
        if args[:2] == ["/bin/sh", "-c"]:
            order.append(f"hook:{args[2]}")
        elif "backup" in args:
            order.append("backup")
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_backup(hooks_backup_profile)

    assert "hook:echo after" in order
    assert order.index("backup") < order.index("hook:echo after")


def test_run_backup_runs_success_hooks_on_success(
    hooks_backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() calls success hooks when backup and forget succeed."""
    hook_calls: list[str] = []

    def fake_run(args: list[str], **kw: object) -> MagicMock:
        if args[:2] == ["/bin/sh", "-c"]:
            hook_calls.append(args[2])
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_backup(hooks_backup_profile)

    assert "echo success" in hook_calls
    assert "echo failure" not in hook_calls


# run_backup — hook failure cases


def test_run_backup_runs_failure_hooks_and_raises_when_prevalidate_fails(
    hooks_backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() runs failure hooks and raises when a prevalidate hook fails."""
    hook_calls: list[str] = []
    backup_called = False

    def fake_run(args: list[str], **kw: object) -> MagicMock:
        nonlocal backup_called
        if args[:2] == ["/bin/sh", "-c"]:
            hook_calls.append(args[2])
            # fail prevalidate
            if args[2] == "echo prevalidate":
                return MagicMock(returncode=1)
        elif "backup" in args:
            backup_called = True
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(WorkflowError, match="prevalidate hook failed"):
        run_backup(hooks_backup_profile)

    assert "echo failure" in hook_calls
    assert backup_called is False
    assert "echo after" not in hook_calls


def test_run_backup_runs_failure_hooks_and_raises_when_before_fails(
    hooks_backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() runs failure hooks and raises when a before hook fails."""
    hook_calls: list[str] = []
    backup_called = False

    def fake_run(args: list[str], **kw: object) -> MagicMock:
        nonlocal backup_called
        if args[:2] == ["/bin/sh", "-c"]:
            hook_calls.append(args[2])
            if args[2] == "echo before":
                return MagicMock(returncode=1)
        elif "backup" in args:
            backup_called = True
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(WorkflowError, match="before hook failed"):
        run_backup(hooks_backup_profile)

    assert "echo failure" in hook_calls
    assert backup_called is False
    assert "echo after" not in hook_calls


def test_run_backup_runs_after_and_failure_hooks_and_raises_when_backup_fails(
    hooks_backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup() runs after and failure hooks then raises when backup fails."""
    hook_calls: list[str] = []

    def fake_run(args: list[str], **kw: object) -> MagicMock:
        if args[:2] == ["/bin/sh", "-c"]:
            hook_calls.append(args[2])
            return MagicMock(returncode=0)
        # fail the backup command
        if "backup" in args:
            return MagicMock(returncode=1)
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(WorkflowError, match="backup command failed"):
        run_backup(hooks_backup_profile)

    assert "echo after" in hook_calls
    assert "echo failure" in hook_calls
    assert "echo success" not in hook_calls


def test_run_backup_exclude_file_is_ignored_in_dry_run(
    backup_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_backup(dry_run=True) does not invoke subprocess.run even when exclude_file is set."""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        calls.append(list(args))
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    backup_profile.backup.exclude_file = (
        "/etc/restic-profile/restic-profile-myapp.exclude"
    )
    run_backup(backup_profile, dry_run=True)

    # dry_run must never call subprocess regardless of exclude settings
    assert calls == []
