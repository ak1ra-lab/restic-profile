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
    assert plan["exclude_files"][0]["profile"] is profiles["myapp"]


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


# ===========================================================================
# deployment_targets + orphan_targets + user_scope_users
# ===========================================================================

SYSTEM_STATE_DIR = "/var/lib/restic-profile"


@pytest.fixture
def scope_profiles() -> dict[str, Any]:
    """Profiles spanning system scope, user scope, and disabled."""
    return {
        "sysapp": {
            "repository_ref": "r1",
            "enabled": True,
            "on_calendar": "daily",
            "backup": {"sources": ["/srv/app"]},
        },
        "disabled_app": {
            "repository_ref": "r1",
            "enabled": False,
            "systemd_scope": "user",
            "systemd_user": "alice",
        },
        "userapp": {
            "repository_ref": "r2",
            "enabled": True,
            "systemd_scope": "user",
            "systemd_user": "alice",
            "on_calendar": "hourly",
            "backup": {"sources": ["/home/alice/data"]},
        },
        "userapp2": {
            "repository_ref": "r1",
            "enabled": True,
            "systemd_scope": "user",
            "systemd_user": "alice",
            "on_calendar": "",
            "timer_enabled": False,
        },
        "userbob": {
            "repository_ref": "r2",
            "enabled": True,
            "systemd_scope": "user",
            "systemd_user": "bob",
            "on_calendar": "weekly",
        },
    }


@pytest.fixture
def passwd() -> dict[str, list[str]]:
    return {
        "alice": ["alice", "1001", "1001", "Alice", "/home/alice", "/bin/bash"],
        "bob": ["bob", "1002", "1002", "Bob", "/home/bob", "/bin/bash"],
    }


# --- user_scope_users ---


def test_user_scope_users_unique_ordered(filters: Any, scope_profiles: dict) -> None:
    assert filters.user_scope_users(scope_profiles, "ansible") == ["alice", "bob"]


def test_user_scope_users_excludes_disabled(filters: Any, scope_profiles: dict) -> None:
    profiles = {
        "p": {
            "repository_ref": "r1",
            "enabled": False,
            "systemd_scope": "user",
            "systemd_user": "alice",
        }
    }
    assert filters.user_scope_users(profiles, "ansible") == []


def test_user_scope_users_empty_when_no_user_scope(filters: Any) -> None:
    assert filters.user_scope_users({"p": {"enabled": True}}, "ansible") == []


# --- deployment_targets: system scope ---


def test_targets_system_scope_paths(
    filters: Any, scope_profiles: dict, passwd: dict
) -> None:
    targets = filters.deployment_targets(
        scope_profiles, "ansible", passwd, SYSTEM_STATE_DIR
    )
    sys_root = [t for t in targets if t["key"] == "system:root"]
    assert len(sys_root) == 1
    t = sys_root[0]
    assert t["scope"] == "system"
    assert t["is_user_scope"] is False
    assert t["home"] == ""
    assert t["uid"] == ""
    assert t["config_dir"] == "/etc/restic-profile"
    assert t["config_file"] == "/etc/restic-profile/restic-profile.toml"
    assert t["hooks_dir"] == "/etc/restic-profile/hooks.d"
    assert t["state_dir"] == SYSTEM_STATE_DIR
    assert t["unit_dir"] == "/etc/systemd/system"
    assert t["install_target"] == "multi-user.target"
    assert t["file_owner"] == "root"
    assert t["file_group"] == "root"
    assert t["file_mode_secret"] == "0640"
    assert t["scope_param"] == "system"
    assert "sysapp" in t["profile_names"]


# --- deployment_targets: user scope ---


def test_targets_user_scope_xdg_paths(
    filters: Any, scope_profiles: dict, passwd: dict
) -> None:
    targets = filters.deployment_targets(
        scope_profiles, "ansible", passwd, SYSTEM_STATE_DIR
    )
    alice = [t for t in targets if t["key"] == "user:alice"][0]
    assert alice["is_user_scope"] is True
    assert alice["home"] == "/home/alice"
    assert alice["uid"] == 1001
    assert alice["config_dir"] == "/home/alice/.config/restic-profile"
    assert alice["config_file"] == (
        "/home/alice/.config/restic-profile/restic-profile.toml"
    )
    assert alice["hooks_dir"] == "/home/alice/.config/restic-profile/hooks.d"
    assert alice["state_dir"] == "/home/alice/.local/share/restic-profile"
    assert alice["unit_dir"] == "/home/alice/.config/systemd/user"
    assert alice["install_target"] == "default.target"
    assert alice["file_owner"] == "alice"
    assert alice["file_group"] == "alice"
    assert alice["file_mode_secret"] == "0600"
    assert alice["scope_param"] == "user"
    assert sorted(alice["profile_names"]) == ["userapp", "userapp2"]


def test_targets_groups_by_scope_user(
    filters: Any, scope_profiles: dict, passwd: dict
) -> None:
    targets = filters.deployment_targets(
        scope_profiles, "ansible", passwd, SYSTEM_STATE_DIR
    )
    keys = [t["key"] for t in targets]
    assert "system:root" in keys
    assert "user:alice" in keys
    assert "user:bob" in keys


def test_targets_missing_user_raises(filters: Any, scope_profiles: dict) -> None:
    with pytest.raises(filters.AnsibleFilterError, match="not found"):
        filters.deployment_targets(scope_profiles, "ansible", {}, SYSTEM_STATE_DIR)


def test_targets_default_user_for_user_scope(filters: Any, passwd: dict) -> None:
    profiles = {
        "p": {
            "repository_ref": "r1",
            "enabled": True,
            "systemd_scope": "user",
        }
    }
    targets = filters.deployment_targets(profiles, "alice", passwd, SYSTEM_STATE_DIR)
    assert targets[0]["user"] == "alice"
    assert targets[0]["home"] == "/home/alice"


def test_targets_empty_profiles(filters: Any) -> None:
    assert filters.deployment_targets({}, "ansible", {}, SYSTEM_STATE_DIR) == []


# --- orphan_targets ---


def test_orphans_basic(filters: Any) -> None:
    current = [{"key": "system:root"}, {"key": "user:alice"}]
    registered = [
        {"key": "system:root"},
        {"key": "user:bob"},
    ]
    orphans = filters.orphan_targets(current, registered, 0, SYSTEM_STATE_DIR)
    assert [o["key"] for o in orphans] == ["user:bob"]


def test_orphans_system_root_fallback(filters: Any) -> None:
    current = [{"key": "user:alice"}]
    registered = [{"key": "user:bob"}]
    orphans = filters.orphan_targets(current, registered, 2, SYSTEM_STATE_DIR)
    keys = [o["key"] for o in orphans]
    assert "system:root" in keys
    sys_root = [o for o in orphans if o["key"] == "system:root"][0]
    assert sys_root["unit_dir"] == "/etc/systemd/system"
    assert sys_root["profile_names"] == []


def test_orphans_no_fallback_when_system_root_current(filters: Any) -> None:
    orphans = filters.orphan_targets([{"key": "system:root"}], [], 5, SYSTEM_STATE_DIR)
    assert orphans == []


def test_orphans_dedup(filters: Any) -> None:
    orphans = filters.orphan_targets(
        [],
        [{"key": "user:alice"}, {"key": "user:alice"}],
        0,
        SYSTEM_STATE_DIR,
    )
    assert len(orphans) == 1


def test_orphans_empty(filters: Any) -> None:
    assert filters.orphan_targets([], [], 0, SYSTEM_STATE_DIR) == []
