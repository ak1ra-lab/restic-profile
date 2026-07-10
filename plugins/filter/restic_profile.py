"""Deployment-plan and deployment-targets filters for the
ak1ra_lab.restic_profile collection.

``deployment_plan`` turns the user's ``restic_profile_profiles`` and
``restic_profile_repositories`` dicts into a single structured plan that the
role tasks consume directly — no more inline Jinja loops in YAML.

``deployment_targets`` groups enabled profiles by ``(scope, user)`` and
computes the per-target filesystem paths (config_dir, unit_dir, ownership,
etc.) so the role can loop over targets and call ``deployment_plan`` once
per target.

Both filters are pure Python and do not import Ansible at runtime (a fallback
``AnsibleFilterError`` is defined for pytest).
"""

from __future__ import annotations

import posixpath
from typing import Any

try:  # pragma: no cover - only inside Ansible runtime
    from ansible.errors import AnsibleFilterError  # ty: ignore[unresolved-import]
except ImportError:  # pragma: no cover - pytest without Ansible

    class AnsibleFilterError(Exception):
        """Stand-in for ansible.errors.AnsibleFilterError."""


def _truthy(value: Any, default: bool = True) -> bool:
    """Return a bool for *value*, treating missing/None as *default*."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "on", "1"}:
            return True
        if lowered in {"false", "no", "off", "0"}:
            return False
        return default
    return bool(value)


def _join(*parts: str) -> str:
    """Join path components with forward slashes (POSIX, controller-safe)."""
    return posixpath.join(*[p for p in parts if p != ""])


def deployment_plan(
    profiles: dict[str, Any],
    repositories: dict[str, Any],
    config_dir: str,
    unit_prefix: str,
    profile_names: list[str] | None = None,
) -> dict[str, Any]:
    """Compute the deployment plan from profile and repository definitions.

    Parameters
    ----------
    profiles:
        The ``restic_profile_profiles`` dict — each key is a profile name,
        each value is the profile configuration dict.
    repositories:
        The ``restic_profile_repositories`` dict — each key is a repository
        reference name, each value is the repository credentials dict.
    config_dir:
        Directory where exclude files and env files live
        (e.g. ``/etc/restic-profile``).
    unit_prefix:
        Prefix for systemd unit names (e.g. ``restic-profile-``).
    profile_names:
        Optional restriction — when given, only profiles whose names appear
        in this list are included in the plan.  Used for per-target plans
        when user scope is layered on top.  Defaults to all profiles.

    Returns
    -------
    dict with keys:
        ``service_units`` — list of ``{profile_name, profile, unit_name,
        timer_enabled, has_timer}``.  ``has_timer`` is ``True`` only when
        ``timer_enabled`` is truthy **and** ``on_calendar`` is non-empty.
        ``exclude_files`` — list of ``{profile_name, path}`` for every
        enabled profile that defines ``backup.exclude_file_content``.
        ``env_files`` — list of ``{key, value, path}`` for each unique
        ``repository_ref`` referenced by enabled profiles, de-duplicated
        in first-seen order.
        ``expected_unit_names`` — list of unit base names (without
        ``.service``/``.timer`` suffix); used for stale-file detection.
        ``expected_exclude_paths`` — list of absolute paths; same purpose.
        ``expected_env_paths`` — list of absolute paths; same purpose.
    """
    plan: dict[str, Any] = {
        "service_units": [],
        "exclude_files": [],
        "env_files": [],
        "expected_unit_names": [],
        "expected_exclude_paths": [],
        "expected_env_paths": [],
    }

    seen_refs: set[str] = set()

    for pname, profile in profiles.items():
        if profile_names is not None and pname not in profile_names:
            continue
        if not _truthy(profile.get("enabled"), default=True):
            continue

        # --- service unit descriptor ---
        timer_enabled = _truthy(profile.get("timer_enabled"), default=True)
        on_calendar = str(profile.get("on_calendar", "")).strip()
        has_timer = timer_enabled and on_calendar != ""
        unit_name = f"{unit_prefix}{pname}"

        plan["service_units"].append(
            {
                "profile_name": pname,
                "profile": profile,
                "unit_name": unit_name,
                "timer_enabled": timer_enabled,
                "has_timer": has_timer,
            }
        )
        plan["expected_unit_names"].append(unit_name)

        # --- exclude file (only when backup.exclude_file_content is non-empty) ---
        backup = profile.get("backup")
        if isinstance(backup, dict):
            content = backup.get("exclude_file_content", "")
            if isinstance(content, str) and content:
                exclude_path = _join(config_dir, f"restic-profile-{pname}.exclude")
                plan["exclude_files"].append(
                    {
                        "profile_name": pname,
                        "profile": profile,
                        "path": exclude_path,
                    }
                )
                plan["expected_exclude_paths"].append(exclude_path)

        # --- env file (one per unique repository_ref) ---
        ref = str(profile.get("repository_ref", ""))
        if ref and ref not in seen_refs:
            seen_refs.add(ref)
            env_path = _join(config_dir, f"restic-profile-{ref}.env")
            plan["env_files"].append(
                {
                    "key": ref,
                    "value": repositories.get(ref),
                    "path": env_path,
                }
            )
            plan["expected_env_paths"].append(env_path)

    return plan


# ---------------------------------------------------------------------------
# Deployment targets — group profiles by (scope, user) and compute paths
# ---------------------------------------------------------------------------

_SYSTEM_CONFIG_DIR = "/etc/restic-profile"
_SYSTEM_UNIT_DIR = "/etc/systemd/system"
_SYSTEM_INSTALL_TARGET = "multi-user.target"
_USER_INSTALL_TARGET = "default.target"
_CONFIG_FILENAME = "restic-profile.toml"
_HOOKS_DIRNAME = "hooks.d"
_USER_CONFIG_SUBDIR = ".config/restic-profile"
_USER_STATE_SUBDIR = ".local/share/restic-profile"
_USER_UNIT_SUBDIR = ".config/systemd/user"


def _build_target(
    scope: str,
    user: str,
    profile_names: list[str],
    home: str,
    uid: int | str,
    system_state_dir: str,
) -> dict[str, Any]:
    """Construct a deployment-target descriptor with all filesystem paths.

    Centralising this eliminates the duplicated dict literal that would
    otherwise appear in both the target-computation and orphan-fallback paths.
    """
    is_user = scope == "user"
    if is_user:
        config_dir = _join(home, _USER_CONFIG_SUBDIR)
        state_dir = _join(home, _USER_STATE_SUBDIR)
        unit_dir = _join(home, _USER_UNIT_SUBDIR)
        install_target = _USER_INSTALL_TARGET
        file_owner = user
        file_group = user
        file_mode_secret = "0600"
    else:
        config_dir = _SYSTEM_CONFIG_DIR
        state_dir = system_state_dir
        unit_dir = _SYSTEM_UNIT_DIR
        install_target = _SYSTEM_INSTALL_TARGET
        file_owner = "root"
        file_group = "root"
        file_mode_secret = "0640"

    return {
        "key": f"{scope}:{user}",
        "scope": scope,
        "user": user,
        "profile_names": profile_names,
        "is_user_scope": is_user,
        "home": home,
        "uid": uid,
        "file_owner": file_owner,
        "file_group": file_group,
        "file_mode_secret": file_mode_secret,
        "config_dir": config_dir,
        "config_file": _join(config_dir, _CONFIG_FILENAME),
        "hooks_dir": _join(config_dir, _HOOKS_DIRNAME),
        "state_dir": state_dir,
        "unit_dir": unit_dir,
        "install_target": install_target,
        "scope_param": scope,
    }


def _group_profiles_by_target(
    profiles: dict[str, Any],
    default_user: str,
) -> list[dict[str, Any]]:
    """Group enabled profiles into raw ``{scope, user, profile_names}`` buckets."""
    buckets: dict[str, dict[str, Any]] = {}
    for pname, profile in profiles.items():
        if not _truthy(profile.get("enabled"), default=True):
            continue
        scope = str(profile.get("systemd_scope", "system"))
        if scope == "user":
            user = str(profile.get("systemd_user", default_user))
        else:
            user = str(profile.get("systemd_user", "root"))
        key = f"{scope}:{user}"
        bucket: dict[str, Any] | None = buckets.get(key)
        if bucket is None:
            bucket = {"scope": scope, "user": user, "profile_names": []}
            buckets[key] = bucket
        bucket["profile_names"].append(pname)
    return list(buckets.values())


def user_scope_users(profiles: dict[str, Any], default_user: str) -> list[str]:
    """Return unique user-scope usernames that need ``getent passwd`` lookups.

    Preserves first-seen order so the getent loop is deterministic.
    """
    seen: set[str] = set()
    users: list[str] = []
    for raw in _group_profiles_by_target(profiles, default_user):
        if raw["scope"] == "user" and raw["user"] not in seen:
            seen.add(raw["user"])
            users.append(raw["user"])
    return users


def deployment_targets(
    profiles: dict[str, Any],
    default_user: str,
    user_passwd: dict[str, Any] | None,
    system_state_dir: str,
) -> list[dict[str, Any]]:
    """Group enabled profiles into deployment targets with full path metadata.

    Each target is a ``(scope, user)`` pair.  System-scope profiles all go to
    the ``system:root`` target.  User-scope profiles go to ``user:<username>``.

    Parameters
    ----------
    profiles:
        The ``restic_profile_profiles`` dict.
    default_user:
        Fallback username for user-scope profiles that don't specify
        ``systemd_user`` (typically ``restic_profile_user``).
    user_passwd:
        ``getent passwd`` result (``ansible_facts.getent_passwd``).
        Used to resolve ``home`` and ``uid`` for user-scope targets.
        A missing entry raises ``AnsibleFilterError``.
    system_state_dir:
        State directory for system-scope targets
        (typically ``restic_profile_state_dir``).

    Returns
    -------
    list of target dicts, each with keys: ``key``, ``scope``, ``user``,
    ``profile_names``, ``is_user_scope``, ``home``, ``uid``,
    ``file_owner``, ``file_group``, ``file_mode_secret``, ``config_dir``,
    ``config_file``, ``hooks_dir``, ``state_dir``, ``unit_dir``,
    ``install_target``, ``scope_param``.
    """
    passwd = user_passwd or {}
    targets: list[dict[str, Any]] = []
    for raw in _group_profiles_by_target(profiles, default_user):
        scope = raw["scope"]
        user = raw["user"]
        if scope == "user":
            entry = passwd.get(user)
            if entry is None:
                raise AnsibleFilterError(
                    "Target user '{0}' (required by profiles: {1}) not found"
                    " on this host.".format(user, ", ".join(raw["profile_names"]))
                )
            home = str(entry[4]) if len(entry) > 4 else ""
            uid: int | str = int(entry[1]) if len(entry) > 1 else ""
        else:
            home = ""
            uid = ""
        targets.append(
            _build_target(
                scope=scope,
                user=user,
                profile_names=raw["profile_names"],
                home=home,
                uid=uid,
                system_state_dir=system_state_dir,
            )
        )
    return targets


def orphan_targets(
    current_targets: list[dict[str, Any]],
    registered_targets: list[dict[str, Any]],
    system_leftover_count: int,
    system_state_dir: str,
) -> list[dict[str, Any]]:
    """Compute deployment targets that should be torn down.

    A registered target is orphaned when its key is no longer among
    *current_targets*.  When leftover system-scope unit files are detected
    on disk (``system_leftover_count > 0``) and ``system:root`` is not a
    current target, a synthetic ``system:root`` fallback is appended so
    those stray units get cleaned up.  Duplicate keys are de-duplicated.

    Parameters
    ----------
    current_targets:
        Targets computed by ``deployment_targets`` for this run.
    registered_targets:
        Targets persisted from the previous run (from the registry file).
    system_leftover_count:
        Number of leftover system-scope unit files found on disk
        (``find.matched`` count under ``/etc/systemd/system``).
    system_state_dir:
        State directory for system-scope targets — needed to construct
        the synthetic ``system:root`` fallback.
    """
    current_keys = {t["key"] for t in current_targets}
    candidates: list[dict[str, Any]] = list(registered_targets or [])
    if system_leftover_count > 0 and "system:root" not in current_keys:
        candidates.append(
            _build_target(
                scope="system",
                user="root",
                profile_names=[],
                home="",
                uid="",
                system_state_dir=system_state_dir,
            )
        )

    seen: set[str] = set()
    orphans: list[dict[str, Any]] = []
    for target in candidates:
        key = target["key"]
        if key in current_keys or key in seen:
            continue
        seen.add(key)
        orphans.append(target)
    return orphans


class FilterModule:
    """Ansible filter plugin."""

    def filters(self) -> dict[str, Any]:
        return {
            "deployment_plan": deployment_plan,
            "deployment_targets": deployment_targets,
            "orphan_targets": orphan_targets,
            "user_scope_users": user_scope_users,
        }
