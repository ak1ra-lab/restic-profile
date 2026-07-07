from __future__ import annotations

import logging
import os
import pwd
import shutil
import socket
import subprocess
from functools import lru_cache
from pathlib import Path

from .config import Profile

logger = logging.getLogger(__name__)

_COMMON_RESTIC_PATHS = ("/usr/local/bin/restic", "/usr/bin/restic")


class _CommandError(Exception):
    """Raised when a subprocess command exits with a non-zero exit code."""

    def __init__(
        self,
        cmd: list[str],
        returncode: int,
        *,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.cmd = list(cmd)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"Command failed (exit {returncode}): {' '.join(cmd)}")


class WorkflowError(Exception):
    """Raised when a backup/retention workflow cannot continue."""


def build_env(profile: Profile) -> dict[str, str]:
    """Build the environment dict for a restic subprocess.

    Starts from a copy of ``os.environ`` so that PATH and other inherited
    variables are preserved.  Credentials are injected via env vars only —
    never written to disk.
    """
    env = os.environ.copy()

    if not env.get("HOME"):
        try:
            env["HOME"] = pwd.getpwuid(os.getuid()).pw_dir
        except KeyError:
            pass

    if not env.get("XDG_CACHE_HOME") and env.get("HOME"):
        env["XDG_CACHE_HOME"] = str(Path(env["HOME"]) / ".cache")

    repo = profile.resolved_repository
    if not repo:
        raise ValueError(f"Profile {profile.name!r} has no resolved repository")

    env["RESTIC_REPOSITORY"] = repo.repository
    env["RESTIC_PASSWORD"] = repo.password

    if repo.rest_username:
        env["RESTIC_REST_USERNAME"] = repo.rest_username
        env["RESTIC_REST_PASSWORD"] = repo.rest_password

    if repo.cacert:
        env["RESTIC_CACERT"] = repo.cacert

    if repo.aws_access_key_id:
        env["AWS_ACCESS_KEY_ID"] = repo.aws_access_key_id
        env["AWS_SECRET_ACCESS_KEY"] = repo.aws_secret_access_key
        if repo.aws_default_region:
            env["AWS_DEFAULT_REGION"] = repo.aws_default_region

    if repo.google_project_id:
        env["GOOGLE_PROJECT_ID"] = repo.google_project_id
        # google_access_token takes precedence — when set it disables all other
        # GCS auth mechanisms (service account key, ADC, etc.).
        if repo.google_access_token:
            env["GOOGLE_ACCESS_TOKEN"] = repo.google_access_token
        elif repo.google_application_credentials:
            env["GOOGLE_APPLICATION_CREDENTIALS"] = repo.google_application_credentials

    if repo.env:
        for k, v in repo.env.items():
            if k in env:
                logger.debug(
                    "Repository %r env %r=%r overrides existing value %r",
                    repo.name,
                    k,
                    v,
                    env[k],
                )
            env[k] = v

    return env


@lru_cache(maxsize=32)
def _resolve_restic_executable(configured: str) -> str:
    """Resolve a configured restic command to the executable path to run."""
    candidate = configured.strip() or "restic"
    expanded = Path(candidate).expanduser()

    if expanded.is_absolute():
        return str(expanded)

    if "/" in candidate:
        return str(expanded.resolve(strict=False))

    if resolved := shutil.which(candidate):
        return resolved

    if candidate == "restic":
        for fallback in _COMMON_RESTIC_PATHS:
            if Path(fallback).exists():
                return fallback

    return candidate


def _restic_executable(profile: Profile) -> str:
    """Return the resolved restic executable for *profile*."""
    return _resolve_restic_executable(profile.restic_binary)


def build_global_args(
    profile: Profile,
    *,
    force_no_cache: bool = False,
) -> list[str]:
    """Return flags inserted before every restic subcommand."""
    args: list[str] = []
    if profile.no_cache or force_no_cache:
        args.append("--no-cache")
    if profile.retry_lock:
        args += ["--retry-lock", profile.retry_lock]
    return args


def _restic_command_parts(profile: Profile) -> tuple[str, list[str]]:
    """Return the executable and global args for *profile*."""
    return _restic_executable(profile), build_global_args(profile)


def _snapshot_host() -> str:
    """Return the host label used for restic snapshot creation and filtering."""
    return socket.gethostname()


