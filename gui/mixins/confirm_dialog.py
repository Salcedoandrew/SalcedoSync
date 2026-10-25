from PySide6.QtWidgets import QMessageBox

from core import SERVER_REQUIRED_TABS
from core.network import check_preflight_server_connection


class ConfirmDialogMixin:
    def show_confirm_dialog(self, is_dry_run: bool):
        if self.stacked_widget.currentIndex() == 0:
            return

        ready, msg = self.check_binary_ready()
        if not ready:
            reply = QMessageBox.question(
                self,
                "Binary Not Ready",
                f"{msg}\n\nDo you want to download it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if not self.update_binary(force_download=True):
                    return
                ready, msg = self.check_binary_ready()
                if not ready:
                    QMessageBox.critical(self, "Error", msg)
                    return
            else:
                return

        validation = self.validate_inputs()
        active_tab = self._get_active_tab_key()
        self._apply_field_errors(active_tab, validation.field_errors)
        if validation.errors:
            QMessageBox.warning(
                self,
                "Validation Errors",
                "\n".join(f"• {e}" for e in validation.errors),
            )
            return

        plan = self.build_plan(dry_run=is_dry_run)
        if plan.errors:
            QMessageBox.critical(
                self, "Command Build Errors", "\n".join(f"• {e}" for e in plan.errors)
            )
            return

        if plan.tab_key in SERVER_REQUIRED_TABS:
            config_state = self._collect_config_state()
            tab_state = self._collect_tab_state(plan.tab_key)
            # Check the server off the UI thread; the run continues in
            # _after_preflight. A newer Run click supersedes this one.
            self._run_net(
                "preflight",
                lambda: check_preflight_server_connection(
                    plan.tab_key, config_state, tab_state, timeout=3.0
                ),
                lambda conn_res: self._after_preflight(plan, conn_res),
            )
            return

        # No confirmation dialog: start immediately (progress shows in-app).
        self.run_command(plan)

    def _after_preflight(self, plan, conn_res):
        if not conn_res.ok:
            reply = QMessageBox.warning(
                self,
                "Server Unreachable",
                f"Immich server connection check failed:\n\n{conn_res.message}\n\n"
                f"Running immich-go will likely fail because the server cannot be reached.\n\n"
                f"Do you want to proceed anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            plan.warnings.insert(
                0, f"Server pre-flight check failed: {conn_res.message}"
            )
        self.run_command(plan)
