"""Album choice mapping and immich-go --no-ui progress parsing."""

import pytest

from core.album_choice import album_flags_state
from core.upload_progress import UploadStats

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        (
            "Just upload to Immich (no album)",
            {"folder-album": "NONE", "into-album": ""},
        ),
        ("Add to an existing album", {"folder-album": "NONE", "into-album": "Old"}),
        ("Create a new album", {"folder-album": "NONE", "into-album": "New"}),
        ("Make albums from folder names", {"folder-album": "FOLDER", "into-album": ""}),
    ],
)
def test_album_flags_state(label, expected):
    assert album_flags_state(label, " Old ", "New") == expected


def test_progress_parsing():
    s = UploadStats()
    s.feed_stdout(
        "Immich read 40%, Assets found: 3, Upload errors: 0, Uploaded 0\r"
        "Immich read 101%, Assets found: 3, Upload errors: 0, Uploaded 2\r"
        "\nTotal Assets:          3  (3.8 MB)\n  Errors:              0  (0 B)\n"
    )
    for line in [
        "2026-10-23 19:36:25 INF metadata updated file=A:x.jpg reason=bigger exists",
        "2026-10-23 19:36:26 INF uploaded successfully file=A:y.jpg",
        "2026-10-23 19:36:26 INF uploaded successfully file=A:y.jpg",
    ]:
        s.feed_log_line(line)
    assert (s.immich_read_pct, s.found, s.uploaded, s.duplicates, s.done) == (
        100,
        3,
        2,
        1,
        3,
    )
    assert s.report == {"Total Assets": 3, "Errors": 0}


def test_compression_helpers(tmp_path):
    from core.compression import ban_file_args, is_paired_raw

    (tmp_path / "a.RAF").write_bytes(b"x")
    (tmp_path / "a.JPG").write_bytes(b"x")
    (tmp_path / "b.raf").write_bytes(b"x")
    assert is_paired_raw(tmp_path / "a.RAF")
    assert not is_paired_raw(tmp_path / "b.raf")
    assert ban_file_args(["d [1]/a*.RAF"]) == ["--ban-file", "/d \\[1\\]/a\\*.RAF"]
