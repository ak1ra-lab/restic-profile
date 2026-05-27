# PYTHON_ARGCOMPLETE_OK
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import argcomplete
from chaos_utils.logging import setup_logger
from pydantic import ValidationError

from .config import load_config
from .runner import run_backup, run_retention

logger = setup_logger(__name__)

DEFAULT_CONFIG = Path("/etc/restic-profile/restic-profile.toml")


def _cmd_backup(args: argparse.Namespace) -> None:
    """Run restic backup (and optional retention) for a named profile."""
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


def _cmd_retention(args: argparse.Namespace) -> None:
    """Run restic forget & prune (retention) for a named profile."""
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
    logger.info("Running retention for profile: %s", args.profile_name)

    try:
        run_retention(profile, dry_run=args.dry_run)
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
        sub_types = []
        if profile.backup:
            sub_types.append("backup")
        if profile.retention:
            sub_types.append("retention")
        sub_type_str = "+".join(sub_types)

        repo_url = (
            profile.resolved_repository.repository
            if profile.resolved_repository
            else "N/A"
        )
        print(f"{name}  type={sub_type_str}  repository={repo_url}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="restic-profile",
        description="Restic backup profile management.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", metavar="<command>")
    subparsers.required = True

    backup_parser = subparsers.add_parser(
        "backup", help="Run restic backup (and optional retention) for a named profile"
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

    retention_parser = subparsers.add_parser(
        "retention",
        aliases=["forget"],
        help="Run restic forget & prune (retention) for a named profile",
    )
    retention_parser.add_argument("profile_name", help="Profile name from config")
    retention_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        metavar="PATH",
        help="Path to TOML config file (default: %(default)s)",
    )
    retention_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Log actions without executing",
    )
    retention_parser.set_defaults(handler=_cmd_retention)

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
