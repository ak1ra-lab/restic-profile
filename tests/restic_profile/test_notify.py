"""Tests for restic_profile.notify — notification formatting and dispatch."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from restic_profile.notify import (  # type: ignore[import-not-found]
    _build_failure_facts,
    _build_success_facts,
    _dispatch_formatted,
    _format_duration,
    _format_ts,
    _human_bytes,
    _inject_notify_env,
    _query_repo_stats,
    _query_snapshot,
    _query_snapshot_diff,
    _render_notify_template,
    try_notify_failure,
    try_notify_success,
)


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (None, "0 B"),
        (0, "0 B"),
        (-1, "0 B"),
        (1, "1 B"),
        (1023, "1023 B"),
        (1024, "1.0 KiB"),
        (1536, "1.5 KiB"),
        (1048576, "1.0 MiB"),
        (1073741824, "1.0 GiB"),
    ],
)
def test_human_bytes(n, expected):
    assert _human_bytes(n) == expected


def test_format_ts_valid():
    result = _format_ts("2024-01-15T08:30:45+08:00")
    assert "2024-01-15" in result
    assert "08:30:45" in result


def test_format_ts_invalid():
    assert _format_ts("not-a-timestamp") == "not-a-timestamp"
    assert _format_ts("") == ""


def test_fmt_duration_valid():
    assert (
        _format_duration(
            "2024-01-15T08:30:00+08:00",
            "2024-01-15T08:35:30+08:00",
        )
        == "5m30s"
    )


def test_fmt_duration_hours():
    result = _format_duration(
        "2024-01-15T08:00:00+00:00",
        "2024-01-15T10:05:00+00:00",
    )
    assert result == "2h5m0s"


def test_fmt_duration_invalid():
    assert _format_duration("bad", "also-bad") == ""
    assert _format_duration("", "") == ""


def test_inject_notify_env_sets_and_restores():
    import os

    with _inject_notify_env({"TEST_NOTIFY_FOO": "bar"}):
        assert os.environ.get("TEST_NOTIFY_FOO") == "bar"
    assert os.environ.get("TEST_NOTIFY_FOO") is None


def test_inject_notify_env_restores_original():
    import os

    os.environ["TEST_NOTIFY_ORIG"] = "original"
    with _inject_notify_env({"TEST_NOTIFY_ORIG": "override"}):
        assert os.environ["TEST_NOTIFY_ORIG"] == "override"
    assert os.environ["TEST_NOTIFY_ORIG"] == "original"
    del os.environ["TEST_NOTIFY_ORIG"]


def _make_minimal_snapshot():
    return {
        "id": "abc123def456abc123def456abc123def456abc123def456abc123def456abc",
        "short_id": "abc123de",
        "time": "2024-01-15T08:30:45+08:00",
        "hostname": "test-host",
        "tags": ["myapp", "production"],
        "paths": ["/data", "/backup"],
        "parent": "def456abc789def456abc789def456abc789def456abc789def456abc789",
        "summary": {
            "files_new": 10,
            "files_changed": 5,
            "files_unmodified": 100,
            "dirs_new": 2,
            "dirs_changed": 0,
            "dirs_unmodified": 15,
            "data_added": 1572864,
            "total_files_processed": 115,
            "total_bytes_processed": 2684354560,
            "backup_start": "2024-01-15T08:30:00+08:00",
            "backup_end": "2024-01-15T08:35:30+08:00",
        },
    }


def _make_minimal_largest_files():
    return [
        {"name": "/data/bigfile.bin", "type": "file", "size": 524288000},
        {"name": "/data/medium.db", "type": "file", "size": 104857600},
    ]


def _make_minimal_diff_data():
    return {
        "changes": [
            {"message_type": "change", "path": "/data/new.log", "modifier": "+"},
            {"message_type": "change", "path": "/data/old.tmp", "modifier": "-"},
        ],
        "statistics": {
            "message_type": "statistics",
            "source_snapshot": "def456ab",
            "target_snapshot": "abc123de",
            "changed_files": 0,
            "added": {
                "files": 2,
                "dirs": 1,
                "others": 0,
                "data_blobs": 10,
                "tree_blobs": 2,
                "bytes": 5242880,
            },
            "removed": {
                "files": 1,
                "dirs": 0,
                "others": 0,
                "data_blobs": 5,
                "tree_blobs": 1,
                "bytes": 1048576,
            },
        },
    }


def _make_minimal_repo_stats():
    return {
        "total_size": 12884901888,
        "total_file_count": 2048,
        "snapshots_count": 42,
    }


def test_build_success_facts_has_all_keys():
    snapshot = _make_minimal_snapshot()
    largest_files = _make_minimal_largest_files()
    facts = _build_success_facts(snapshot, largest_files, "test-host", "myapp")

    assert facts["host"] == "test-host"
    assert facts["profile"] == "myapp"
    assert facts["short_id"] == "abc123de"
    assert facts["tags"] == ["myapp", "production"]
    assert facts["paths"] == ["/data", "/backup"]
    assert facts["data_added"] == "1.5 MiB"
    assert facts["duration"] == "5m30s"
    assert len(facts["largest_files"]) == 2
    assert facts["diff_has_parent"] is False
    assert facts["repo_snapshots_count"] == 0
    assert facts["repo_total_size"] == "—"


def test_build_success_facts_with_diff_and_repo():
    snapshot = _make_minimal_snapshot()
    largest_files = _make_minimal_largest_files()
    diff_data = _make_minimal_diff_data()
    repo_stats = _make_minimal_repo_stats()

    facts = _build_success_facts(
        snapshot,
        largest_files,
        "test-host",
        "myapp",
        diff_data=diff_data,
        repo_stats=repo_stats,
    )

    assert facts["diff_has_parent"] is True
    assert facts["diff_changed_files"] == 0
    assert facts["diff_added_files"] == 2
    assert facts["diff_added_dirs"] == 1
    assert facts["diff_added_bytes"] == "5.0 MiB"
    assert facts["diff_removed_files"] == 1
    assert facts["diff_removed_dirs"] == 0
    assert facts["diff_removed_bytes"] == "1.0 MiB"
    assert len(facts["diff_changes"]) == 2
    assert facts["diff_changes"][0] == ("+", "/data/new.log")
    assert facts["diff_changes"][1] == ("-", "/data/old.tmp")
    assert facts["repo_snapshots_count"] == 42
    assert facts["repo_total_size"] == "12.0 GiB"


def test_render_success_template_contains_key_info():
    snapshot = _make_minimal_snapshot()
    largest_files = _make_minimal_largest_files()
    diff_data = _make_minimal_diff_data()
    repo_stats = _make_minimal_repo_stats()
    facts = _build_success_facts(
        snapshot,
        largest_files,
        "test-host",
        "myapp",
        diff_data=diff_data,
        repo_stats=repo_stats,
    )
    text = _render_notify_template("notify_success.md.j2", facts)

    assert "restic Backup Succeeded" in text
    assert "test-host" in text
    assert "abc123de" in text
    assert "/data" in text
    assert "1.5 MiB" in text
    assert "5m30s" in text
    assert "bigfile.bin" in text
    assert "Changes" in text
    assert "+2 files" in text
    assert "-1 files" in text
    assert "/data/new.log" in text
    assert "/data/old.tmp" in text
    assert "Repository" in text
    assert "42 snapshots" in text
    assert "12.0 GiB" in text


def test_render_success_template_no_diff():
    snapshot = _make_minimal_snapshot()
    largest_files = _make_minimal_largest_files()
    repo_stats = _make_minimal_repo_stats()
    facts = _build_success_facts(
        snapshot,
        largest_files,
        "test-host",
        "myapp",
        repo_stats=repo_stats,
    )
    text = _render_notify_template("notify_success.md.j2", facts)

    assert "Changes" not in text
    assert "Repository" in text


def test_render_success_no_largest_files():
    snapshot = _make_minimal_snapshot()
    facts = _build_success_facts(snapshot, [], "test-host", "myapp")
    text = _render_notify_template("notify_success.md.j2", facts)

    assert "Largest Files" not in text


def test_render_success_no_tags():
    snapshot = _make_minimal_snapshot()
    snapshot["tags"] = []
    facts = _build_success_facts(snapshot, [], "test-host", "myapp")
    text = _render_notify_template("notify_success.md.j2", facts)

    assert "Tags" not in text


def test_build_failure_facts():
    facts = _build_failure_facts("exit 1\nconnection refused", "test-host", "myapp")

    assert facts["host"] == "test-host"
    assert facts["profile"] == "myapp"
    assert "exit 1" in facts["error"]


def test_render_failure_template():
    facts = _build_failure_facts("exit 1", "test-host", "myapp")
    text = _render_notify_template("notify_failure.md.j2", facts)

    assert "restic Backup Failed" in text
    assert "test-host" in text
    assert "myapp" in text
    assert "exit 1" in text


def test_dispatch_formatted_dingtalk():
    notifier_config = MagicMock()
    notifier_config.type = "dingtalk"
    bot_mock = MagicMock()
    notifier_config.build.return_value = bot_mock

    _dispatch_formatted(
        notifier_config,
        title="test",
        markdown="**markdown**",
    )
    bot_mock.send_markdown.assert_called_once_with("test", "**markdown**")


def test_dispatch_formatted_telegram():
    notifier_config = MagicMock()
    notifier_config.type = "telegram"
    notifier_config.send_kwargs = {"disable_notification": True}
    bot_mock = MagicMock()
    notifier_config.build.return_value = bot_mock

    _dispatch_formatted(
        notifier_config,
        title="test",
        markdown="**md**",
    )
    bot_mock.send_rich_message.assert_called_once_with(
        markdown="**md**",
        disable_notification=True,
    )


def test_dispatch_formatted_wechat():
    notifier_config = MagicMock()
    notifier_config.type = "wechat"
    bot_mock = MagicMock()
    notifier_config.build.return_value = bot_mock

    _dispatch_formatted(
        notifier_config,
        title="test",
        markdown="**md**",
    )
    bot_mock.send_markdown_v2.assert_called_once_with("**md**")


def test_dispatch_formatted_unknown_falls_back_to_send():
    notifier_config = MagicMock()
    notifier_config.type = "unknown"
    bot_mock = MagicMock()
    notifier_config.build.return_value = bot_mock

    _dispatch_formatted(
        notifier_config,
        title="test",
        markdown="plain",
    )
    bot_mock.send.assert_called_once_with("plain")


def test_query_snapshot_diff_returns_parsed_data():
    stdout = (
        '{"message_type":"change","path":"/a","modifier":"+"}\n'
        '{"message_type":"change","path":"/b","modifier":"-"}\n'
        '{"message_type":"statistics","added":{"files":1,"dirs":0,"bytes":100},"removed":{"files":1,"dirs":0,"bytes":200},"changed_files":0}\n'
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=stdout, stderr="")
        result = _query_snapshot_diff(
            "parent1",
            "snap1",
            env={},
            restic_executable="restic",
            global_args=[],
        )

    assert len(result["changes"]) == 2
    assert result["changes"][0]["path"] == "/a"
    assert result["changes"][1]["modifier"] == "-"
    assert result["statistics"]["added"]["files"] == 1


def test_query_snapshot_diff_nonzero_return():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="diff failed")
        result = _query_snapshot_diff(
            "parent1",
            "snap1",
            env={},
            restic_executable="restic",
            global_args=[],
        )

    assert result == {}


def test_query_snapshot_by_id_returns_single():
    stdout = json.dumps([_make_minimal_snapshot()])
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=stdout, stderr="")
        result = _query_snapshot(
            snapshot_id="abc123de",
            env={},
            restic_executable="restic",
            global_args=[],
        )

    assert result["short_id"] == "abc123de"
    assert result["parent"]


def test_query_snapshot_by_tag_host_returns_latest():
    stdout = json.dumps([_make_minimal_snapshot()])
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=stdout, stderr="")
        result = _query_snapshot(
            tag="myapp",
            host="test-host",
            env={},
            restic_executable="restic",
            global_args=[],
        )

    call_args = mock_run.call_args[0][0]
    assert "--latest" in call_args
    assert "--tag" in call_args
    assert result["short_id"] == "abc123de"


def test_query_snapshot_nonzero_return():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="query failed"
        )
        result = _query_snapshot(
            snapshot_id="abc",
            env={},
            restic_executable="restic",
            global_args=[],
        )

    assert result == {}


def test_query_repo_stats_returns_data():
    stdout = '{"total_size": 1073741824, "snapshots_count": 5}\n'
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=stdout, stderr="")
        result = _query_repo_stats(
            env={},
            restic_executable="restic",
            global_args=[],
        )

    assert result["total_size"] == 1073741824
    assert result["snapshots_count"] == 5


def test_query_repo_stats_nonzero_return():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="stats failed"
        )
        result = _query_repo_stats(
            env={},
            restic_executable="restic",
            global_args=[],
        )

    assert result == {}


def test_try_notify_success_no_notifier():
    profile = MagicMock()
    profile.resolved_notifier = None

    try_notify_success(
        profile,
        snapshot_id="abc",
        env={},
        restic_executable="restic",
        global_args=[],
    )


def test_try_notify_failure_no_notifier():
    profile = MagicMock()
    profile.resolved_notifier = None

    try_notify_failure(profile, "error")


def test_try_notify_failure_with_notifier():
    notifier_config = MagicMock()
    notifier_config.type = "dingtalk"
    notifier_config.env = {}
    bot_mock = MagicMock()
    notifier_config.build.return_value = bot_mock

    profile = MagicMock()
    profile.resolved_notifier = notifier_config
    profile.name = "myapp"
    profile.resolved_template_dir = ""

    with patch("restic_profile.notify.socket.gethostname", return_value="test-host"):
        try_notify_failure(profile, "exit 1")
    bot_mock.send_markdown.assert_called_once()
