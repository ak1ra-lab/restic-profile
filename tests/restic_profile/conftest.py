"""Shared pytest fixtures for restic_profile test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from restic_profile import runner as runner_module
from restic_profile.config import (
    BackupConfig,
    HooksConfig,
    Profile,
    Repository,
    RetentionConfig,
)


@pytest.fixture(autouse=True)
def _reset_runner_state() -> None:
    """Keep restic runner caches isolated per test."""
    runner_module._resolve_restic_executable.cache_clear()
    yield
    runner_module._resolve_restic_executable.cache_clear()


@pytest.fixture
def minimal_config_dict() -> dict:
    """Return a minimal config dict with [global] + [repositories] + [profiles]."""
    return {
        "global": {
            "retry_lock": "10m",
        },
        "repositories": {
            "r1": {
                "repository": "rest:https://backup.example.com/",
                "password": "secret",
            },
            "r2": {
                "repository": "rest:https://backup.example.com/server",
                "password": "secret2",
            },
        },
        "profiles": {
            "myapp": {
                "repository_ref": "r1",
                "tag": "myapp",
                "on_calendar": "hourly",
                "randomized_delay_sec": "10min",
                "retry_lock": "",
                "backup": {
                    "sources": ["/home/alice/myapp"],
                    "exclude_patterns": ["*.log", "node_modules/"],
                },
                "retention": {
                    "keep_last": 0,
                    "keep_hourly": 6,
                    "keep_daily": 7,
                    "keep_weekly": 4,
                    "keep_monthly": 3,
                    "keep_yearly": 0,
                },
            },
            "server_prune": {
                "repository_ref": "r2",
                "on_calendar": "daily",
                "retry_lock": "",
                "retention": {
                    "keep_daily": 7,
                },
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

    repo = Repository(
        name="r1",
        repository="rest:https://backup.example.com/",
        password="secret",
    )

    return Profile(
        name="myapp",
        repository_ref="r1",
        tag="myapp",
        retry_lock="10m",
        resolved_repository=repo,
        backup=BackupConfig(
            sources=[str(source_dir)],
        ),
        retention=RetentionConfig(
            keep_last=0,
            keep_hourly=6,
            keep_daily=7,
            keep_weekly=4,
            keep_monthly=3,
            keep_yearly=0,
        ),
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
    repo = Repository(
        name="r2",
        repository="rest:https://backup.example.com/server",
        password="secret2",
    )

    return Profile(
        name="server_prune",
        repository_ref="r2",
        resolved_repository=repo,
        retention=RetentionConfig(
            keep_last=0,
            keep_hourly=0,
            keep_daily=7,
            keep_weekly=4,
            keep_monthly=3,
            keep_yearly=0,
        ),
    )


# Internal helpers


def _dict_to_toml(config: dict) -> str:
    """Produce a minimal TOML representation of *config*.

    Handles the [global] + [repositories.*] + [profiles.*] structure used in restic-profile
    configs; does not need to be a general-purpose serialiser.
    """
    lines: list[str] = []

    for section, value in config.items():
        if section == "repositories":
            for r_name, r_cfg in value.items():
                lines.append(f"\n[repositories.{r_name}]")
                for k, v in r_cfg.items():
                    lines.append(_toml_kv(k, v))
        elif section == "profiles":
            for p_name, p_cfg in value.items():
                lines.append(f"\n[profiles.{p_name}]")
                for k, v in p_cfg.items():
                    if not isinstance(v, dict):
                        lines.append(_toml_kv(k, v))

                # Render nested sub-tables
                for k, v in p_cfg.items():
                    if isinstance(v, dict):
                        lines.append(f"\n[profiles.{p_name}.{k}]")
                        for sub_k, sub_v in v.items():
                            lines.append(_toml_kv(sub_k, sub_v))
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
