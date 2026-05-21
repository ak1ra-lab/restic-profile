"""CLI integration tests for restic_profile.

Tests call main() directly with a list of argv tokens and use capsys to
capture stdout/stderr.  run_backup and run_forget are monkeypatched wherever
the CLI would shell out to restic(1).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from restic_profile.cli import main

# Inline TOML helpers

_VALID_TOML = """\
[global]
retry_lock = "10m"

[profiles.myapp]
repository = "rest:https://backup.example.com/"
password = "secret"
sources = ["/home/alice/myapp"]
tag = "myapp"
exclude_patterns = ["*.log"]
forget = true
keep_last = 0
keep_hourly = 6
keep_daily = 7
keep_weekly = 4
keep_monthly = 3
keep_yearly = 0
on_calendar = "hourly"
randomized_delay_sec = "10min"
system_user = "root"
retry_lock = ""

[profiles.server_prune]
repository = "rest:https://backup.example.com/server"
password = "secret2"
sources = []
keep_daily = 7
on_calendar = "daily"
system_user = "root"
retry_lock = ""
"""

_INVALID_PASSWORD_TOML = """\
[profiles.bad]
repository = "rest:https://example.com/"
password = ""
sources = []
keep_daily = 7
"""

_MISSING_PASSWORD_AND_REPO_TOML = """\
[profiles.broken]
repository = ""
password = ""
sources = ["/data"]
"""


def _write_config(tmp_path: Path, content: str) -> Path:
    """Write *content* to a temporary TOML file and return its Path."""
    p = tmp_path / "restic-profile.toml"
    p.write_text(content, encoding="utf-8")
    return p


# validate — valid config


def test_validate_with_valid_config_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """restic-profile validate exits 0 and reports 'Config is valid' for a valid config."""
    config_file = _write_config(tmp_path, _VALID_TOML)

    main(["validate", "--config", str(config_file)])

    captured = capsys.readouterr()
    assert "Config is valid" in captured.out + captured.err


# validate — missing config


def test_validate_with_missing_config_exits_1(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """restic-profile validate exits 1 and logs an error when the config is missing."""
    missing = tmp_path / "does_not_exist.toml"

    with pytest.raises(SystemExit) as exc_info:
        main(["validate", "--config", str(missing)])

    assert exc_info.value.code == 1
    assert "not found" in caplog.text.lower() or str(missing) in caplog.text


# validate — invalid config


def test_validate_with_invalid_config_exits_1(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """restic-profile validate exits 1 and logs an error for an invalid config."""
    config_file = _write_config(tmp_path, _INVALID_PASSWORD_TOML)

    with pytest.raises(SystemExit) as exc_info:
        main(["validate", "--config", str(config_file)])

    assert exc_info.value.code == 1
    assert "bad" in caplog.text or "password" in caplog.text.lower()


def test_validate_with_missing_repo_and_password_exits_1(tmp_path: Path) -> None:
    """restic-profile validate exits 1 when both repository and password are empty."""
    config_file = _write_config(tmp_path, _MISSING_PASSWORD_AND_REPO_TOML)

    with pytest.raises(SystemExit) as exc_info:
        main(["validate", "--config", str(config_file)])

    assert exc_info.value.code == 1


# list — valid config


def test_list_with_valid_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """restic-profile list exits 0 and prints profile names, types, and schedules."""
    config_file = _write_config(tmp_path, _VALID_TOML)

    main(["list", "--config", str(config_file)])

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "myapp" in combined
    assert "server_prune" in combined
    assert "backup" in combined
    assert "retention-only" in combined
    assert "hourly" in combined or "daily" in combined


# list — missing config


def test_list_with_missing_config_exits_1(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """restic-profile list exits 1 and logs an error when the config is missing."""
    missing = tmp_path / "no_config.toml"

    with pytest.raises(SystemExit) as exc_info:
        main(["list", "--config", str(missing)])

    assert exc_info.value.code == 1
    assert "not found" in caplog.text.lower() or str(missing) in caplog.text


# backup — mocked run_backup (success)


def test_backup_with_mocked_run_backup_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restic-profile backup exits 0 when run_backup succeeds."""
    config_file = _write_config(tmp_path, _VALID_TOML)
    monkeypatch.setattr("restic_profile.cli.run_backup", lambda *a, **kw: None)

    main(["backup", "myapp", "--config", str(config_file)])


def test_backup_calls_run_backup_with_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restic-profile backup passes the correct Profile to run_backup."""
    config_file = _write_config(tmp_path, _VALID_TOML)
    received: list[object] = []

    def fake_run_backup(profile: object, **kwargs: object) -> None:
        received.append(profile)

    monkeypatch.setattr("restic_profile.cli.run_backup", fake_run_backup)
    main(["backup", "myapp", "--config", str(config_file)])

    assert len(received) == 1
    assert getattr(received[0], "name", None) == "myapp"


def test_backup_dry_run_flag_is_forwarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restic-profile backup --dry-run forwards dry_run=True to run_backup."""
    config_file = _write_config(tmp_path, _VALID_TOML)
    received_kwargs: list[dict] = []

    def fake_run_backup(profile: object, **kwargs: object) -> None:
        received_kwargs.append(dict(kwargs))

    monkeypatch.setattr("restic_profile.cli.run_backup", fake_run_backup)
    main(["backup", "myapp", "--dry-run", "--config", str(config_file)])

    assert len(received_kwargs) == 1
    assert received_kwargs[0].get("dry_run") is True


