"""In-app immich-go runner: background QProcess with live progress and Cancel."""

import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
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


class RunPanel(Card):
    finished = Signal(bool)  # True on success

    def __init__(self, parent=None):
        super().__init__("Upload Progress", parent=parent)
        self.setFixedWidth(340)
        self.proc: QProcess | None = None
        self.stats = UploadStats()
        self._log_path: Path | None = None
        self._log_pos = 0
        self._stdout_tail = ""
        self._stderr_tail = ""
        self._canceled = False

        self.lbl_status = QLabel("Ready. Pick a folder and click Run Command.")
        self.lbl_status.setWordWrap(True)
        self.layout.addWidget(self.lbl_status)

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

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._poll_log)
        self._reset_view()

    def is_running(self) -> bool:
        return (
            self.proc is not None
            and self.proc.state() != QProcess.ProcessState.NotRunning
        )

    def start(
        self, program: str, args: list[str], env: dict[str, str], log_path: Path
    ) -> None:
        self.stats = UploadStats()
        self._log_path, self._log_pos = log_path, 0
        self._stdout_tail = self._stderr_tail = ""
        self._canceled = False
        self._reset_view()
        self.lbl_status.setText("Connecting to Immich…")

        self.proc = QProcess(self)
        qenv = QProcessEnvironment()
        for k, v in env.items():
            qenv.insert(k, v)
        self.proc.setProcessEnvironment(qenv)
        self.proc.readyReadStandardOutput.connect(self._read_stdout)
        self.proc.readyReadStandardError.connect(self._read_stderr)
        self.proc.finished.connect(self._on_finished)
        self.proc.errorOccurred.connect(self._on_error)
        self.proc.start(program, args)
        self.btn_cancel.setEnabled(True)
        self._timer.start()

    def cancel(self) -> None:
        if not self.is_running():
            return
        self._canceled = True
        self.lbl_status.setText("Canceling…")
        # immich-go exits cleanly (report, resumes paused Immich jobs) on Ctrl+C
        # but dies abruptly on SIGTERM, so send SIGINT where available.
        if sys.platform.startswith("win"):
            self.proc.terminate()
        else:
            os.kill(self.proc.processId(), signal.SIGINT)
        QTimer.singleShot(10000, lambda: self.is_running() and self.proc.kill())

    def _reset_view(self):
        self.bar_read.setRange(0, 100)
        self.bar_read.setValue(0)
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

    def _render(self):
        s = self.stats
        for key, lbl in self.stat_labels.items():
            lbl.setText(str(getattr(s, key)))
        self.bar_read.setValue(s.immich_read_pct)
        self.bar_files.setFormat("%v / %m files" if s.found else "")
        self.bar_files.setRange(0, max(s.found, 1))
        self.bar_files.setValue(min(s.done, max(s.found, 1)))
        if self.is_running() and not self._canceled:
            if s.immich_read_pct < 100:
                self.lbl_status.setText(
                    f"Checking what's already in Immich… found {s.found} files"
                )
            else:
                self.lbl_status.setText(f"Uploading… {s.done} of {s.found} files")

    def _on_error(self, err):
        if err == QProcess.ProcessError.FailedToStart:
            self._timer.stop()
            self.btn_cancel.setEnabled(False)
            self.lbl_status.setText(
                "❌ Could not start immich-go. Check Binary Management."
            )
            self.finished.emit(False)

    def _on_finished(self, code: int, status):
        self._timer.stop()
        self._read_stdout()
        self._poll_log()
        self.btn_cancel.setEnabled(False)
        s = self.stats
        summary = f"{s.uploaded} uploaded, {s.duplicates} already in Immich, {s.errors} errors"
        ok = False
        if self._canceled:
            msg = f"⏹ Canceled. {summary}."
        elif status == QProcess.ExitStatus.NormalExit and code == 0 and s.errors == 0:
            ok = True
            self.bar_files.setValue(self.bar_files.maximum())
            msg = f"✅ Done. {summary}."
        elif status == QProcess.ExitStatus.NormalExit and code == 0:
            msg = f"⚠️ Finished with errors. {summary}. Log: {self._log_path}"
        else:
            last = self._stderr_tail.strip().splitlines()[-1:] or [f"exit code {code}"]
            msg = f"❌ immich-go failed: {last[0][:300]}\nLog: {self._log_path}"
        self.lbl_status.setText(msg)
        self.finished.emit(ok)
