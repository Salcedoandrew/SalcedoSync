"""Pre-upload photo compression, ported from Immich Upload (run-upload.sh v1.7.1).

Same engine and parameters: caesiumclt (libcaesium) v1.5.0, lossy quality 80,
keep EXIF/XMP/ICC (-e), keep file dates (--keep-dates), no resize, no format
change. Only JPEG/PNG/WebP/GIF are compressed; a compressed copy is kept only
if it is smaller, otherwise the original bytes are used. Originals are never
touched: everything goes to a temp folder that mirrors the original folder
name and structure (so "albums from folder names" keeps the original names).
Videos/other files are APFS-cloned into the temp folder for a single upload
pass; if cloning isn't possible they upload from the original folder in a
second pass. RAW files with a same-name JPG are skipped (the JPG is uploaded).

Qt-free.
"""

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

QUALITY = 80
CAESIUM_ARGS = [
    "-q",
    str(QUALITY),
    "-e",
    "--keep-dates",
    "-R",
    "-S",
    "-O",
    "all",
    "--verbose",
    "2",
]
IMG_EXTS = {".jpg", ".jpeg", ".jpe", ".png", ".webp", ".gif"}
IMG_EXCL = ".jpg,.jpeg,.jpe,.png,.webp,.gif"
RAW_EXTS = set(
    [
        "cr2",
        "cr3",
        "crw",
        "nef",
        "nrw",
        "arw",
        "srf",
        "sr2",
        "raf",
        "orf",
        "rw2",
        "rwl",
        "dng",
        "srw",
        "pef",
        "3fr",
        "iiq",
        "erf",
        "mef",
        "mos",
        "mrw",
        "x3f",
        "kdc",
        "dcr",
        "raw",
    ]
)
TEMP_PREFIX = "immich-compress-"


class CompressionCanceled(Exception):
    pass


@dataclass
class CompressResult:
    upload_dir: Path | None = None  # temp folder to upload from; None = originals
    single_pass: bool = False  # True: everything is in upload_dir
    temp_root: Path | None = None  # delete after the run
    paired_raw: list[str] = field(default_factory=list)  # rel paths skipped
    n_img: int = 0
    n_comp: int = 0
    n_pass: int = 0
    n_fail: int = 0
    skipped_symlinks: list[str] = field(
        default_factory=list
    )  # rel paths of symlinks escaping src
    bytes_in: int = 0
    bytes_out: int = 0
    message: str = ""

    @property
    def saved_pct(self) -> int:
        return (
            (self.bytes_in - self.bytes_out) * 100 // self.bytes_in
            if self.bytes_in
            else 0
        )


def find_caesiumclt() -> str | None:
    """Bundled next to the app executable first (like Immich Upload), then PATH."""
    here = [Path(sys.argv[0]).resolve().parent, Path(__file__).resolve().parent.parent]
    for d in here:
        p = d / "caesiumclt"
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return shutil.which("caesiumclt") or (
        "/opt/homebrew/bin/caesiumclt"
        if os.access("/opt/homebrew/bin/caesiumclt", os.X_OK)
        else None
    )


def _is_img(p: Path) -> bool:
    return p.suffix.lower() in IMG_EXTS


def is_paired_raw(p: Path) -> bool:
    if p.suffix.lower().lstrip(".") not in RAW_EXTS:
        return False
    b = str(p)[: -len(p.suffix)]
    return any(
        os.path.exists(b + e) for e in (".jpg", ".JPG", ".jpeg", ".JPEG", ".Jpg")
    )


def ban_file_args(paired_rel: list[str]) -> list[str]:
    """immich-go --ban-file for each paired RAW, glob chars escaped."""
    out: list[str] = []
    for rel in paired_rel:
        out += ["--ban-file", "/" + re.sub(r"([][*?\\+{}])", r"\\\1", rel)]
    return out


def _is_within(base: Path, candidate: Path) -> bool:
    """True if candidate's resolved path is inside base's resolved path.

    Same rule as folder_filters.is_within_folder, kept local so this
    module stays stdlib-only: a symlink target is allowed only when it
    resolves inside the source folder.
    """
    try:
        candidate.resolve().relative_to(base.resolve())
    except (ValueError, OSError, RuntimeError):
        return False
    return True