def build_forget_args(
    profile: Profile,
    *,
    current_host_only: bool = False,
    snapshot_host: str | None = None,
) -> list[str]:
    """Return the ``forget`` subcommand scoped by tag and optional host.

    Returns an empty list when no retention policy is configured (all
    ``keep_*`` values are 0), which signals callers to skip the forget step.
    """
    ret = profile.retention
    if not ret:
        return []

    keep_fields: list[tuple[str, int]] = [
        ("--keep-last", ret.keep_last),
        ("--keep-hourly", ret.keep_hourly),
        ("--keep-daily", ret.keep_daily),
        ("--keep-weekly", ret.keep_weekly),
        ("--keep-monthly", ret.keep_monthly),
        ("--keep-yearly", ret.keep_yearly),
    ]

    if not any(value > 0 for _, value in keep_fields):
        return []

    args: list[str] = ["forget"]
    if current_host_only:
        if snapshot_host is None:
            snapshot_host = _snapshot_host()
        args += ["--host", snapshot_host]
    args += ["--tag", profile.tag]
    for flag, value in keep_fields:
        if value > 0:
            args += [flag, str(value)]

    return args


def _build_forget_command(
    profile: Profile,
    *,
    current_host_only: bool = False,
    snapshot_host: str | None = None,
    prune: bool = False,
    restic_executable: str | None = None,
    global_args: list[str] | None = None,
) -> list[str]:
    """Return the full restic forget command for *profile*.

    Returns an empty list when the profile has no effective retention policy.
    """
    forget_args = build_forget_args(
        profile,
        current_host_only=current_host_only,
        snapshot_host=snapshot_host,
    )
    if not forget_args:
        return []

    if restic_executable is None or global_args is None:
        restic_executable, global_args = _restic_command_parts(profile)

    forget_cmd = [restic_executable, *global_args, *forget_args]
    if prune:
        forget_cmd.append("--prune")
    return forget_cmd


def _build_prune_command(
    profile: Profile,
    *,
    restic_executable: str | None = None,
    global_args: list[str] | None = None,
) -> list[str]:
    """Return the full restic prune command for *profile* when enabled."""
    if not profile.retention or not profile.retention.prune:
        return []

    if restic_executable is None or global_args is None:
        restic_executable, global_args = _restic_command_parts(profile)

    return [restic_executable, *global_args, "prune"]


def _build_unlock_command(
    profile: Profile,
    *,
    restic_executable: str | None = None,
    global_args: list[str] | None = None,
) -> list[str]:
    """Return the full restic unlock command for *profile*."""
    if restic_executable is None or global_args is None:
        restic_executable, global_args = _restic_command_parts(profile)

    return [restic_executable, *global_args, "unlock"]


def _is_local_repo(repository: str) -> bool:
    """Return True when *repository* looks like a local filesystem path."""
    return ":" not in repository


def _existing_backup_sources(profile: Profile) -> list[str]:
    """Return the subset of configured backup sources that currently exists."""
    existing_sources: list[str] = []
    if not profile.backup:
        return []
    for source in profile.backup.sources:
        if Path(source).exists():
            existing_sources.append(source)
            continue

        logger.warning(
            "Profile %s: skipping missing backup source %s",
            profile.name,
            source,
        )

    return existing_sources


def _is_existing_repository_error(error: _CommandError) -> bool:
    """Return True when ``restic init`` failed because the repo already exists."""
    combined_output = "\n".join(filter(None, [error.stdout, error.stderr])).lower()
    return "config file already exists" in combined_output


def _repo_initialized(profile: Profile, env: dict[str, str]) -> bool:
    """Return True when the restic repository already exists / is initialised.

    Uses ``restic cat config`` for both local and remote repositories. When the
    profile does not already require ``--no-cache``, the check first retries with
    that flag to bypass stale local restic metadata and then falls back to the
    plain command for older restic builds that lack ``--no-cache``.
    """
    restic_executable, global_args = _restic_command_parts(profile)
    repo_check_commands: list[list[str]] = []

    if profile.no_cache:
        repo_check_commands.append([restic_executable, *global_args, "cat", "config"])
    else:
        repo_check_commands.append(
            [
                restic_executable,
                *build_global_args(profile, force_no_cache=True),
                "cat",
                "config",
            ]
        )
        repo_check_commands.append([restic_executable, *global_args, "cat", "config"])

    for command in repo_check_commands:
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode == 0:
            return True

    return False


