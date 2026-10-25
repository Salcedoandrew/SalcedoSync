from core import (
    SERVER_REQUIRED_TABS,
    ValidationResult,
    collect_safety_warnings,
    is_lock_active,
    normalize_server_url,
    validate_state,
    validate_state_light,
)


class StatusMixin:
    def validate_inputs(self) -> ValidationResult:
        tab_key = self._get_active_tab_key()
        if tab_key == "config":
            return ValidationResult()

        config_state = self._collect_config_state()
        tab_state = self._collect_tab_state(tab_key)
        advanced_state = self._collect_advanced_state(tab_key)

        base = validate_state(
            tab_key=tab_key,
            config_state=config_state,
            tab_state=tab_state,
        )

        from core.advanced_flags import validate_advanced_state

        adv = validate_advanced_state(tab_key, advanced_state)

        base.errors.extend(adv.errors)
        base.warnings.extend(adv.warnings)
        return base

    def validate_inputs_light(self) -> ValidationResult:
        tab_key = self._get_active_tab_key()
        if tab_key == "config":
            return ValidationResult()

        config_state = self._collect_config_state()
        tab_state = self._collect_tab_state(tab_key)
        advanced_state = self._collect_advanced_state(tab_key)

        base = validate_state_light(
            tab_key=tab_key,
            config_state=config_state,
            tab_state=tab_state,
        )

        from core.advanced_flags import validate_advanced_state

        adv = validate_advanced_state(tab_key, advanced_state)

        base.errors.extend(adv.errors)
        base.warnings.extend(adv.warnings)
        base.warnings.extend(
            collect_safety_warnings(tab_key, config_state, advanced_state)
        )
        return base

    def _reset_conn_test_state(self):
        self._last_conn_test_ok = None
        self._drop_pending_net("auto")  # an in-flight test is for the old text
        self._schedule_status_update()

    def _schedule_status_update(self):
        self._status_debounce.start()

    def update_status(self):
        """Immediate status refresh for programmatic calls (tab switches, run state)."""
        self._do_update_status()

    def _do_update_status(self):
        active_paths = getattr(self, "active_lock_paths", set())
        if not active_paths and getattr(self, "active_lock_path", None):
            active_paths = {self.active_lock_path}
        is_running = (
            any(is_lock_active(p) for p in active_paths)
            or getattr(self, "running_process", False) is True
            or (hasattr(self, "run_panel") and self.run_panel.is_running())
        )
        validation = self.validate_inputs_light()
        active_tab = self._get_active_tab_key()
        self._apply_field_errors(active_tab, validation.field_errors)

        if is_running:
            self.lbl_running_warning.setVisible(True)
            self.btn_run.setEnabled(False)
        else:
            self.lbl_running_warning.setVisible(False)

        last_test = getattr(self, "_last_conn_test_ok", None)

        if last_test is False and active_tab in ("config", *SERVER_REQUIRED_TABS):
            self.status_card.set_server("err", "Server: Connection Failed")
            if not is_running and active_tab in SERVER_REQUIRED_TABS:
                self.btn_run.setEnabled(False)
        elif last_test is True and active_tab == "config":
            self.status_card.set_server("ok", "Server: Connected")
        elif active_tab == "config":
            srv_widget = self.inputs.get("config", {}).get("server")
            api_widget = self.inputs.get("config", {}).get("api_key")
            srv_text = srv_widget.text().strip() if srv_widget else ""
            key_text = api_widget.text().strip() if api_widget else ""
            if srv_text and key_text:
                self.status_card.set_server("ok", "Server: Configured")
            else:
                self.status_card.set_server("err", "Server: Not Set")
        elif validation.warnings and not validation.errors:
            self.status_card.set_server("warn", validation.warnings[0])
            if not is_running:
                self.btn_run.setEnabled(True)
        elif validation.is_valid:
            self.status_card.set_server("ok", "Server: Ready")
            if not is_running:
                self.btn_run.setEnabled(True)
        else:
            first_error = (
                validation.errors[0] if validation.errors else "Server: Not Set"
            )
            self.status_card.set_server("err", f"Server: {first_error}")
            if not is_running:
                self.btn_run.setEnabled(False)

        srv_edit = self.inputs.get("config", {}).get("server")
        srv = normalize_server_url(srv_edit.text()) if srv_edit else ""
        for t in ["archive-immich", "stack"]:
            if t in self.inputs and "target-server" in self.inputs[t]:
                self.inputs[t]["target-server"].setText(
                    srv if srv else "Not Configured"
                )
