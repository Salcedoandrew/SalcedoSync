"""In-app immich-go runner: optional compression stage, then background
immich-go pass(es) with live progress and Cancel."""

import os
import signal
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
)

from core.compression import (
    CompressionCanceled,
    CompressResult,
    cleanup,
    compress_folder,
)
from core.upload_progress import UploadStats
from gui.widgets.cards import Card

_STATS = (
    ("found", "Discovered"),
    ("uploaded", "Uploaded"),
    ("duplicates", "Already in Immich"),
    ("skipped", "Skipped"),
    ("errors", "Errors"),
)

Pass = tuple[list[str], Path]  # immich-go args, its --log-file


class _CompressSignals(QObject):
    progress = Signal(str, int, int)
    done = Signal(object, str)  # CompressResult | None, error ("" / "canceled")


class RunPanel(Card):
    finished = Signal(bool)  # True on success

    def __init__(self, parent=None):
        super().__init__("Upload Progress", parent=parent)
        self.setFixedWidth(340)
        self.proc: QProcess | None = None
        self.stats = UploadStats()
        self._prev: list[UploadStats] = []
        self._passes: list[Pass] = []
        self._program = ""
        self._env: dict[str, str] = {}
        self._compressing = False
        self._compress: CompressResult | None = None
        self._cancel_event = threading.Event()
        self._log_path: Path | None = None
        self._log_pos = 0
        self._stdout_tail = ""
        self._stderr_tail = ""
        self._canceled = False

        self.lbl_status = QLabel("Ready. Pick a folder and click Run Command.")
        self.lbl_status.setWordWrap(True)
        self.layout.addWidget(self.lbl_status)

        self.lbl_compress = QLabel("Compressing photos")
        self.layout.addWidget(self.lbl_compress)
        self.bar_compress = QProgressBar()
        self.layout.addWidget(self.bar_compress)
        self.layout.addWidget(QLabel("Checking what's already in Immich"))
        self.bar_read = QProgressBar()
        self.layout.addWidget(self.bar_read)
        self.layout.addWidget(QLabel("Files processed"))
        self.bar_files = QProgressBar()
        self.layout.addWidget(self.bar_files)

        grid = QGridLayout()
        self.stat_labels: dict[str, QLabel] = {}
        for i, (key, title) in enumerate(_STATS):
            grid.addWidget(QLabel(title), i, 0)
            val = QLabel("0")
            val.setObjectName("CardTitle")
            grid.addWidget(val, i, 1)
            self.stat_labels[key] = val
        self.layout.addLayout(grid)

        row = QHBoxLayout()
        row.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("BtnPreview")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel)
        row.addWidget(self.btn_cancel)
        self.layout.addLayout(row)

        self._sig = _CompressSignals()
        self._sig.progress.connect(self._on_compress_progress)
        self._sig.done.connect(self._on_compress_done)

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._poll_log)
        self._show_compress(False)
        self._reset_view()

    def is_running(self) -> bool:
        return self._compressing or (
            self.proc is not None
            and self.proc.state() != QProcess.ProcessState.NotRunning
        )

    def start(
        self,
        program: str,
        passes: list[Pass],
        env: dict[str, str],
        compress: tuple[Path, str, Path, Callable[[CompressResult], list[Pass]]]
        | None = None,
    ) -> None:
        """Run passes in order. With compress=(src, caesiumclt, log, make_passes),
        compress first and build the passes from the result."""
        self._program, self._env, self._passes = program, env, list(passes)
        self._prev, self.stats = [], UploadStats()
        self._compress, self._canceled = None, False
        self._cancel_event = threading.Event()
        self._stderr_tail = ""
        self._show_compress(compress is not None)
        self._reset_view()
        self.btn_cancel.setEnabled(True)
        if compress is None:
            self._run_next_pass()
            return
        src, caesium, log, self._make_passes = compress
        self._compressing = True
        self.lbl_status.setText("Compressing photos…")
        sig, ev = self._sig, self._cancel_event

        def work():
            try:
                res = compress_folder(src, caesium, sig.progress.emit, ev, log=str(log))
                sig.done.emit(res, "")
            except CompressionCanceled:
                sig.done.emit(None, "canceled")
            except Exception as e:
                sig.done.emit(None, f"{type(e).__name__}: {e}"[:300])

        threading.Thread(target=work, daemon=True).start()

    def cancel(self) -> None:
        if not self.is_running():
            return
        self._canceled = True
        self.lbl_status.setText("Canceling…")
        if self._compressing:
            self._cancel_event.set()
            return
        # immich-go exits cleanly (report, resumes paused Immich jobs) on Ctrl+C
        # but dies abruptly on SIGTERM, so send SIGINT where available.
        if sys.platform.startswith("win"):
            self.proc.terminate()
        else:
            os.kill(self.proc.processId(), signal.SIGINT)
        QTimer.singleShot(10000, lambda: self.is_running() and self.proc.kill())

    # ── compression stage ──────────────────────────────────────────
    def _show_compress(self, on: bool):
        self.lbl_compress.setVisible(on)
        self.bar_compress.setVisible(on)

    def _on_compress_progress(self, stage: str, done: int, total: int):
        if self._canceled:
            return
        self.bar_compress.setRange(0, max(total, 1))
        self.bar_compress.setValue(done)
        self.bar_compress.setFormat(
            f"%v / %m photos{'' if stage == 'compress' else ' (preparing)'}"
        )
        self.lbl_status.setText(
            f"Compressing photos… {done} of {total}"
            if stage == "compress"
            else f"Preparing compressed photos… {done} of {total}"
        )

    def _on_compress_done(self, res: CompressResult | None, error: str):
        self._compressing = False
        if error == "canceled" or self._canceled:
            cleanup(res)
            self._finish(False, "⏹ Canceled during compression. Nothing was uploaded.")
            return
        if res is None:  # failed: upload originals, like Immich Upload
            res = CompressResult(
                message=f"Compression failed ({error}); uploading originals."
            )
        self._compress = res
        self.bar_compress.setValue(self.bar_compress.maximum())
        self._passes = self._make_passes(res)
        self._run_next_pass()

    # ── immich-go passes ───────────────────────────────────────────
    def _run_next_pass(self):
        args, self._log_path = self._passes.pop(0)
        self._log_pos = 0
        self._stdout_tail = ""
        self.stats = UploadStats()
        self.bar_read.setValue(0)
        self.lbl_status.setText("Connecting to Immich…")
        self.proc = QProcess(self)
        qenv = QProcessEnvironment()
        for k, v in self._env.items():
            qenv.insert(k, v)
        self.proc.setProcessEnvironment(qenv)
        self.proc.readyReadStandardOutput.connect(self._read_stdout)
        self.proc.readyReadStandardError.connect(self._read_stderr)
        self.proc.finished.connect(self._on_finished)
        self.proc.errorOccurred.connect(self._on_error)
        self.proc.start(self._program, args)
        self._timer.start()

    def _reset_view(self):
        for bar in (self.bar_compress, self.bar_read):
            bar.setRange(0, 100)
            bar.setValue(0)
        self.bar_compress.setFormat("")
        self.bar_files.setRange(0, 1)
        self.bar_files.setValue(0)
        self._render()

    def _read_stdout(self):
        chunk = bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        # keep a tail so a progress line split across reads still matches
        self._stdout_tail = (self._stdout_tail + chunk)[-20000:]
        self.stats.feed_stdout(self._stdout_tail)
        self._render()

    def _read_stderr(self):
        chunk = bytes(self.proc.readAllStandardError()).decode("utf-8", "replace")
        self._stderr_tail = (self._stderr_tail + chunk)[-4000:]

    def _poll_log(self):
        if not self._log_path or not self._log_path.exists():
            return
        with self._log_path.open("r", encoding="utf-8", errors="replace") as f:
            f.seek(self._log_pos)
            data = f.read()
        complete, _, _rest = data.rpartition("\n")
        if not complete:
            return
        self._log_pos += len(complete.encode("utf-8")) + 1
        for line in complete.splitlines():
            self.stats.feed_log_line(line)
        self._render()

    def _total(self, key: str) -> int:
        return sum(getattr(s, key) for s in [*self._prev, self.stats])

    def _render(self):
        for key, lbl in self.stat_labels.items():
            lbl.setText(str(self._total(key)))
        found, done = self._total("found"), self._total("done")
        self.bar_read.setValue(self.stats.immich_read_pct)
        self.bar_files.setFormat("%v / %m files" if found else "")
        self.bar_files.setRange(0, max(found, 1))
        self.bar_files.setValue(min(done, max(found, 1)))
        if self.is_running() and not self._compressing and not self._canceled:
            if self.stats.immich_read_pct < 100:
                self.lbl_status.setText(
                    f"Checking what's already in Immich… found {found} files"
                )
            else:
                self.lbl_status.setText(f"Uploading… {done} of {found} files")

    def _on_error(self, err):
        if err == QProcess.ProcessError.FailedToStart:
            self._timer.stop()
            self._finish(
                False, "❌ Could not start immich-go. Check Binary Management."
            )

    def _on_finished(self, code: int, status):
        self._timer.stop()
        self._read_stdout()
        self._poll_log()
        clean = status == QProcess.ExitStatus.NormalExit and code == 0
        if clean and self._passes and not self._canceled:
            self._prev.append(self.stats)
            self._run_next_pass()
            return
        summary = (
            f"{self._total('uploaded')} uploaded, {self._total('duplicates')} "
            f"already in Immich, {self._total('errors')} errors"
        )
        ok = False
        if self._canceled:
            msg = f"⏹ Canceled. {summary}."
        elif clean and self._total("errors") == 0:
            ok = True
            self.bar_files.setValue(self.bar_files.maximum())
            msg = f"✅ Done. {summary}."
        elif clean:
            msg = f"⚠️ Finished with errors. {summary}. Log: {self._log_path}"
        else:
            last = self._stderr_tail.strip().splitlines()[-1:] or [f"exit code {code}"]
            msg = f"❌ immich-go failed: {last[0][:300]}\nLog: {self._log_path}"
        if self._compress and self._compress.message:
            msg += f"\n{self._compress.message}"
        self._finish(ok, msg)

    def _finish(self, ok: bool, msg: str):
        cleanup(self._compress)  # temp copies only; originals are never touched
        self._compress = None
        self._passes = []
        self.btn_cancel.setEnabled(False)
        self.lbl_status.setText(msg)
        self.finished.emit(ok)
