import os
import sys
import tempfile
import time
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from core import (
    TAB_COMMANDS,
    CommandPlan,
    build_plan_from_state,
    create_lock,
    get_binary_path,
    load_binary_metadata,
    release_lock,
)
from core.command_builder import collect_paths
from core.compression import (
    IMG_EXCL,
    CompressResult,
    ban_file_args,
    find_caesiumclt,
)
from core.terminal_launcher import launch_external_terminal


class ExecutionMixin:
    def build_plan(self, dry_run: bool) -> CommandPlan:
        tab_key = self._get_active_tab_key()
        if tab_key == "config":
            return CommandPlan(errors=["No executable tab selected."], tab_key=tab_key)

        config_state = self._collect_config_state()
        tab_state = self._collect_tab_state(tab_key)
        advanced_state = self._collect_advanced_state(tab_key)

        binary_path = getattr(self, "binary_path", "")
        if not binary_path:
            binary_path = get_binary_path(load_binary_metadata()) or "./immich-go"

        return build_plan_from_state(
            tab_key=tab_key,
            config_state=config_state,
            tab_state=tab_state,
            binary_path=binary_path,
            dry_run=dry_run,
            advanced_state=advanced_state,
        )

    def build_command(self, dry_run: bool) -> list[str]:
        """Backwards-compatible wrapper returning plan.argv."""
        return self.build_plan(dry_run).argv

    def run_command(self, plan: CommandPlan):
        if plan.errors:
            QMessageBox.critical(
                self, "Command Build Errors", "\n".join(f"• {e}" for e in plan.errors)
            )
            return

        binary_path = plan.binary_path or getattr(self, "binary_path", "./immich-go")
        try:
            resolved = Path(binary_path).expanduser().resolve()
            if resolved.is_file():
                binary_path = str(resolved)
        except OSError:
            resolved = Path(binary_path)

        if not os.path.isfile(binary_path) and not self.update_binary():
            QMessageBox.critical(
                self, "Error", "Immich-Go binary is missing or not executable."
            )
            return

        if not sys.platform.startswith("win") and not os.access(binary_path, os.X_OK):
            QMessageBox.critical(
                self, "Error", "Immich-Go binary exists but is not executable."
            )
            return

        plan.binary_path = binary_path

        if plan.tab_key.startswith("upload-"):
            self._run_in_background(plan)
            return

        if hasattr(self, "log"):
            self.log.info(
                "Launching: tab=%s argv=%s env_keys=%s",
                plan.tab_key,
                plan.display_argv,
                sorted(plan.env.keys()),
            )

        summary = f"{plan.tab_key}"
        if plan.argv:
            summary = " ".join(plan.argv[:3])

        lock_path = create_lock(
            tab_key=plan.tab_key,
            command_summary=summary,
            binary_path=binary_path,
        )

        pref_term = getattr(self.app_config, "preferred_terminal", "auto")
        full_cmd = [binary_path] + plan.argv

        res = launch_external_terminal(
            command=full_cmd,
            env=plan.env,
            lock_path=lock_path,
            preferred_terminal=pref_term,
        )

        if not res.ok:
            release_lock(lock_path)
            QMessageBox.critical(self, "Error Launching Terminal", res.message)
            self.btn_run.setEnabled(True)
            return

        self.active_lock_paths = {lock_path}
        self.active_lock_path = lock_path
        self.running_process = True
        self.btn_run.setEnabled(False)
        self._start_process_timer()
        self.update_status()

    def _run_in_background(self, plan: CommandPlan):
        """Run immich-go as a child process; progress shows in self.run_panel."""
        log_dir = Path(tempfile.gettempdir()) / "immich-go-gui-logs"
        log_dir.mkdir(exist_ok=True)
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        log_path = log_dir / f"upload_{stamp}.log"
        n = len(TAB_COMMANDS.get(plan.tab_key, ()))
        argv = [a for a in plan.argv if a != "--no-ui"]
        tab_state = self._collect_tab_state(plan.tab_key)
        paths = collect_paths(str(tab_state.get("path", "")).strip())
        base = argv[: len(argv) - len(paths)] if argv[-len(paths) :] == paths else argv

        def cmd(log: Path, extra: list[str], srcs: list[str]) -> list[str]:
            # --no-ui gives a plain progress line; --log-file gives per-file
            # events. Flags must precede the positional path argument.
            return (
                base[:n] + ["--no-ui", "--log-file", str(log)] + base[n:] + extra + srcs
            )

        compress = None
        if plan.tab_key == "upload-folder" and tab_state.get("compress"):
            caesium = find_caesiumclt()
            if not caesium:
                QMessageBox.warning(
                    self,
                    "Compress images",
                    "Image compression needs the caesiumclt tool, which wasn't found "
                    "in this app. Untick 'Compress images' to upload the originals.",
                )
                return
            if len(paths) == 1 and Path(paths[0]).is_dir():
                src = paths[0]

                def make_passes(res: CompressResult):
                    # Same passes as Immich Upload (paired RAW skipped).
                    ban = ban_file_args(res.paired_raw)
                    if res.upload_dir and res.single_pass:
                        return [(cmd(log_path, [], [str(res.upload_dir)]), log_path)]
                    if res.upload_dir:
                        photos_log = log_dir / f"upload_{stamp}-photos.log"
                        return [
                            (cmd(photos_log, [], [str(res.upload_dir)]), photos_log),
                            (
                                cmd(
                                    log_path,
                                    ["--exclude-extensions", IMG_EXCL, *ban],
                                    [src],
                                ),
                                log_path,
                            ),
                        ]
                    return [(cmd(log_path, ban, [src]), log_path)]

                compress = (
                    Path(src),
                    caesium,
                    log_dir / f"compress_{stamp}.log",
                    make_passes,
                )
        if hasattr(self, "log"):
            self.log.info(
                "Background run: tab=%s argv=%s compress=%s",
                plan.tab_key,
                plan.display_argv,
                bool(compress),
            )
        passes = [] if compress else [(cmd(log_path, [], paths), log_path)]
        self.running_process = True
        self.btn_run.setEnabled(False)
        self.run_panel.start(plan.binary_path, passes, plan.env, compress)
        self.update_status()

    def _on_background_finished(self, ok: bool):
        self.running_process = False
        self.update_status()
