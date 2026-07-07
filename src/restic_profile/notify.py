from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

import jinja2
from chaos_utils.notify.base import BaseNotifier

from .config import NotifierConfig

if TYPE_CHECKING:
    from .config import Profile

logger = logging.getLogger(__name__)


class ResticSnapshotSummary(TypedDict, total=False):
    data_added: int
    backup_start: str
    backup_end: str


class ResticSnapshot(TypedDict, total=False):
    id: str
    short_id: str
    time: str
    tags: list[str]
    paths: list[str]
    parent: str
    summary: ResticSnapshotSummary


class ResticFileNode(TypedDict, total=False):
    type: str
    name: str
    size: int


class ResticDiffAddedRemoved(TypedDict, total=False):
    files: int
    dirs: int
    bytes: int


class ResticDiffStatistics(TypedDict, total=False):
    changed_files: int
    added: ResticDiffAddedRemoved
    removed: ResticDiffAddedRemoved


class ResticDiffChange(TypedDict, total=False):
    message_type: str
    modifier: str
    path: str


class ResticDiffResult(TypedDict, total=False):
    changes: list[ResticDiffChange]
    statistics: ResticDiffStatistics


class ResticRepoStats(TypedDict, total=False):
    snapshots_count: int
    total_size: int


def _human_bytes(n: float | None) -> str:
    if n is None or n <= 0:
        return "0 B"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"