def _files(src: Path) -> tuple[list[Path], list[str]]:
    """Files under src, following symlinks only while they stay inside src.

    Returns (files, skipped). A symlinked file keeps the link's name; a
    symlinked dir is walked under the link's name unless its target was
    already reached under another name. Symlinks whose resolved target
    escapes src are listed in skipped (rel paths). Dangling links are
    skipped. Entries are visited in sorted order, so which name wins for
    a directory reached twice is deterministic.
    """
    src = src.resolve()
    files: list[Path] = []
    skipped: list[str] = []
    seen: set[Path] = set()
    stack: list[tuple[Path, Path]] = [(src, src)]
    while stack:
        disp, real = stack.pop()
        try:
            resolved = real.resolve()
        except (OSError, RuntimeError):
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            with os.scandir(real) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError:
            continue
        for e in entries:
            p_disp = disp / e.name
            try:
                if e.is_symlink():
                    target = Path(e.path).resolve()
                    if not _is_within(src, target):
                        skipped.append(str(p_disp.relative_to(src)))
                    elif e.is_dir(follow_symlinks=True):
                        stack.append((p_disp, target))
                    elif e.is_file(follow_symlinks=True):
                        files.append(p_disp)
                elif e.is_dir(follow_symlinks=False):
                    stack.append((p_disp, Path(e.path)))
                elif e.is_file(follow_symlinks=False):
                    files.append(p_disp)
            except OSError:
                continue
    return sorted(files), sorted(skipped)


class _OutputCounter:
    """Counts files under a growing output dir.

    Walks the tree with os.scandir on each call, using the directory
    entries' own type (no per-file stat) so it stays cheap even for
    large outputs. An earlier version cached per-directory counts
    keyed on mtime and size, but some filesystems report both at a
    coarse granularity, so files added within the same tick were
    missed and the count went stale. Re-listing is fast enough to run
    on every progress tick, and it is always correct.
    """

    def __init__(self, root: Path):
        self._root = root

    def count(self) -> int:
        return self._count_dir(self._root)

    def _count_dir(self, d: Path) -> int:
        total = 0
        try:
            with os.scandir(d) as it:
                for e in it:
                    if e.is_dir(follow_symlinks=False):
                        total += self._count_dir(Path(e.path))
                    elif e.is_file(follow_symlinks=False):
                        total += 1
        except OSError:
            return 0
        return total


def _copy_dates(orig: Path, dst: Path) -> None:
    """Copy birth + modification time (birth first: setting an older mtime moves birth)."""
    st = orig.stat()
    b = int(getattr(st, "st_birthtime", st.st_mtime))
    try:
        os.utime(dst, (b, b))
        os.utime(dst, ns=(st.st_atime_ns, st.st_mtime_ns))
    except OSError:
        pass


