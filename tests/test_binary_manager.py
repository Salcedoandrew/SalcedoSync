"""Unit tests for binary_manager version handling."""

import pytest

from core.binary_manager import clean_version

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
    ],
)
def test_clean_version_keeps_valid_versions(raw, expected):
    assert clean_version(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "../../x",
        "../x",
        "1.2",
        "abc",
        "1.2.3/../../x",
        "1.2.3+build",
        "v",
    ],
)
def test_clean_version_rejects_non_versions(raw):
    """A hostile version string must never become a directory name."""
    assert clean_version(raw) == ""
