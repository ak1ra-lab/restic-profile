"""Shared pytest fixtures for restic_profile test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from restic_profile import runner as runner_module
from restic_profile.config import HooksConfig, Profile

# Config dict fixtures


@pytest.fixture(autouse=True)
def _reset_runner_state() -> None:
    """Keep restic runner caches isolated per test."""
    runner_module._resolve_restic_executable.cache_clear()
    yield
    runner_module._resolve_restic_executable.cache_clear()


@pytest.fixture
def minimal_config_dict() -> dict:
    """Return a minimal config dict with [global] + one backup profile + one prune-only profile."""
    return {
        "global": {
            "retry_lock": "10m",
        },
        "profiles": {
            "myapp": {
                "repository": "rest:https://backup.example.com/",
                "password": "secret",
                "rest_username": "",
                "rest_password": "",
                "cacert": "",
                "aws_default_region": "",
                "aws_access_key_id": "",
                "aws_secret_access_key": "",
                "sources": ["/home/alice/myapp"],
                "tag": "myapp",
                "exclude_patterns": ["*.log", "node_modules/"],
                "forget": True,
                "keep_last": 0,
                "keep_hourly": 6,
                "keep_daily": 7,
                "keep_weekly": 4,
                "keep_monthly": 3,
                "keep_yearly": 0,
                "on_calendar": "hourly",
                "randomized_delay_sec": "10min",
                "system_user": "root",
                "retry_lock": "",
            },
            "server_prune": {
                "repository": "rest:https://backup.example.com/server",
                "password": "secret2",
                "sources": [],
                "keep_daily": 7,
                "on_calendar": "daily",
                "system_user": "root",
                "retry_lock": "",
            },
        },
    }


# TOML file fixtures


@pytest.fixture
def config_toml_file(tmp_path: Path, minimal_config_dict: dict) -> Path:
    """Write minimal_config_dict to a temporary TOML file and return its Path."""
    toml_content = _dict_to_toml(minimal_config_dict)
    path = tmp_path / "restic-profile.toml"
    path.write_text(toml_content, encoding="utf-8")
    return path


# Profile instance fixtures


@pytest.fixture
def backup_profile(tmp_path: Path) -> Profile:
    """Return a Profile instance configured for backup (has sources)."""
    source_dir = tmp_path / "testdata"
    source_dir.mkdir()

    return Profile(
        name="myapp",
        repository="rest:https://backup.example.com/",
        password="secret",
        sources=[str(source_dir)],
        tag="myapp",
        keep_last=0,
        keep_hourly=6,
        keep_daily=7,
        keep_weekly=4,
        keep_monthly=3,
        keep_yearly=0,
        retry_lock="10m",
    )


@pytest.fixture
def hooks_backup_profile(backup_profile: Profile) -> Profile:
    """Return a backup Profile with all five hook phases populated."""
    backup_profile.hooks = HooksConfig(
        shell="/bin/sh",
        prevalidate=["echo prevalidate"],
        before=["echo before"],
        after=["echo after"],
        success=["echo success"],
        failure=["echo failure"],
    )
    return backup_profile


@pytest.fixture
def prune_profile() -> Profile:
    """Return a Profile instance configured for prune-only (no sources)."""
    return Profile(
        name="server_prune",
        repository="rest:https://backup.example.com/server",
        password="secret2",
        sources=[],
        keep_last=0,
        keep_hourly=0,
        keep_daily=7,
        keep_weekly=4,
        keep_monthly=3,
        keep_yearly=0,
        retry_lock="",
    )


# Internal helpers


def _dict_to_toml(config: dict) -> str:
    """Produce a minimal TOML representation of *config*.

    Handles the [global] + [profiles.*] structure used in restic-profile
    configs; does not need to be a general-purpose serialiser.
    """
    lines: list[str] = []

    for section, value in config.items():
        if section == "profiles":
            for profile_name, profile_cfg in value.items():
                lines.append(f"\n[profiles.{profile_name}]")
                for k, v in profile_cfg.items():
                    lines.append(_toml_kv(k, v))
        elif isinstance(value, dict):
            lines.append(f"\n[{section}]")
            for k, v in value.items():
                lines.append(_toml_kv(k, v))
        else:
            lines.append(_toml_kv(section, value))

    return "\n".join(lines) + "\n"


def _toml_kv(key: str, value: object) -> str:
    """Format a single TOML key = value line."""
    if isinstance(value, bool):
        return f"{key} = {str(value).lower()}"
    if isinstance(value, int):
        return f"{key} = {value}"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'{key} = "{escaped}"'
    if isinstance(value, list):
        items = ", ".join(_toml_inline_value(item) for item in value)
        return f"{key} = [{items}]"
    # Fallback
    return f'{key} = "{value}"'


def _toml_inline_value(value: object) -> str:
    """Format a scalar for use inside a TOML inline array."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return f'"{value}"'
