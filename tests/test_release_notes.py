"""Unit tests for scripts/release_notes.py."""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release_notes.py"

CHANGELOG = """# Changelog

## 1.5.2-mod (2026-10-25)

Audit fixes #5-9.

- **API key file is created locked-down.**

## 1.5.1-mod (2026-10-25)

Audit fixes #1-4.

- **Symlinks are included.**
"""


def _run(tmp_path, *args):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--changelog", str(changelog)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_renders_install_whats_new_features_credits(tmp_path):
    out = tmp_path / "notes.md"
    res = _run(tmp_path, "1.5.2-mod", "--output", str(out))
    assert res.returncode == 0, res.stderr
    notes = out.read_text(encoding="utf-8")
    assert "SalcedoSync-1.5.2-mod-arm64.dmg" in notes
    assert "## What's new since 1.5.1-mod" in notes
    assert "Audit fixes #5-9." in notes
    assert "API key file is created locked-down." in notes
    assert "Audit fixes #1-4." not in notes
    assert "## Features" in notes
    assert "## Credits" in notes
    assert "Apple Silicon (arm64) only." in notes


def test_missing_version_fails(tmp_path):
    res = _run(tmp_path, "9.9.9-mod")
    assert res.returncode != 0
    assert "No '## 9.9.9-mod' section" in res.stderr
