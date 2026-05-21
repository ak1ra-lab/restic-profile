# PYTHON_ARGCOMPLETE_OK
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import argcomplete
from chaos_utils.logging import setup_logger
from pydantic import ValidationError

from .config import load_config
from .runner import run_backup, run_forget

logger = setup_logger(__name__)

DEFAULT_CONFIG = Path("/etc/restic-profile/restic-profile.toml")


def _cmd_backup(args: argparse.Namespace) -> None:
    """Run restic backup (and optional forget) for a named profile."""
    try:
        cfg = load_config(args.config)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except ValidationError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    if args.profile_name not in cfg.profiles:
        logger.error(
            "Profile %r not found in config %s", args.profile_name, args.config
        )
        sys.exit(1)

    profile = cfg.profiles[args.profile_name]
    logger.info("Running backup for profile: %s", args.profile_name)

    try:
        run_backup(profile, dry_run=args.dry_run)
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)


def _cmd_forget(args: argparse.Namespace) -> None:
    """Run restic forget for a named profile."""
    try:
        cfg = load_config(args.config)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except ValidationError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    if args.profile_name not in cfg.profiles:
        logger.error(
            "Profile %r not found in config %s", args.profile_name, args.config
        )
        sys.exit(1)

    profile = cfg.profiles[args.profile_name]
    logger.info("Running forget for profile: %s", args.profile_name)

    try:
        run_forget(profile, dry_run=args.dry_run)
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)


def _cmd_validate(args: argparse.Namespace) -> None:
    """Validate the TOML config file and print any errors."""
    try:
        load_config(args.config)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except ValidationError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    print("Config is valid.")


def _cmd_list(args: argparse.Namespace) -> None:
    """List all profiles with key settings."""
    try:
        cfg = load_config(args.config)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except ValidationError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    if not cfg.profiles:
        print("No profiles configured.")
        return

    for name, profile in cfg.profiles.items():
        profile_type = "backup" if profile.is_backup else "retention-only"
        print(
            f"{name}  type={profile_type}  repository={profile.repository}"
            f"  on_calendar={profile.on_calendar}"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="restic-profile",
        description="Restic backup profile management.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", metavar="<command>")
    subparsers.required = True

    backup_parser = subparsers.add_parser(
        "backup", help="Run restic backup (and optional forget) for a named profile"
    )
    backup_parser.add_argument("profile_name", help="Profile name from config")
    backup_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        metavar="PATH",
        help="Path to TOML config file (default: %(default)s)",
    )
    backup_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Log actions without executing",
    )
    backup_parser.set_defaults(handler=_cmd_backup)

    forget_parser = subparsers.add_parser(
        "forget",
        help="Run restic forget for a named profile",
    )
    forget_parser.add_argument("profile_name", help="Profile name from config")
    forget_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        metavar="PATH",
        help="Path to TOML config file (default: %(default)s)",
    )
    forget_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Log actions without executing",
    )
    forget_parser.set_defaults(handler=_cmd_forget)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate the TOML config file and print any errors"
    )
    validate_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        metavar="PATH",
        help="Path to TOML config file (default: %(default)s)",
    )
    validate_parser.set_defaults(handler=_cmd_validate)

    list_parser = subparsers.add_parser(
        "list", help="List all profiles with key settings"
    )
    list_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        metavar="PATH",
        help="Path to TOML config file (default: %(default)s)",
    )
    list_parser.set_defaults(handler=_cmd_list)

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for restic-profile."""
    parser = _build_parser()
    argcomplete.autocomplete(parser)
    args = parser.parse_args(argv)
    args.handler(args)
