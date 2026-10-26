"""Unit tests for binary_manager version handling."""

import pytest

from core.binary_manager import (
    BinaryManager,
    _is_safe_version_dir_name,
    clean_version,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1.2.3", "1.2.3"),
        ("v1.2.3", "1.2.3"),
        ("V0.35.0", "0.35.0"),
        ("1.2.3-mod", "1.2.3-mod"),
        ("0.32.0, built with Go", "0.32.0"),
        ("  1.2.3  ", "1.2.3"),
        ("1.2.3-alpha.1", "1.2.3-alpha.1"),
        # Not a version, but clean_version is only normalization: the app
        # update check relies on "dev" passing through untouched.
        ("dev", "dev"),
        ("v", ""),
        ("", ""),
    ],
)
def test_clean_version_keeps_valid_versions(raw, expected):
    assert clean_version(raw) == expected


@pytest.mark.parametrize(
    "version, safe",
    [
        ("1.2.3", True),
        ("0.35.0", True),
        ("1.2.3-mod", True),
        ("1.2.3-alpha.1", True),
        ("../../x", False),
        ("../x", False),
        ("1.2", False),
        ("dev", False),
        ("1.2.3/../../x", False),
        ("", False),
    ],
)
def test_is_safe_version_dir_name(version, safe):
    assert _is_safe_version_dir_name(version) is safe


def test_download_and_install_rejects_escaping_version(tmp_path):
    """A hostile version string must never become a directory name."""
    manager = BinaryManager(base_dir=str(tmp_path), os_name="linux")
    ok, message = manager.download_and_install("../../x")
    assert ok is False
    assert message == "Invalid version tag"
    # Nothing was created outside the base dir.
    assert list(tmp_path.iterdir()) == []
    assert not (tmp_path.parent / "x").exists()
