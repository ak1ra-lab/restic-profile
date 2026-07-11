# PYTHON_ARGCOMPLETE_OK
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import argcomplete
from chaos_utils.logging import setup_logger
from pydantic import ValidationError

from .config import load_config
from .runner import WorkflowError, run_profile, run_unlock

logger = setup_logger(__name__)

DEFAULT_CONFIG = Path("/etc/restic-profile/restic-profile.toml")


def _resolve_config_path() -> Path:
    """Return the default config path using XDG search-path precedence.

    1. ``RESTIC_PROFILE_CONFIG`` env var (explicit override, no existence check).
    2. ``$XDG_CONFIG_HOME/restic-profile/restic-profile.toml`` (falls back
       to ``~/.config`` when ``XDG_CONFIG_HOME`` is unset; only used when
       the file exists).
    3. ``/etc/restic-profile/restic-profile.toml`` (always the final fallback).
    """
    env_config = os.environ.get("RESTIC_PROFILE_CONFIG")
    if env_config:
        return Path(env_config)

    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    user_config = Path(xdg_config_home) / "restic-profile" / "restic-profile.toml"
    if user_config.exists():
        return user_config

    return DEFAULT_CONFIG


def _load_config_or_exit(config_path: Path):
    """Return the parsed config or exit with a logged error."""
    try:
        return load_config(config_path)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except (ValidationError, ValueError) as exc:
        logger.error("%s", exc)
        sys.exit(1)


def _resolve_profile_or_exit(args: argparse.Namespace):
    """Return the named profile from *args* or exit with a logged error."""
    cfg = _load_config_or_exit(args.config)

    if not args.profile_name:
        raise ValueError("profile_name is required")

    if args.profile_name not in cfg.profiles:
        logger.error(
            "Profile %r not found in config %s", args.profile_name, args.config
        )
        sys.exit(1)

    return cfg.profiles[args.profile_name]


def _profile_type(profile) -> str:
    """Return a user-facing type label for *profile*."""
    sub_types = []
    if profile.backup:
        sub_types.append("backup")
    if profile.retention:
        sub_types.append("retention")
    return "+".join(sub_types)


def _cmd_run(
    args: argparse.Namespace,
    *,
    is_dry_run: bool = False,
    force_notify: bool = False,
) -> None:
    """Run the configured workflow for a named profile."""
    profile = _resolve_profile_or_exit(args)
    logger.info("Running configured workflow for profile: %s", args.profile_name)

    try:
        run_profile(profile, dry_run=is_dry_run, force_notify=force_notify)
    except (ValueError, WorkflowError) as exc:
        logger.error("%s", exc)
        sys.exit(1)


def _cmd_unlock(args: argparse.Namespace, *, is_dry_run: bool = False) -> None:
    """Run restic unlock on the named profile's repository."""
    profile = _resolve_profile_or_exit(args)
    logger.info("Unlocking repository for profile: %s", args.profile_name)

    try:
        run_unlock(profile, dry_run=is_dry_run)
    except (ValueError, WorkflowError) as exc:
        logger.error("%s", exc)
        sys.exit(1)


def _cmd_check(args: argparse.Namespace) -> None:
    """Validate the TOML config file and print any errors."""
    _load_config_or_exit(args.config)

    print("Config is valid.")


def _cmd_list(args: argparse.Namespace) -> None:
    """List all profiles with key settings."""
    cfg = _load_config_or_exit(args.config)

    if not cfg.profiles:
        print("No profiles configured.")
        return

    for name, profile in cfg.profiles.items():
        repo_url = (
            profile.resolved_repository.repository
            if profile.resolved_repository
            else "N/A"
        )
        schedule = profile.on_calendar or "manual"
        print(
            f"{name}  type={_profile_type(profile)}  "
            f"schedule={schedule}  repository={repo_url}"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="restic-profile",
        description="Run configured restic profile workflows.",
    )

    parser.add_argument(
        "profile_name",
        nargs="?",
        help="Profile name from config to execute",
    )
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "-l",
        "--list",
        action="store_true",
        default=False,
        help="List all configured profiles",
    )
    action_group.add_argument(
        "-C",
        "--check",
        action="store_true",
        default=False,
        help="Validate the TOML config file and exit",
    )
    action_group.add_argument(
        "-U",
        "--unlock",
        action="store_true",
        default=False,
        help="Remove stale restic locks for the named profile",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to TOML config file"
        " (searches $XDG_CONFIG_HOME then /etc/restic-profile if not set)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        nargs="?",
        const="all",
        default=None,
        choices=["all", "notify"],
        help="Dry-run mode: 'all' logs actions without executing (no-op), "
        "'notify' dry-runs everything but sends the success notification for "
        "real. When -n is used without a value, defaults to 'all'.",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for restic-profile."""
    parser = _build_parser()
    argcomplete.autocomplete(parser)
    args = parser.parse_args(argv)

    if args.config is None:
        args.config = _resolve_config_path()

    if args.profile_name and (args.list or args.check or args.unlock):
        parser.error(
            "profile name cannot be combined with --list, --check, or --unlock"
        )

    if args.list:
        _cmd_list(args)
        return

    if args.check:
        _cmd_check(args)
        return

    if args.unlock:
        if not args.profile_name:
            parser.error("--unlock requires a profile name")
        _cmd_unlock(args, is_dry_run=args.dry_run == "all")
        return

    if not args.profile_name:
        parser.error(
            "provide a profile name or one of --list/--check/--unlock/--dry-run"
        )

    if args.dry_run == "notify":
        _cmd_run(args, is_dry_run=True, force_notify=True)
    else:
        _cmd_run(args, is_dry_run=args.dry_run == "all")