def _clone(src: Path, dst: Path) -> bool:
    """APFS clone (cp -c), keeping attributes (-p). False if cloning fails."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    return (
        subprocess.run(
            ["cp", "-cp", str(src), str(dst)], capture_output=True, check=False
        ).returncode
        == 0
    )


def _same_apfs_volume(a: Path, b: Path) -> bool:
    if a.stat().st_dev != b.stat().st_dev:
        return False
    try:
        dev = subprocess.run(
            ["stat", "-f", "%Sd", str(a)], capture_output=True, text=True, check=False
        ).stdout.strip()
        mounts = subprocess.run(
            ["mount"], capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        return False
    return any(
        line.startswith(f"/dev/{dev} on ") and "(apfs" in line
        for line in mounts.splitlines()
    )


def compress_folder(
    src: Path,
    caesium: str,
    progress: Callable[[str, int, int], None],
    cancel: threading.Event,
    log=None,
    tmpbase: Path | None = None,
) -> CompressResult:
    """Compress photos from src into a temp mirror. Raises CompressionCanceled."""
    src = src.resolve()
    tmpbase = Path(tmpbase or os.environ.get("TMPDIR") or "/tmp").resolve()
    files, skipped = _files(src)
    res = CompressResult()
    res.skipped_symlinks = skipped
    res.paired_raw = [str(p.relative_to(src)) for p in files if is_paired_raw(p)]
    imgs = [p for p in files if _is_img(p)]
    res.n_img = len(imgs)
    if not imgs:
        res.message = "No photos to compress; uploading originals."
        return res

    if src.stat().st_dev != tmpbase.stat().st_dev:
        need_kb = sum(p.stat().st_size for p in imgs) // 1024
        free_kb = shutil.disk_usage(tmpbase).free // 1024
        if need_kb + 2097152 > free_kb:
            res.message = "Not enough free space to compress; uploading originals."
            return res

    root = tmpbase / f"{TEMP_PREFIX}{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    try:
        work = root / src.name
        cdir = root / "caesium-out"
        work.mkdir(parents=True, mode=0o700)
        os.chmod(root, 0o700)
        cdir.mkdir(mode=0o700)
        res.temp_root, res.upload_dir = root, work

        # caesiumclt -S keeps structure relative to the photos' common parent folder
        pfx = None
        for p in imgs:
            d = os.path.dirname(str(p.relative_to(src))) or "."
            if pfx is None:
                pfx = d
                continue
            while pfx != "." and not (d + "/").startswith(pfx + "/"):
                pfx = os.path.dirname(pfx) or "."
        pfx = "" if pfx in (None, ".") else pfx + "/"

        progress("compress", 0, res.n_img)
        logf = open(log, "ab") if log else subprocess.DEVNULL  # noqa: SIM115
        try:
            proc = subprocess.Popen(
                [caesium, *CAESIUM_ARGS, "-o", str(cdir), str(src)],
                stdout=logf,
                stderr=subprocess.STDOUT,
            )
            counter = _OutputCounter(cdir)
            while proc.poll() is None:
                if cancel.is_set():
                    proc.terminate()
                    try:
                        proc.wait(5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    raise CompressionCanceled
                n_out = counter.count()
                progress("compress", min(n_out, res.n_img), res.n_img)
                time.sleep(0.5)
        finally:
            if log:
                logf.close()

        for i, f in enumerate(imgs, 1):
            if cancel.is_set():
                raise CompressionCanceled
            if i % 25 == 1:
                progress("prepare", i, res.n_img)
            rel = str(f.relative_to(src))
            dst = work / rel
            ssz = f.stat().st_size
            c = cdir / rel[len(pfx) :] if rel.startswith(pfx) else cdir / rel
            if not c.is_file():
                c = cdir / rel
            if c.is_file() and not c.is_symlink():
                dsz = c.stat().st_size
                if 0 < dsz < ssz:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(c), str(dst))
                    _copy_dates(f, dst)
                    res.n_comp += 1
                    res.bytes_in += ssz
                    res.bytes_out += dsz
                    continue
            else:
                res.n_fail += 1
            # pass-through: original bytes, untouched (clone if possible)
            dst.unlink(missing_ok=True)
            if not _clone(f, dst):
                shutil.copy2(f, dst)
            _copy_dates(f, dst)
            res.n_pass += 1
        shutil.rmtree(cdir, ignore_errors=True)

        # .xmp sidecars next to photos so photo metadata stays linked
        for f in files:
            if f.suffix.lower() == ".xmp":
                dst = work / f.relative_to(src)
                if not _clone(f, dst):
                    shutil.copy2(f, dst)

        # Videos/other files: APFS clones (no real copy) -> one upload pass.
        others = [
            f
            for f in files
            if not _is_img(f) and f.suffix.lower() != ".xmp" and f.name != ".DS_Store"
        ]
        res.single_pass = _same_apfs_volume(src, tmpbase)
        if res.single_pass:
            for f in others:
                if cancel.is_set():
                    raise CompressionCanceled
                if is_paired_raw(f):
                    continue
                dst = work / f.relative_to(src)
                if not _clone(f, dst):
                    res.single_pass = False
                    break
                _copy_dates(f, dst)
        if not res.single_pass:
            for p in work.rglob("*"):
                if p.is_file() and not _is_img(p) and p.suffix.lower() != ".xmp":
                    p.unlink()

        mb = 1048576
        res.message = (
            f"Compressed {res.n_comp} photos: {res.bytes_in / mb:.1f} MB → {res.bytes_out / mb:.1f} MB "
            f"(saved {res.saved_pct}%)."
        )
        if skipped:
            shown = ", ".join(skipped[:3])
            more = f" and {len(skipped) - 3} more" if len(skipped) > 3 else ""
            res.message += (
                f" Skipped {len(skipped)} symlinked file(s) pointing outside "
                f"the folder: {shown}{more}."
            )
        return res
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)  # canceled/failed: no temp left
        raise


def cleanup(res: CompressResult | None) -> None:
    """Delete this run's temp folder (only ever an immich-compress-* folder)."""
    if res and res.temp_root and res.temp_root.name.startswith(TEMP_PREFIX):
        shutil.rmtree(res.temp_root, ignore_errors=True)
