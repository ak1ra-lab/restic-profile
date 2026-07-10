"""Deployment-plan filter for the ak1ra_lab.restic_profile collection.

``deployment_plan`` turns the user's ``restic_profile_profiles`` and
``restic_profile_repositories`` dicts into a single structured plan that the
role tasks consume directly — no more inline Jinja loops in YAML.

The filter is pure Python and does not import Ansible at runtime (a fallback
``AnsibleFilterError`` is defined for pytest).  It is deliberately **scope
agnostic**: the caller passes the filesystem paths (``config_dir``,
``unit_prefix``) and the filter figures out which files should exist there.
This keeps the filter reusable when per-profile user scope is layered on top.
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


class FilterModule:
    """Ansible filter plugin."""

    def filters(self) -> dict[str, Any]:
        return {"deployment_plan": deployment_plan}
