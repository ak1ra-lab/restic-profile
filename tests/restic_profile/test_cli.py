"""CLI integration tests for restic_profile.

Tests call main() directly with argv lists and monkeypatch the runner entrypoint
where the CLI would otherwise shell out to restic(1).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from restic_profile.cli import main

# Inline TOML helpers

_VALID_TOML = """\
[global]
retry_lock = "10m"

[repositories.r1]
repository = "rest:https://backup.example.com/"
password = "secret"

[repositories.r2]
repository = "rest:https://backup.example.com/server"
password = "secret2"

[profiles.myapp]
repository_ref = "r1"
tag = "myapp"
on_calendar = "hourly"
randomized_delay_sec = "10min"
retry_lock = ""
[profiles.myapp.backup]
sources = ["/home/alice/myapp"]
exclude_patterns = ["*.log"]
[profiles.myapp.retention]
keep_last = 0
keep_hourly = 6
keep_daily = 7
keep_weekly = 4
keep_monthly = 3
keep_yearly = 0

[profiles.server_prune]
repository_ref = "r2"
on_calendar = "daily"
retry_lock = ""
[profiles.server_prune.retention]
keep_daily = 7
"""

_INVALID_PASSWORD_TOML = """\
[repositories.r1]
repository = "rest:https://example.com/"
password = ""

[profiles.bad]
repository_ref = "r1"
[profiles.bad.retention]
keep_daily = 7
"""

_MISSING_PASSWORD_AND_REPO_TOML = """\
[repositories.r1]
repository = ""
password = ""

[profiles.broken]
repository_ref = "r1"
[profiles.broken.backup]
sources = ["/data"]
"""


def _write_config(tmp_path: Path, content: str) -> Path:
    """Write *content* to a temporary TOML file and return its Path."""
    p = tmp_path / "restic-profile.toml"
    p.write_text(content, encoding="utf-8")
    return p


# check — valid config


def test_check_with_valid_config_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """restic-profile --check exits 0 and reports 'Config is valid'."""
    config_file = _write_config(tmp_path, _VALID_TOML)

    main(["--check", "-c", str(config_file)])

    captured = capsys.readouterr()
    assert "Config is valid" in captured.out + captured.err


# check — missing config


def test_check_with_missing_config_exits_1(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """restic-profile --check exits 1 and logs an error when the config is missing."""
    missing = tmp_path / "does_not_exist.toml"

    with pytest.raises(SystemExit) as exc_info:
        main(["--check", "--config", str(missing)])

    assert exc_info.value.code == 1
    assert "not found" in caplog.text.lower() or str(missing) in caplog.text


# check — invalid config


def test_check_with_invalid_config_exits_1(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """restic-profile --check exits 1 and logs an error for an invalid config."""
    config_file = _write_config(tmp_path, _INVALID_PASSWORD_TOML)

    with pytest.raises(SystemExit) as exc_info:
        main(["--check", "--config", str(config_file)])

    assert exc_info.value.code == 1
    assert "bad" in caplog.text or "password" in caplog.text.lower()


def test_check_with_missing_repo_and_password_exits_1(tmp_path: Path) -> None:
    """restic-profile --check exits 1 when both repository and password are empty."""
    config_file = _write_config(tmp_path, _MISSING_PASSWORD_AND_REPO_TOML)

    with pytest.raises(SystemExit) as exc_info:
        main(["--check", "--config", str(config_file)])

    assert exc_info.value.code == 1


# list — valid config


def test_list_with_valid_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """restic-profile --list prints profile names, types, and schedules."""
    config_file = _write_config(tmp_path, _VALID_TOML)

    main(["-l", "--config", str(config_file)])

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "myapp" in combined
    assert "server_prune" in combined
    assert "type=backup+retention" in combined
    assert "type=retention" in combined
    assert "schedule=hourly" in combined
    assert "schedule=daily" in combined


# list — missing config


def test_list_with_missing_config_exits_1(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """restic-profile --list exits 1 and logs an error when the config is missing."""
    missing = tmp_path / "no_config.toml"

    with pytest.raises(SystemExit) as exc_info:
        main(["--list", "--config", str(missing)])

    assert exc_info.value.code == 1
    assert "not found" in caplog.text.lower() or str(missing) in caplog.text


# run profile — mocked run_profile (success)


def test_run_profile_with_mocked_runner_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restic-profile <profile> exits 0 when run_profile succeeds."""
    config_file = _write_config(tmp_path, _VALID_TOML)
    monkeypatch.setattr("restic_profile.cli.run_profile", lambda *a, **kw: None)

    main(["myapp", "--config", str(config_file)])


