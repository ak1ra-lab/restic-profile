"""Tests for the deployment_plan Ansible filter plugin.

The filter module is loaded via importlib under a distinct name to avoid
clashing with the ``restic_profile`` src package.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

_FILTER_PATH = (
    Path(__file__).resolve().parents[2] / "plugins" / "filter" / "restic_profile.py"
)


@pytest.fixture(scope="session")
def filters() -> Any:
    """Load the filter plugin module for direct function testing."""
    spec = importlib.util.spec_from_file_location(
        "restic_profile_filters", _FILTER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONFIG_DIR = "/etc/restic-profile"
UNIT_PREFIX = "restic-profile-"


@pytest.fixture
def repositories() -> dict[str, Any]:
    return {
        "r1": {"repository": "rest:https://backup.example.com/", "password": "s1"},
        "r2": {"repository": "s3:https://s3.example.com/bucket", "password": "s2"},
    }


@pytest.fixture
def profiles() -> dict[str, Any]:
    """Profiles covering backup, retention, timer, exclude, disabled, shared repos."""
    return {
        "myapp": {
            "repository_ref": "r1",
            "enabled": True,
            "on_calendar": "daily",
            "backup": {
                "sources": ["/srv/app"],
                "exclude_file_content": "*.log\n*.tmp",
            },
            "retention": {"keep_daily": 7},
        },
        "prune_only": {
            "repository_ref": "r2",
            "enabled": True,
            "on_calendar": "weekly",
            "retention": {"keep_daily": 7},
        },
        "no_timer": {
            "repository_ref": "r1",
            "enabled": True,
            "timer_enabled": False,
            "backup": {"sources": ["/srv/no-timer"]},
        },
        "disabled_app": {
            "repository_ref": "r2",
            "enabled": False,
            "on_calendar": "daily",
            "backup": {"sources": ["/srv/disabled"]},
        },
        "shared_repo": {
            "repository_ref": "r1",
            "enabled": True,
            "on_calendar": "hourly",
            "backup": {"sources": ["/srv/shared"]},
        },
    }


# ---------------------------------------------------------------------------
# service_units
# ---------------------------------------------------------------------------


def test_plan_includes_only_enabled_profiles(
    filters: Any, profiles: dict, repositories: dict
) -> None:
    plan = filters.deployment_plan(profiles, repositories, CONFIG_DIR, UNIT_PREFIX)
    names = [u["profile_name"] for u in plan["service_units"]]
    assert "disabled_app" not in names
    assert sorted(names) == ["myapp", "no_timer", "prune_only", "shared_repo"]


def test_plan_service_unit_fields(
    filters: Any, profiles: dict, repositories: dict
) -> None:
    plan = filters.deployment_plan(profiles, repositories, CONFIG_DIR, UNIT_PREFIX)
    myapp = next(u for u in plan["service_units"] if u["profile_name"] == "myapp")
    assert myapp["unit_name"] == "restic-profile-myapp"
    assert myapp["timer_enabled"] is True
    assert myapp["has_timer"] is True
    assert myapp["profile"] is profiles["myapp"]


def test_plan_has_timer_false_when_timer_enabled_false(
    filters: Any, profiles: dict, repositories: dict
) -> None:
    plan = filters.deployment_plan(profiles, repositories, CONFIG_DIR, UNIT_PREFIX)
    no_timer = next(u for u in plan["service_units"] if u["profile_name"] == "no_timer")
    assert no_timer["timer_enabled"] is False
    assert no_timer["has_timer"] is False


def test_plan_has_timer_false_when_on_calendar_empty(
    filters: Any, profiles: dict, repositories: dict
) -> None:
    plan = filters.deployment_plan(
        {"p": {"repository_ref": "r1", "enabled": True, "on_calendar": ""}},
        repositories,
        CONFIG_DIR,
        UNIT_PREFIX,
    )
    assert plan["service_units"][0]["has_timer"] is False


def test_plan_has_timer_false_when_on_calendar_whitespace(
    filters: Any, profiles: dict, repositories: dict
) -> None:
    plan = filters.deployment_plan(
        {"p": {"repository_ref": "r1", "enabled": True, "on_calendar": "  "}},
        repositories,
        CONFIG_DIR,
        UNIT_PREFIX,
    )
    assert plan["service_units"][0]["has_timer"] is False


# ---------------------------------------------------------------------------
# exclude_files
# ---------------------------------------------------------------------------


def test_plan_exclude_files_only_for_profiles_with_content(
    filters: Any, profiles: dict, repositories: dict
) -> None:
    plan = filters.deployment_plan(profiles, repositories, CONFIG_DIR, UNIT_PREFIX)
    names = [f["profile_name"] for f in plan["exclude_files"]]
    assert names == ["myapp"]
    assert plan["exclude_files"][0]["path"] == (
        "/etc/restic-profile/restic-profile-myapp.exclude"
    )


def test_plan_exclude_files_skips_empty_content(
    filters: Any, repositories: dict
) -> None:
    profiles = {
        "p": {
            "repository_ref": "r1",
            "enabled": True,
            "backup": {"sources": ["/srv"], "exclude_file_content": ""},
        }
    }
    plan = filters.deployment_plan(profiles, repositories, CONFIG_DIR, UNIT_PREFIX)
    assert plan["exclude_files"] == []


def test_plan_exclude_files_skips_profiles_without_backup(
    filters: Any, repositories: dict
) -> None:
    profiles = {
        "p": {
            "repository_ref": "r1",
            "enabled": True,
            "retention": {"keep_daily": 7},
        }
    }
    plan = filters.deployment_plan(profiles, repositories, CONFIG_DIR, UNIT_PREFIX)
    assert plan["exclude_files"] == []


# ---------------------------------------------------------------------------
# env_files (repository_ref de-duplication)
# ---------------------------------------------------------------------------


def test_plan_env_files_deduplicated_by_ref(
    filters: Any, profiles: dict, repositories: dict
) -> None:
    plan = filters.deployment_plan(profiles, repositories, CONFIG_DIR, UNIT_PREFIX)
    # r1 is referenced by myapp, no_timer, shared_repo — should appear once
    # r2 is referenced by prune_only — should appear once
    refs = [f["key"] for f in plan["env_files"]]
    assert refs == ["r1", "r2"]


def test_plan_env_files_include_repo_data_and_path(
    filters: Any, profiles: dict, repositories: dict
) -> None:
    plan = filters.deployment_plan(profiles, repositories, CONFIG_DIR, UNIT_PREFIX)
    r1 = next(f for f in plan["env_files"] if f["key"] == "r1")
    assert r1["value"] == repositories["r1"]
    assert r1["path"] == "/etc/restic-profile/restic-profile-r1.env"


# ---------------------------------------------------------------------------
# expected_* lists (stale-file detection)
# ---------------------------------------------------------------------------


def test_plan_expected_unit_names(
    filters: Any, profiles: dict, repositories: dict
) -> None:
    plan = filters.deployment_plan(profiles, repositories, CONFIG_DIR, UNIT_PREFIX)
    assert sorted(plan["expected_unit_names"]) == [
        "restic-profile-myapp",
        "restic-profile-no_timer",
        "restic-profile-prune_only",
        "restic-profile-shared_repo",
    ]


def test_plan_expected_exclude_paths(
    filters: Any, profiles: dict, repositories: dict
) -> None:
    plan = filters.deployment_plan(profiles, repositories, CONFIG_DIR, UNIT_PREFIX)
    assert plan["expected_exclude_paths"] == [
        "/etc/restic-profile/restic-profile-myapp.exclude"
    ]


def test_plan_expected_env_paths(
    filters: Any, profiles: dict, repositories: dict
) -> None:
    plan = filters.deployment_plan(profiles, repositories, CONFIG_DIR, UNIT_PREFIX)
    assert plan["expected_env_paths"] == [
        "/etc/restic-profile/restic-profile-r1.env",
        "/etc/restic-profile/restic-profile-r2.env",
    ]


# ---------------------------------------------------------------------------
# profile_names filtering (for future per-target use)
# ---------------------------------------------------------------------------


def test_plan_profile_names_filter(
    filters: Any, profiles: dict, repositories: dict
) -> None:
    plan = filters.deployment_plan(
        profiles,
        repositories,
        CONFIG_DIR,
        UNIT_PREFIX,
        profile_names=["myapp", "shared_repo"],
    )
    names = [u["profile_name"] for u in plan["service_units"]]
    assert sorted(names) == ["myapp", "shared_repo"]


def test_plan_profile_names_excludes_disabled_even_if_listed(
    filters: Any, profiles: dict, repositories: dict
) -> None:
    plan = filters.deployment_plan(
        profiles, repositories, CONFIG_DIR, UNIT_PREFIX, profile_names=["disabled_app"]
    )
    assert plan["service_units"] == []


# ---------------------------------------------------------------------------
# edge cases
# ---------------------------------------------------------------------------


def test_plan_empty_profiles(filters: Any, repositories: dict) -> None:
    plan = filters.deployment_plan({}, repositories, CONFIG_DIR, UNIT_PREFIX)
    assert plan["service_units"] == []
    assert plan["exclude_files"] == []
    assert plan["env_files"] == []
    assert plan["expected_unit_names"] == []
    assert plan["expected_exclude_paths"] == []
    assert plan["expected_env_paths"] == []


def test_plan_all_profiles_disabled(filters: Any, repositories: dict) -> None:
    profiles = {
        "p1": {"repository_ref": "r1", "enabled": False},
        "p2": {"repository_ref": "r1", "enabled": False},
    }
    plan = filters.deployment_plan(profiles, repositories, CONFIG_DIR, UNIT_PREFIX)
    assert plan["service_units"] == []
    assert plan["env_files"] == []
