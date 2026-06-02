# PYTHON_ARGCOMPLETE_OK
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import argcomplete
from chaos_utils.logging import setup_logger
from pydantic import ValidationError

from .config import load_config
from .runner import WorkflowError, run_profile

logger = setup_logger(__name__)

DEFAULT_CONFIG = Path("/etc/restic-profile/restic-profile.toml")


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


def _cmd_run(args: argparse.Namespace) -> None:
    """Run the configured workflow for a named profile."""
    profile = _resolve_profile_or_exit(args)
    logger.info("Running configured workflow for profile: %s", args.profile_name)

    try:
        run_profile(profile, dry_run=args.dry_run)
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
        "--check",
        action="store_true",
        default=False,
        help="Validate the TOML config file and exit",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        metavar="PATH",
        help="Path to TOML config file (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Log actions without executing",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for restic-profile."""
    parser = _build_parser()
    argcomplete.autocomplete(parser)
    args = parser.parse_args(argv)

    if args.profile_name and (args.list or args.check):
        parser.error("profile name cannot be combined with --list or --check")

    if args.list:
        _cmd_list(args)
        return

    if args.check:
        _cmd_check(args)
        return

    if not args.profile_name:
        parser.error("provide a profile name or one of --list/--check")

    _cmd_run(args)