def test_run_profile_calls_runner_with_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restic-profile <profile> passes the correct Profile to run_profile."""
    config_file = _write_config(tmp_path, _VALID_TOML)
    received: list[object] = []

    def fake_run_profile(profile: object, **kwargs: object) -> None:
        received.append(profile)

    monkeypatch.setattr("restic_profile.cli.run_profile", fake_run_profile)
    main(["myapp", "--config", str(config_file)])

    assert len(received) == 1
    assert getattr(received[0], "name", None) == "myapp"


def test_run_profile_dry_run_flag_is_forwarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restic-profile <profile> --dry-run forwards dry_run=True to run_profile."""
    config_file = _write_config(tmp_path, _VALID_TOML)
    received_kwargs: list[dict] = []

    def fake_run_profile(profile: object, **kwargs: object) -> None:
        received_kwargs.append(dict(kwargs))

    monkeypatch.setattr("restic_profile.cli.run_profile", fake_run_profile)
    main(["myapp", "--dry-run", "-c", str(config_file)])

    assert len(received_kwargs) == 1
    assert received_kwargs[0].get("dry_run") is True


# run profile — profile not found


def test_run_profile_nonexistent_profile_exits_1(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """restic-profile <profile> exits 1 and logs an error for an unknown profile."""
    config_file = _write_config(tmp_path, _VALID_TOML)

    with pytest.raises(SystemExit) as exc_info:
        main(["nonexistent", "--config", str(config_file)])

    assert exc_info.value.code == 1
    assert "nonexistent" in caplog.text or "not found" in caplog.text.lower()


# run profile — missing config


def test_run_profile_with_missing_config_exits_1(tmp_path: Path) -> None:
    """restic-profile <profile> exits 1 when the config file does not exist."""
    missing = tmp_path / "no_config.toml"

    with pytest.raises(SystemExit) as exc_info:
        main(["myapp", "--config", str(missing)])

    assert exc_info.value.code == 1


# run profile — run_profile raises ValueError


def test_run_profile_value_error_from_runner_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restic-profile <profile> exits 1 when run_profile raises ValueError."""
    config_file = _write_config(tmp_path, _VALID_TOML)

    def failing_run_profile(profile: object, **kwargs: object) -> None:
        raise ValueError("Profile 'server_prune' has no runnable workflow")

    monkeypatch.setattr("restic_profile.cli.run_profile", failing_run_profile)

    with pytest.raises(SystemExit) as exc_info:
        main(["server_prune", "--config", str(config_file)])

    assert exc_info.value.code == 1


def test_cli_requires_a_profile_or_action_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """restic-profile exits with usage when no profile or action flag is supplied."""
    with pytest.raises(SystemExit) as exc_info:
        main([])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "provide a profile name" in captured.err


def test_cli_rejects_profile_name_with_list_flag(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """restic-profile rejects combining a profile name with --list."""
    config_file = _write_config(tmp_path, _VALID_TOML)

    with pytest.raises(SystemExit) as exc_info:
        main(["myapp", "--list", "--config", str(config_file)])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "cannot be combined" in captured.err


_VALID_TOML_WITH_NOTIFY = """\
[global]
retry_lock = "10m"

[notify.test_bot]
type = "telegram"
token = "test-token"
chat_id = 123456789

[repositories.r1]
repository = "rest:https://backup.example.com/"
password = "secret"

[repositories.r2]
repository = "rest:https://backup.example.com/server"
password = "secret2"

[profiles.myapp]
repository_ref = "r1"
tag = "myapp"
on_calendar = "hourly"
randomized_delay_sec = "10min"
retry_lock = ""
notify_ref = "test_bot"
[profiles.myapp.backup]
sources = ["/home/alice/myapp"]
exclude_patterns = ["*.log"]
[profiles.myapp.retention]
keep_last = 0
keep_hourly = 6
keep_daily = 7
keep_weekly = 4
keep_monthly = 3
keep_yearly = 0

[profiles.server_prune]
repository_ref = "r2"
on_calendar = "daily"
retry_lock = ""
[profiles.server_prune.retention]
keep_daily = 7
"""


def test_dry_run_notify_routes_to_run_profile_with_force_notify(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--dry-run notify calls run_profile with dry_run=True and force_notify=True."""
    config_file = _write_config(tmp_path, _VALID_TOML_WITH_NOTIFY)
    with patch("restic_profile.runner.run_backup") as mock_backup:
        main(["--dry-run", "notify", "myapp", "-c", str(config_file)])
    mock_backup.assert_called_once()
    call_kwargs = mock_backup.call_args.kwargs
    assert call_kwargs["dry_run"] is True
    assert call_kwargs["force_notify"] is True


def test_dry_run_notify_requires_profile_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--dry-run notify without a profile name exits with error."""
    config_file = _write_config(tmp_path, _VALID_TOML)
    with pytest.raises(SystemExit) as exc_info:
        main(["--dry-run", "notify", "-c", str(config_file)])
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "provide a profile name" in captured.err
