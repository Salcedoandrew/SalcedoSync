from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import QCheckBox, QMessageBox

from core.network import test_immich_connection


class _NetSignals(QObject):
    """Carries a worker's result back to the GUI thread."""

    done = Signal(str, int, object)  # kind, sequence number, result


class _NetTask(QRunnable):
    def __init__(self, signals, kind, seq, fn) -> None:
        super().__init__()
        self._args = (signals, kind, seq, fn)

    def run(self) -> None:
        signals, kind, seq, fn = self._args
        signals.done.emit(kind, seq, fn())


class ConnectionMixin:
    def _run_net(self, kind: str, fn, on_result) -> None:
        """Run blocking network call fn() off the UI thread.

        on_result(result) runs on the GUI thread, and only for the newest
        request of this kind; stale results are dropped.
        """
        if not hasattr(self, "_net_signals"):
            self._net_signals = _NetSignals()
            self._net_signals.done.connect(self._on_net_done)
            self._net_seq, self._net_cb = {}, {}
        seq = self._net_seq.get(kind, 0) + 1
        self._net_seq[kind] = seq
        self._net_cb[kind] = on_result
        QThreadPool.globalInstance().start(_NetTask(self._net_signals, kind, seq, fn))

    def _drop_pending_net(self, kind: str) -> None:
        if hasattr(self, "_net_seq"):
            self._net_seq[kind] = self._net_seq.get(kind, 0) + 1

    def _on_net_done(self, kind: str, seq: int, result) -> None:
        if seq == self._net_seq.get(kind):
            self._net_cb.pop(kind)(result)

    def on_test_connection_clicked(self):
        srv_widget = self.inputs.get("config", {}).get("server")
        api_widget = self.inputs.get("config", {}).get("api_key")
        ssl_widget = self.inputs.get("config", {}).get("skip-ssl")

        server_url = srv_widget.text().strip() if srv_widget else ""
        api_key = api_widget.text().strip() if api_widget else ""
        skip_ssl = ssl_widget.isChecked() if ssl_widget else False

        if not server_url:
            QMessageBox.warning(
                self, "Test Connection", "Please enter a Server URL first."
            )
            return
        if not api_key:
            QMessageBox.warning(
                self, "Test Connection", "Please enter an API Key first."
            )
            return

        self.btn_test_connection.setEnabled(False)
        self._run_net(
            "manual",
            lambda: test_immich_connection(server_url, api_key, skip_ssl=skip_ssl),
            self._on_manual_test_result,
        )

    def _on_manual_test_result(self, res):
        self.btn_test_connection.setEnabled(True)
        if res.ok:
            self._last_conn_test_ok = True
            QMessageBox.information(self, "Test Connection Succeeded", res.message)
        else:
            self._last_conn_test_ok = False
            QMessageBox.warning(self, "Test Connection Failed", res.message)
        self.update_status()

    def _auto_test_connection(self):
        """Silent background test — updates status card only, no popup."""
        srv = self.server_url_edit.text().strip()
        key = self.api_key_edit.text().strip()
        if not srv or not key:
            self._drop_pending_net("auto")
            self._last_conn_test_ok = None
            self.update_status()
            return
        skip_ssl = self.inputs["config"].get("skip-ssl", QCheckBox()).isChecked()
        self._run_net(
            "auto",
            lambda: test_immich_connection(srv, key, skip_ssl=skip_ssl, timeout=4.0),
            self._on_auto_test_result,
        )

    def _on_auto_test_result(self, res):
        self._last_conn_test_ok = res.ok
        self.update_status()