# backup — profile not found


def test_backup_nonexistent_profile_exits_1(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """restic-profile backup exits 1 and logs an error for an unknown profile."""
    config_file = _write_config(tmp_path, _VALID_TOML)

    with pytest.raises(SystemExit) as exc_info:
        main(["backup", "nonexistent", "--config", str(config_file)])

    assert exc_info.value.code == 1
    assert "nonexistent" in caplog.text or "not found" in caplog.text.lower()


# backup — missing config


def test_backup_with_missing_config_exits_1(tmp_path: Path) -> None:
    """restic-profile backup exits 1 when the config file does not exist."""
    missing = tmp_path / "no_config.toml"

    with pytest.raises(SystemExit) as exc_info:
        main(["backup", "myapp", "--config", str(missing)])

    assert exc_info.value.code == 1


# backup — run_backup raises ValueError (prune-only profile)


def test_backup_value_error_from_run_backup_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restic-profile backup exits 1 when run_backup raises ValueError."""
    config_file = _write_config(tmp_path, _VALID_TOML)

    def failing_run_backup(profile: object, **kwargs: object) -> None:
        raise ValueError("Profile 'server_prune' has no sources, cannot run backup")

    monkeypatch.setattr("restic_profile.cli.run_backup", failing_run_backup)

    with pytest.raises(SystemExit) as exc_info:
        main(["backup", "server_prune", "--config", str(config_file)])

    assert exc_info.value.code == 1


# forget — mocked run_forget (success)


def test_forget_with_mocked_run_forget_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restic-profile forget exits 0 when run_forget succeeds."""
    config_file = _write_config(tmp_path, _VALID_TOML)
    monkeypatch.setattr("restic_profile.cli.run_forget", lambda *a, **kw: None)

    main(["forget", "server_prune", "--config", str(config_file)])


def test_forget_calls_run_forget_with_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restic-profile forget passes the correct Profile to run_forget."""
    config_file = _write_config(tmp_path, _VALID_TOML)
    received: list[object] = []

    def fake_run_forget(profile: object, **kwargs: object) -> None:
        received.append(profile)

    monkeypatch.setattr("restic_profile.cli.run_forget", fake_run_forget)
    main(["forget", "server_prune", "--config", str(config_file)])

    assert len(received) == 1
    assert getattr(received[0], "name", None) == "server_prune"


def test_forget_dry_run_flag_is_forwarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restic-profile forget --dry-run forwards dry_run=True to run_forget."""
    config_file = _write_config(tmp_path, _VALID_TOML)
    received_kwargs: list[dict] = []

    def fake_run_forget(profile: object, **kwargs: object) -> None:
        received_kwargs.append(dict(kwargs))

    monkeypatch.setattr("restic_profile.cli.run_forget", fake_run_forget)
    main(["forget", "server_prune", "--dry-run", "--config", str(config_file)])

    assert len(received_kwargs) == 1
    assert received_kwargs[0] == {"dry_run": True}


# forget — profile not found


def test_forget_nonexistent_profile_exits_1(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """restic-profile forget exits 1 and logs an error for an unknown profile."""
    config_file = _write_config(tmp_path, _VALID_TOML)

    with pytest.raises(SystemExit) as exc_info:
        main(["forget", "ghost_profile", "--config", str(config_file)])

    assert exc_info.value.code == 1
    assert "ghost_profile" in caplog.text or "not found" in caplog.text.lower()


# forget — missing config


def test_forget_with_missing_config_exits_1(tmp_path: Path) -> None:
    """restic-profile forget exits 1 when the config file does not exist."""
    missing = tmp_path / "no_config.toml"

    with pytest.raises(SystemExit) as exc_info:
        main(["forget", "server_prune", "--config", str(missing)])

    assert exc_info.value.code == 1


# forget — run_forget raises ValueError (no retention policy)


def test_forget_value_error_from_run_forget_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restic-profile forget exits 1 when run_forget raises ValueError."""
    config_file = _write_config(tmp_path, _VALID_TOML)

    def failing_run_forget(profile: object, **kwargs: object) -> None:
        raise ValueError("Profile 'server_prune' has no retention policy")

    monkeypatch.setattr("restic_profile.cli.run_forget", failing_run_forget)

    with pytest.raises(SystemExit) as exc_info:
        main(["forget", "server_prune", "--config", str(config_file)])

    assert exc_info.value.code == 1