def _format_ts(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S %z")
    except (ValueError, TypeError):
        return iso_ts


def _format_duration(start: str, end: str) -> str:
    try:
        s = datetime.fromisoformat(start)
        e = datetime.fromisoformat(end)
        sec = int((e - s).total_seconds())
        if sec < 60:
            return f"{sec}s"
        m, s = divmod(sec, 60)
        if m < 60:
            return f"{m}m{s}s"
        h, m = divmod(m, 60)
        return f"{h}h{m}m{s}s"
    except (ValueError, TypeError):
        return ""


@contextmanager
def _inject_notify_env(env_vars: dict[str, str]):
    """Temporarily set environment variables, restoring originals on exit."""
    originals: dict[str, str | None] = {}
    for key, val in env_vars.items():
        originals[key] = os.environ.get(key)
        os.environ[key] = val
    try:
        yield
    finally:
        for key, orig in originals.items():
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig


def _query_snapshot(
    *,
    env: dict[str, str],
    restic_executable: str,
    global_args: list[str],
    snapshot_id: str | None = None,
    tag: str | None = None,
    host: str | None = None,
) -> ResticSnapshot | None:
    cmd = [restic_executable, *global_args, "--json", "snapshots"]
    if snapshot_id:
        cmd.append(snapshot_id)
    else:
        if tag:
            cmd.extend(["--tag", tag])
        if host:
            cmd.extend(["--host", host])
        cmd.extend(["--latest", "1"])

    result = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = snapshot_id or f"tag={tag} host={host}"
        logger.warning(
            "restic snapshots (%s) failed (exit %s): %s",
            detail,
            result.returncode,
            (result.stderr or "").rstrip()[:200],
        )
        return None
    try:
        snapshots = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning("Failed to parse restic snapshots JSON")
        return None
    return snapshots[-1] if snapshots else None


def _query_largest_files(
    snapshot_id: str,
    *,
    env: dict[str, str],
    restic_executable: str,
    global_args: list[str],
    limit: int,
) -> list[ResticFileNode]:
    if limit <= 0:
        return []
    result = subprocess.run(
        [
            restic_executable,
            *global_args,
            "--json",
            "ls",
            "--sort",
            "size",
            snapshot_id,
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.warning(
            "restic ls (snapshot %s) failed (exit %s): %s",
            snapshot_id,
            result.returncode,
            (result.stderr or "").rstrip()[:200],
        )
        return []
    files: list[ResticFileNode] = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") == "file":
            files.append(entry)
    return files[-limit:][::-1]


def _query_snapshot_diff(
    parent_id: str,
    snapshot_id: str,
    *,
    env: dict[str, str],
    restic_executable: str,
    global_args: list[str],
) -> ResticDiffResult | None:
    result = subprocess.run(
        [
            restic_executable,
            *global_args,
            "--json",
            "diff",
            parent_id,
            snapshot_id,
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.warning(
            "restic diff (%s .. %s) failed (exit %s): %s",
            parent_id,
            snapshot_id,
            result.returncode,
            (result.stderr or "").rstrip()[:200],
        )
        return None
    changes: list[ResticDiffChange] = []
    statistics: ResticDiffStatistics = {}
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("message_type") == "change":
            changes.append(entry)
        elif entry.get("message_type") == "statistics":
            statistics = entry
    return {"changes": changes, "statistics": statistics}


def _query_repo_stats(
    *,
    env: dict[str, str],
    restic_executable: str,
    global_args: list[str],
) -> ResticRepoStats | None:
    result = subprocess.run(
        [restic_executable, *global_args, "--json", "stats"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.warning(
            "restic stats (repo) failed (exit %s): %s",
            result.returncode,
            (result.stderr or "").rstrip()[:200],
        )
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning("Failed to parse restic stats JSON for repo")
        return None


def _build_success_facts(
    snapshot: ResticSnapshot,
    largest_files: list[ResticFileNode],
    host: str,
    profile_name: str,
    *,
    diff_data: ResticDiffResult | None = None,
    repo_stats: ResticRepoStats | None = None,
) -> dict[str, object]:
    summary = snapshot.get("summary", {})
    facts: dict[str, object] = {
        "host": host,
        "profile": profile_name,
        "short_id": snapshot.get("short_id", "N/A"),
        "time": _format_ts(str(snapshot.get("time", ""))),
        "tags": snapshot.get("tags", []),
        "paths": snapshot.get("paths", []),
        "data_added": _human_bytes(summary.get("data_added")),
        "duration": _format_duration(
            str(summary.get("backup_start", "")),
            str(summary.get("backup_end", "")),
        ),
        "largest_files": [
            (
                f.get("name", "?"),
                _human_bytes(f.get("size", 0)),
            )
            for f in largest_files
        ],
    }

    if diff_data and diff_data.get("statistics"):
        diff_stats = diff_data["statistics"]
        diff_changes = diff_data.get("changes", [])
        added = diff_stats.get("added", {})
        removed = diff_stats.get("removed", {})
        facts["diff_has_parent"] = True
        facts["diff_changed_files"] = diff_stats.get("changed_files", 0)
        facts["diff_added_files"] = added.get("files", 0)
        facts["diff_added_dirs"] = added.get("dirs", 0)
        facts["diff_added_bytes"] = _human_bytes(added.get("bytes"))
        facts["diff_removed_files"] = removed.get("files", 0)
        facts["diff_removed_dirs"] = removed.get("dirs", 0)
        facts["diff_removed_bytes"] = _human_bytes(removed.get("bytes"))
        facts["diff_changes"] = [
            (c.get("modifier", "?"), c.get("path", "?")) for c in diff_changes
        ]
    else:
        facts["diff_has_parent"] = False

    if repo_stats:
        facts["repo_snapshots_count"] = repo_stats.get("snapshots_count", 0)
        facts["repo_total_size"] = _human_bytes(repo_stats.get("total_size"))
    else:
        facts["repo_snapshots_count"] = 0
        facts["repo_total_size"] = "—"

    return facts


def _load_template_content(
    template_name: str,
    *,
    user_template_dir: str | None = None,
) -> str:
    if user_template_dir:
        user_path = Path(user_template_dir) / template_name
        if user_path.is_file():
            logger.debug("Loading notify template: %s", user_path)
            return user_path.read_text(encoding="utf-8")
    pkg_path = Path(__file__).resolve().parent / "templates" / template_name
    logger.debug("Loading built-in notify template: %s", pkg_path)
    return pkg_path.read_text(encoding="utf-8")


def _render_notify_template(
    template_name: str,
    facts: dict[str, object],
    *,
    template_dir: str | None = None,
) -> str:
    content = _load_template_content(template_name, user_template_dir=template_dir)
    env = jinja2.Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(content)
    return template.render(**facts)


def _build_failure_facts(
    error: str,
    host: str,
    profile_name: str,
) -> dict[str, object]:
    return {
        "host": host,
        "profile": profile_name,
        "error": error,
        "time": _format_ts(datetime.now().astimezone().isoformat()),
    }


def _dispatch_formatted(
    notifier_config: NotifierConfig,
    *,
    title: str,
    markdown: str,
) -> None:
    logger.info("Notify report:\n%s", markdown)
    bot: BaseNotifier = notifier_config.build()
    nt = notifier_config.type
    extra_kwargs: dict[str, object] = getattr(notifier_config, "send_kwargs", {})

    if nt == "dingtalk":
        bot.send_markdown(title, markdown)  # type: ignore
    elif nt == "telegram":
        bot.send_rich_message(markdown=markdown, **extra_kwargs)  # type: ignore
    elif nt == "wechat":
        bot.send_markdown_v2(markdown)  # type: ignore
    else:
        bot.send(markdown)


def try_notify_success(
    profile: Profile,
    *,
    snapshot_id: str | None,
    env: dict[str, str],
    restic_executable: str,
    global_args: list[str],
) -> None:
    """Send a success notification for *profile*."""
    if profile.resolved_notifier is None:
        return

    host = socket.gethostname()
    tag = profile.tag

    snap = _query_snapshot(
        snapshot_id=snapshot_id,
        tag=tag,
        host=host,
        env=env,
        restic_executable=restic_executable,
        global_args=global_args,
    )

    if not snap:
        logger.warning(
            "No snapshot data available for success notification (profile %s)",
            profile.name,
        )
        return

    snap_id = snap.get("id", "latest")
    notifier = profile.resolved_notifier
    limit = max(notifier.top_files_limit, 0)
    largest_files = _query_largest_files(
        snap_id,
        env=env,
        restic_executable=restic_executable,
        global_args=global_args,
        limit=limit,
    )

    parent_id = snap.get("parent")
    diff_data: ResticDiffResult | None = None
    if parent_id:
        diff_data = _query_snapshot_diff(
            parent_id,
            snap_id,
            env=env,
            restic_executable=restic_executable,
            global_args=global_args,
        )
        if not diff_data:
            diff_data = None

    repo_stats = _query_repo_stats(
        env=env,
        restic_executable=restic_executable,
        global_args=global_args,
    )

    facts = _build_success_facts(
        snap,
        largest_files,
        host,
        profile.name,
        diff_data=diff_data,
        repo_stats=repo_stats,
    )

    markdown = _render_notify_template(
        "notify_success.md.j2",
        facts,
        template_dir=profile.resolved_template_dir or None,
    )

    with _inject_notify_env(notifier.env):
        _dispatch_formatted(
            notifier,
            title=f"restic Backup Succeeded — {profile.name}",
            markdown=markdown,
        )


def try_notify_failure(profile: Profile, error_msg: str) -> None:
    """Send a failure notification for *profile*."""
    if profile.resolved_notifier is None:
        return

    host = socket.gethostname()
    facts = _build_failure_facts(error_msg, host, profile.name)
    notifier = profile.resolved_notifier

    markdown = _render_notify_template(
        "notify_failure.md.j2",
        facts,
        template_dir=profile.resolved_template_dir or None,
    )

    with _inject_notify_env(notifier.env):
        _dispatch_formatted(
            notifier,
            title=f"restic Backup Failed — {profile.name}",
            markdown=markdown,
        )
