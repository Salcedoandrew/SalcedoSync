"""System tray icon for the Monitor subsystem.

Provides a QSystemTrayIcon with status-aware icons, context menu,
balloon notifications, and minimize-to-tray behavior.
"""

from pathlib import Path

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class TrayManager:
    """Manages the system tray icon and its context menu."""

    def __init__(self, window, app_icon_path: str = "", fallback_icon_path: str = ""):
        self._window = window
        self._app_icon_path = app_icon_path
        self._fallback_icon_path = fallback_icon_path
        self._icon_style = "colorful"
        self._app_icon = self._resolve_icon(app_icon_path, fallback_icon_path)

        self.tray_available = bool(
            QSystemTrayIcon.isSystemTrayAvailable()
            and self._app_icon is not None
            and not self._app_icon.isNull()
        )

        self._tray = QSystemTrayIcon(window)
        if self._app_icon:
            self._tray.setIcon(self._app_icon)

        self._tray.setToolTip("SalcedoSync — Idle")

        # Context menu
        self._menu = QMenu()
        self._status_action = QAction("Status: Idle")
        self._status_action.setEnabled(False)
        self._menu.addAction(self._status_action)
        self._menu.addSeparator()

        self._open_action = QAction("Open SalcedoSync")
        self._open_action.triggered.connect(self._show_window)
        self._menu.addAction(self._open_action)

        self._menu.addSeparator()

        # Tray Icon Style Submenu
        self._style_menu = QMenu("Tray Icon Style", self._menu)
        from PySide6.QtGui import QActionGroup

        self._style_group = QActionGroup(self._style_menu)
        self._style_group.setExclusive(True)

        styles = [
            ("Colorful (Default)", "colorful"),
            ("Monochrome - Auto (System)", "monochrome-system"),
            ("Monochrome - Light Taskbar", "monochrome-light"),
            ("Monochrome - Dark Taskbar", "monochrome-dark"),
        ]

        self._style_actions: dict[str, QAction] = {}
        for label, style_key in styles:
            action = QAction(label, self._style_menu)
            action.setCheckable(True)
            if style_key == "colorful":
                action.setChecked(True)
            action.setData(style_key)
            action.triggered.connect(
                lambda _, k=style_key: self._on_menu_style_triggered(k)
            )
            self._style_group.addAction(action)
            self._style_menu.addAction(action)
            self._style_actions[style_key] = action

        self._menu.addMenu(self._style_menu)

        self._menu.addSeparator()
        self._quit_action = QAction("Quit")
        self._quit_action.triggered.connect(self._quit_app)
        self._menu.addAction(self._quit_action)

        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_tray_activated)

        # A QSystemTrayIcon without an icon is invisible on Windows, and on
        # platforms without a system tray show() is pointless.  Only show
        # when the tray is actually available and an icon was resolved.
        if self.tray_available:
            self._tray.show()

    def _on_menu_style_triggered(self, style_key: str) -> None:
        """Handle selection of tray icon style directly from the tray right-click menu."""
        self.update_icon_style(style_key)
        if hasattr(self._window, "monitor_config"):
            self._window.monitor_config.tray_icon_style = style_key
        if hasattr(self._window, "tray_icon_style_combo"):
            combo = self._window.tray_icon_style_combo
            combo.blockSignals(True)
            idx = combo.findData(style_key)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)
        if hasattr(self._window, "_save_monitor_state"):
            self._window._save_monitor_state()

    def update_icon_style(
        self, style: str = "colorful", active_theme: str | None = None
    ) -> None:
        """Update tray icon to colorful or themed monochrome mode."""
        self._icon_style = style
        if hasattr(self, "_style_actions") and style in self._style_actions:
            self._style_actions[style].setChecked(True)
        if style == "colorful":
            icon = self._resolve_icon(self._app_icon_path, self._fallback_icon_path)
        else:
            from theme import detect_system_theme, load_themed_icon

            if style == "monochrome-light":
                theme = "light"
            elif style == "monochrome-dark":
                theme = "dark"
            else:
                theme = active_theme or detect_system_theme()
            icon = load_themed_icon("app-monochrome", theme)
            if not icon or icon.isNull():
                icon = self._resolve_icon(self._app_icon_path, self._fallback_icon_path)

        if icon and not icon.isNull():
            self._app_icon = icon
            self._tray.setIcon(icon)

        self.tray_available = bool(
            QSystemTrayIcon.isSystemTrayAvailable()
            and self._app_icon is not None
            and not self._app_icon.isNull()
        )

    @staticmethod
    def _resolve_icon(app_icon_path: str, fallback_icon_path: str) -> QIcon | None:
        """Resolve the tray icon, falling back so it is never icon-less."""
        for candidate in (app_icon_path, fallback_icon_path):
            if candidate and Path(candidate).is_file():
                return QIcon(candidate)
        app_icon = QApplication.windowIcon()
        if app_icon and not app_icon.isNull():
            return app_icon
        return None

    def set_status(self, text: str) -> None:
        """Update tray tooltip and status menu item."""
        self._status_action.setText(f"Status: {text}")
        self._tray.setToolTip(f"SalcedoSync — {text}")

    def notify(
        self, title: str, message: str, icon_type: str = "info", duration_ms: int = 5000
    ) -> None:
        """Show a balloon notification."""
        icon = QSystemTrayIcon.MessageIcon.Information
        if icon_type == "warning":
            icon = QSystemTrayIcon.MessageIcon.Warning
        elif icon_type == "error":
            icon = QSystemTrayIcon.MessageIcon.Critical

        self._tray.showMessage(title, message, icon, duration_ms)

    def set_minimize_to_tray(self, enabled: bool) -> None:
        """Enable or disable minimize-to-tray behavior."""
        self._minimize_to_tray = bool(enabled and self.tray_available)

    def handle_close(self, event) -> bool:
        """Handle window close event. Returns True if handled (i.e., hidden to tray)."""
        if self._minimize_to_tray:
            self._window.hide()
            self._tray.showMessage(
                "SalcedoSync",
                "Minimized to tray. Right-click the tray icon to quit.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
            event.ignore()
            return True
        return False

    def _show_window(self) -> None:
        """Show and raise the main window."""
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _quit_app(self) -> None:
        """Quit the application."""
        # Force close flag to skip confirmation
        self._window._force_close = True
        self._window.close()
        QApplication.instance().quit()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon click/double-click."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def shutdown(self) -> None:
        """Clean up the tray icon."""
        self._tray.hide()
        if self._tray.contextMenu():
            self._tray.contextMenu().deleteLater()
