"""Compression: symlinks, temp-dir permissions, incremental progress count."""

import os
import stat
import threading
from pathlib import Path

import pytest

from core.compression import _files, _OutputCounter, cleanup, compress_folder

pytestmark = pytest.mark.unit


def _fake_caesium(tmp_path: Path) -> str:
    p = tmp_path / "caesiumclt"
    p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    p.chmod(0o755)
    return str(p)


def _src(tmp_path: Path, *names: str) -> Path:
    src = tmp_path / "photos"
    src.mkdir()
    for name in names:
        (src / name).write_bytes(b"fake-image-data")
    return src


def _names(paths) -> list[str]:
    return sorted(p.name for p in paths)


def test_files_includes_in_folder_symlink(tmp_path):
    src = _src(tmp_path, "a.jpg", "b_target.jpg", "v_target.mp4")
    os.symlink("b_target.jpg", src / "b_link.jpg")
    os.symlink("v_target.mp4", src / "v_link.mp4")
    files, skipped = _files(src)
    assert _names(files) == [
        "a.jpg",
        "b_link.jpg",
        "b_target.jpg",
        "v_link.mp4",
        "v_target.mp4",
    ]
    assert skipped == []


def test_files_skips_escaping_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.jpg").write_bytes(b"x")
    src = _src(tmp_path, "a.jpg")
    os.symlink(outside / "secret.jpg", src / "escape.jpg")
    files, skipped = _files(src)
    assert _names(files) == ["a.jpg"]
    assert skipped == ["escape.jpg"]


def test_files_recurses_symlinked_dir(tmp_path):
    src = _src(tmp_path, "a.jpg")
    sub = src / "sub"
    sub.mkdir()
    (sub / "photo.jpg").write_bytes(b"x")
    os.symlink("sub", src / "linkdir")
    files, skipped = _files(src)
    # The target is already walked under its real name, so the link adds
    # no second copy: the photo appears once, as sub/photo.jpg.
    # as_posix() so the comparison holds on Windows (backslash separator).
    assert [p.relative_to(src).as_posix() for p in files] == [
        "a.jpg",
        "sub/photo.jpg",
    ]
    assert skipped == []


def test_files_symlink_cycle(tmp_path):
    src = _src(tmp_path, "a.jpg")
    os.symlink(".", src / "loop")
    files, skipped = _files(src)
    assert _names(files) == ["a.jpg"]
    assert skipped == []


def test_files_dangling_symlink(tmp_path):
    src = _src(tmp_path, "a.jpg")
    os.symlink("missing.jpg", src / "broken.jpg")
    files, skipped = _files(src)
    assert _names(files) == ["a.jpg"]
    assert skipped == []


def test_compress_folder_includes_symlinked_image(tmp_path):
    src = _src(tmp_path, "a.jpg", "b_target.jpg")
    os.symlink("b_target.jpg", src / "b_link.jpg")
    res = compress_folder(
        src,
        _fake_caesium(tmp_path),
        lambda *a: None,
        threading.Event(),
        tmpbase=tmp_path,
    )
    try:
        assert res.skipped_symlinks == []
        assert (res.upload_dir / "b_link.jpg").is_file()
        assert (res.upload_dir / "b_target.jpg").is_file()
        assert "Skipped" not in res.message
    finally:
        cleanup(res)


def test_compress_folder_warns_escaping_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.jpg").write_bytes(b"x")
    src = _src(tmp_path, "a.jpg")
    os.symlink(outside / "secret.jpg", src / "escape.jpg")
    res = compress_folder(
        src,
        _fake_caesium(tmp_path),
        lambda *a: None,
        threading.Event(),
        tmpbase=tmp_path,
    )
    try:
        assert res.skipped_symlinks == ["escape.jpg"]
        assert "Skipped 1 symlinked file(s) pointing outside the folder" in res.message
        assert not (res.upload_dir / "escape.jpg").exists()
        assert (res.upload_dir / "a.jpg").is_file()
    finally:
        cleanup(res)


def test_temp_root_is_private(tmp_path):
    src = _src(tmp_path, "a.jpg")
    res = compress_folder(
        src,
        _fake_caesium(tmp_path),
        lambda *a: None,
        threading.Event(),
        tmpbase=tmp_path,
    )
    try:
        assert stat.S_IMODE(res.temp_root.stat().st_mode) == 0o700
        assert stat.S_IMODE(res.upload_dir.stat().st_mode) == 0o700
    finally:
        cleanup(res)


def test_output_counter_incremental(tmp_path):
    out = tmp_path / "out"
    (out / "sub").mkdir(parents=True)
    (out / "a.jpg").write_bytes(b"x")
    counter = _OutputCounter(out)

    def full_count():
        return sum(1 for p in out.rglob("*") if p.is_file())

    assert counter.count() == full_count() == 1
    (out / "sub" / "b.jpg").write_bytes(b"x")
    (out / "sub" / "c.jpg").write_bytes(b"x")
    assert counter.count() == full_count() == 3
    (out / "d.jpg").write_bytes(b"x")
    (out / "sub2").mkdir()
    (out / "sub2" / "e.jpg").write_bytes(b"x")
    assert counter.count() == full_count() == 5
    # Unchanged tree: repeated counts stay correct without re-walking.
    assert counter.count() == 5
    assert counter.count() == full_count()
