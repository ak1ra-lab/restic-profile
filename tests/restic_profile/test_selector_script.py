"""Tests for the restic-profile interactive selector shell helper."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SELECTOR_SCRIPT = (
    REPO_ROOT / "roles" / "restic_profile" / "files" / "restic-profile-select.bash"
)


def _write_selector_script(tmp_path: Path, config_dir: Path) -> Path:
    """Write a test-local selector script with its config dir pointed at tmp_path."""
    script_text = SELECTOR_SCRIPT.read_text(encoding="utf-8").replace(
        'local config_dir="/etc/restic-profile"',
        f'local config_dir="{config_dir}"',
        1,
    )
    script_path = tmp_path / "restic-profile-select.bash"
    script_path.write_text(script_text, encoding="utf-8")
    return script_path


def _write_profile_env(config_dir: Path, profile_name: str, exports: list[str]) -> None:
    """Write one rendered restic-profile env file for the selector to load."""
    env_path = config_dir / f"restic-profile-{profile_name}.env"
    env_path.write_text("\n".join(exports) + "\n", encoding="utf-8")


def test_selector_clears_managed_vars_between_profile_switches(tmp_path: Path) -> None:
    """Selecting a second profile clears optional vars that were only set by the first."""
    config_dir = tmp_path / "etc-restic-profile"
    config_dir.mkdir()

    _write_profile_env(
        config_dir,
        "alpha",
        [
            'export RESTIC_PROFILE_NAME="alpha"',
            'export RESTIC_REPOSITORY="rest:https://backup.example.com/alpha"',
            'export AWS_ACCESS_KEY_ID="KEY_ONE"',
        ],
    )
    _write_profile_env(
        config_dir,
        "beta",
        [
            'export RESTIC_PROFILE_NAME="beta"',
            'export RESTIC_REPOSITORY="rest:https://backup.example.com/beta"',
        ],
    )

    script_path = _write_selector_script(tmp_path, config_dir)
    command = textwrap.dedent(
        f"""\
        source "{script_path}"
        restic-profile-select <<<"1" >/dev/null 2>/dev/null
        printf 'after_first=%s\\n' "${{AWS_ACCESS_KEY_ID-<unset>}}"
        restic-profile-select <<<"2" >/dev/null 2>/dev/null
        printf 'after_second=%s\\n' "${{AWS_ACCESS_KEY_ID-<unset>}}"
        printf 'profile=%s\\n' "${{RESTIC_PROFILE_NAME-<unset>}}"
        """
    )

    result = subprocess.run(
        ["/bin/bash", "-lc", command],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "after_first=KEY_ONE" in result.stdout
    assert "after_second=<unset>" in result.stdout
    assert "profile=beta" in result.stdout