def _run(
    cmd: list[str],
    env: dict[str, str],
    *,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Log and execute *cmd*; raise :exc:`_CommandError` on non-zero exit code."""
    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        env=env,
        capture_output=capture_output,
        check=False,
        text=capture_output,
    )
    if result.returncode != 0:
        logger.error("Command failed (exit %s): %s", result.returncode, " ".join(cmd))
        if capture_output:
            if result.stdout:
                logger.error("%s", result.stdout.rstrip())
            if result.stderr:
                logger.error("%s", result.stderr.rstrip())
        raise _CommandError(
            cmd,
            result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )
    return result


def run_hooks(
    commands: list[str],
    env: dict[str, str],
    shell_path: str = "/bin/sh",
    *,
    dry_run: bool = False,
) -> bool:
    """Run *commands* via *shell_path*, returning ``True`` when all succeed.

    Each command string is passed to the shell executable as
    ``shell_path -c command``, so pipelines, redirections, and multi-line
    scripts all work as expected. This is intentionally not
    ``subprocess.run(..., shell=True)``: the caller chooses the exact shell
    binary to exec.

    Returns ``False`` and stops on the first command that exits non-zero.
    In *dry_run* mode, logs each command without executing and returns ``True``.
    """
    for command in commands:
        if dry_run:
            logger.info("DRY RUN: Would run hook: %s", command)
            continue
        logger.info("Running hook: %s", command)
        result = subprocess.run([shell_path, "-c", command], env=env, check=False)
        if result.returncode != 0:
            logger.error(
                "Hook command failed (exit %s): %s", result.returncode, command
            )
            return False
    return True


def run_backup(profile: Profile, *, dry_run: bool = False) -> None:
    """Run ``restic backup`` and any configured inline retention for *profile*.

    Parameters
    ----------
    profile:
        The resolved :class:`Profile` to operate on.
    dry_run:
        When *True* log the actions that would be taken without executing
        any subprocess calls.
    """
    if not profile.is_backup or not profile.backup:
        raise ValueError(
            f"Profile {profile.name!r} has no backup block, cannot run backup"
        )

    hooks = profile.hooks
    env = build_env(profile)
    restic_executable, global_args = _restic_command_parts(profile)

    # prevalidate: run before checking / mounting the backup location
    if not run_hooks(hooks.prevalidate, env, hooks.shell, dry_run=dry_run):
        run_hooks(hooks.failure, env, hooks.shell, dry_run=dry_run)
        raise WorkflowError(f"Profile {profile.name!r}: prevalidate hook failed")

    sources = _existing_backup_sources(profile)
    if not sources:
        raise ValueError(
            f"Profile {profile.name!r} has no existing sources, cannot run backup"
        )

    repo = profile.resolved_repository
    if not repo:
        raise ValueError(f"Profile {profile.name!r} has no resolved repository")
    repo_url = repo.repository
    if _is_local_repo(repo_url):
        repo_path = Path(repo_url)
        if dry_run:
            logger.info("DRY RUN: Would create directory %s", repo_path)
        else:
            logger.debug("Ensuring local repository directory exists: %s", repo_path)
            repo_path.mkdir(parents=True, exist_ok=True)

    if dry_run:
        logger.info("DRY RUN: Would check / initialise repository %s", repo_url)
    else:
        try:
            if not _repo_initialized(profile, env):
                logger.info(
                    "Repository not initialised, running: %s init",
                    restic_executable,
                )
                _run(
                    [restic_executable] + global_args + ["init"],
                    env,
                    capture_output=True,
                )
        except _CommandError as exc:
            if _is_existing_repository_error(exc):
                logger.warning(
                    "restic init reported that %s already exists; continuing",
                    repo_url,
                )
            else:
                run_hooks(hooks.failure, env, hooks.shell, dry_run=dry_run)
                raise WorkflowError(
                    f"Profile {profile.name!r}: repository initialization failed"
                )

    # before: run after location checks, before the backup starts
    if not run_hooks(hooks.before, env, hooks.shell, dry_run=dry_run):
        run_hooks(hooks.failure, env, hooks.shell, dry_run=dry_run)
        raise WorkflowError(f"Profile {profile.name!r}: before hook failed")

    if profile.unlock:
        try:
            run_unlock(profile, dry_run=dry_run)
        except _CommandError:
            logger.warning(
                "restic unlock failed for profile %s; continuing with backup",
                profile.name,
            )

    snapshot_host = _snapshot_host()
    backup_cmd = [
        restic_executable,
        *global_args,
        "backup",
        "--host",
        snapshot_host,
        "--tag",
        profile.tag,
    ]

    if profile.backup.one_file_system:
        backup_cmd.append("--one-file-system")

    for pattern in profile.backup.exclude_patterns:
        backup_cmd += ["--exclude", pattern]

    if profile.backup.exclude_file:
        backup_cmd += ["--exclude-file", profile.backup.exclude_file]

    backup_cmd += sources

    backup_failed = False
    try:
        if dry_run:
            logger.info("DRY RUN: Would run: %s", " ".join(backup_cmd))
        else:
            _run(backup_cmd, env)

        if profile.retention:
            forget_cmd = _build_forget_command(
                profile,
                current_host_only=True,
                snapshot_host=snapshot_host,
                prune=profile.retention.prune,
                restic_executable=restic_executable,
                global_args=global_args,
            )
            if forget_cmd:
                if dry_run:
                    logger.info("DRY RUN: Would run: %s", " ".join(forget_cmd))
                else:
                    _run(forget_cmd, env)
            else:
                prune_cmd = _build_prune_command(
                    profile,
                    restic_executable=restic_executable,
                    global_args=global_args,
                )
                if prune_cmd:
                    if dry_run:
                        logger.info("DRY RUN: Would run: %s", " ".join(prune_cmd))
                    else:
                        _run(prune_cmd, env)
    except _CommandError:
        backup_failed = True

    # after: always runs after the backup attempt (success or failure)
    run_hooks(hooks.after, env, hooks.shell, dry_run=dry_run)

    if backup_failed:
        run_hooks(hooks.failure, env, hooks.shell, dry_run=dry_run)
        raise WorkflowError(f"Profile {profile.name!r}: backup command failed")

    run_hooks(hooks.success, env, hooks.shell, dry_run=dry_run)


def run_retention(
    profile: Profile,
    *,
    dry_run: bool = False,
) -> None:
    """Run ``restic forget`` (and optional ``prune``) for *profile*.

    Parameters
    ----------
    profile:
        The resolved :class:`Profile` to operate on.
    dry_run:
        When *True* log the action without executing any subprocess calls.

    Raises
    ------
    ValueError
        When the profile has no retention block or no retention action.
    """
    if not profile.retention:
        raise ValueError(
            f"Profile {profile.name!r} has no retention block, cannot run retention"
        )

    forget_cmd = _build_forget_command(
        profile,
        current_host_only=profile.retention.forget_current_host,
        prune=profile.retention.prune,
    )
    command = forget_cmd or _build_prune_command(profile)
    if not command:
        raise ValueError(
            f"Profile {profile.name!r} has no retention action, cannot run retention"
        )

    env = build_env(profile)

    if profile.unlock:
        try:
            run_unlock(profile, dry_run=dry_run)
        except _CommandError:
            logger.warning(
                "restic unlock failed for profile %s; continuing with retention",
                profile.name,
            )

    if dry_run:
        logger.info("DRY RUN: Would run: %s", " ".join(command))
    else:
        try:
            _run(command, env)
        except _CommandError as exc:
            raise WorkflowError(
                f"Profile {profile.name!r}: retention command failed"
            ) from exc


def run_unlock(profile: Profile, *, dry_run: bool = False) -> None:
    """Run ``restic unlock`` for *profile* to remove stale locks.

    Parameters
    ----------
    profile:
        The resolved :class:`Profile` to operate on.
    dry_run:
        When *True* log the action without executing any subprocess calls.
    """
    env = build_env(profile)
    unlock_cmd = _build_unlock_command(profile)

    if dry_run:
        logger.info("DRY RUN: Would run: %s", " ".join(unlock_cmd))
    else:
        _run(unlock_cmd, env)


def run_profile(profile: Profile, *, dry_run: bool = False) -> None:
    """Run the configured workflow for *profile*."""
    if profile.is_backup:
        run_backup(profile, dry_run=dry_run)
        return

    if profile.runs_retention:
        run_retention(profile, dry_run=dry_run)
        return

    raise ValueError(
        f"Profile {profile.name!r} has no runnable backup or retention configuration"
    )
