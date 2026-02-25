"""
Main Application Window for the Accessibility Automation Agent.

Provides the top-level PyQt6 interface with tabbed panels for all
automation features. Supports voice commands, keyboard navigation,
and high-contrast accessibility.

Features:
    - Tabbed interface for all panels
    - Status bar with current state
    - Menu bar with application controls
    - Keyboard shortcuts for all actions
    - Voice command integration
    - Theme switching
    - Language switching (English/Bengali)
"""

from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QStatusBar,
    QMenuBar,
    QMenu,
    QDialog,
    QLabel,
    QComboBox,
    QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon, QFont

from loguru import logger

from .accessibility import (
    Theme,
    get_stylesheet,
    get_ui_string,
    get_button_size,
)
from .panels.voice_panel import VoiceControlPanel
from .panels.eye_tracking_panel import EyeTrackingPanel
from .panels.mouse_panel import MouseControlPanel
from .panels.browser_panel import BrowserAutomationPanel
from .panels.macro_panel import MacroSystemPanel
from .panels.app_launcher_panel import AppLauncherPanel
from .panels.settings_panel import SettingsPanel


class MainWindow(QMainWindow):
    """
    Main application window with tabbed interface.

    Signals:
        theme_changed: Emitted when theme is changed.
        language_changed: Emitted when language is changed.
        quit_requested: Emitted when quit is requested.
    """

    theme_changed = pyqtSignal(Theme)
    language_changed = pyqtSignal(str)
    quit_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize main window.

        Args:
            parent: Parent widget (typically None).
        """
        super().__init__(parent)

        self.current_theme = Theme.DARK
        self.current_language = "en"

        # Initialize UI
        self._init_ui()
        self._init_menu_bar()
        self._init_status_bar()

        # Set window properties
        self.setWindowTitle(get_ui_string("app_title", self.current_language))
        self.setMinimumSize(1200, 800)

        # Apply theme
        self.set_theme(self.current_theme)

        logger.info(
            f"MainWindow created | theme={self.current_theme.value} | "
            f"language={self.current_language}"
        )

    def _init_ui(self) -> None:
        """Initialize the main UI with tabbed panels."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        layout.addWidget(self.tab_widget)

        # Create panels
        self.voice_panel = VoiceControlPanel(language=self.current_language)
        self.eye_tracking_panel = EyeTrackingPanel(language=self.current_language)
        self.mouse_panel = MouseControlPanel(language=self.current_language)
        self.browser_panel = BrowserAutomationPanel(language=self.current_language)
        self.macro_panel = MacroSystemPanel(language=self.current_language)
        self.app_launcher_panel = AppLauncherPanel(language=self.current_language)
        self.settings_panel = SettingsPanel(language=self.current_language)

        # Add panels to tabs
        self.tab_widget.addTab(
            self.voice_panel,
            get_ui_string("voice_control", self.current_language),
        )
        self.tab_widget.addTab(
            self.eye_tracking_panel,
            get_ui_string("eye_tracking", self.current_language),
        )
        self.tab_widget.addTab(
            self.mouse_panel,
            get_ui_string("mouse_control", self.current_language),
        )
        self.tab_widget.addTab(
            self.browser_panel,
            get_ui_string("browser_automation", self.current_language),
        )
        self.tab_widget.addTab(
            self.macro_panel,
            get_ui_string("macro_system", self.current_language),
        )
        self.tab_widget.addTab(
            self.app_launcher_panel,
            get_ui_string("app_launcher", self.current_language),
        )
        self.tab_widget.addTab(
            self.settings_panel,
            get_ui_string("settings", self.current_language),
        )

        logger.info("All UI panels created and added to tab widget")

    def _init_menu_bar(self) -> None:
        """Initialize the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")
        
        quit_action = QAction(
            get_ui_string("quit", self.current_language),
            self,
        )
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self._on_quit)
        file_menu.addAction(quit_action)

        # View menu
        view_menu = menubar.addMenu("View")
        
        theme_menu = view_menu.addMenu(get_ui_string("theme", self.current_language))
        for theme in Theme:
            theme_action = QAction(theme.value.replace("_", " ").title(), self)
            theme_action.triggered.connect(
                lambda checked, t=theme: self.set_theme(t)
            )
            theme_menu.addAction(theme_action)

        language_menu = view_menu.addMenu(
            get_ui_string("language", self.current_language)
        )
        for lang_code, lang_name in [("en", "English"), ("bn", "বাংলা")]:
            lang_action = QAction(lang_name, self)
            lang_action.triggered.connect(
                lambda checked, l=lang_code: self.set_language(l)
            )
            language_menu.addAction(lang_action)

        # Help menu
        help_menu = menubar.addMenu(get_ui_string("help", self.current_language))
        help_action = QAction("About", self)
        help_action.triggered.connect(self._show_about)
        help_menu.addAction(help_action)

        logger.info("Menu bar initialized")

    def _init_status_bar(self) -> None:
        """Initialize the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel(
            get_ui_string("ready", self.current_language)
        )
        self.status_bar.addWidget(self.status_label)

        # Update status periodically
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)  # Update every 1 second

        logger.info("Status bar initialized")

    def set_theme(self, theme: Theme) -> None:
        """
        Set the application theme.

        Args:
            theme: The theme to apply.
        """
        self.current_theme = theme
        stylesheet = get_stylesheet(theme)
        self.setStyleSheet(stylesheet)

        # Update all panels with new theme
        for panel in [
            self.voice_panel,
            self.eye_tracking_panel,
            self.mouse_panel,
            self.browser_panel,
            self.macro_panel,
            self.app_launcher_panel,
            self.settings_panel,
        ]:
            if hasattr(panel, "update_theme"):
                panel.update_theme(theme)

        self.theme_changed.emit(theme)
        logger.info(f"Theme changed to: {theme.value}")

    def set_language(self, language: str) -> None:
        """
        Set the application language.

        Args:
            language: Language code ("en" or "bn").
        """
        if language not in ("en", "bn"):
            logger.warning(f"Unknown language: {language}, using en")
            language = "en"

        self.current_language = language

        # Update window title
        self.setWindowTitle(get_ui_string("app_title", language))

        # Update all panels with new language
        for panel in [
            self.voice_panel,
            self.eye_tracking_panel,
            self.mouse_panel,
            self.browser_panel,
            self.macro_panel,
            self.app_launcher_panel,
            self.settings_panel,
        ]:
            if hasattr(panel, "update_language"):
                panel.update_language(language)

        self.language_changed.emit(language)
        logger.info(f"Language changed to: {language}")

    def _update_status(self) -> None:
        """Update the status bar with current state."""
        # Collect status from active panel
        current_panel = self.tab_widget.currentWidget()

        if hasattr(current_panel, "get_status"):
            status_text = current_panel.get_status()
            self.status_label.setText(status_text)

    def _on_quit(self) -> None:
        """Handle quit action."""
        self.quit_requested.emit()
        self.close()

    def _show_about(self) -> None:
        """Show about dialog."""
        about_text = f"""
        <h2>Accessibility Automation Agent</h2>
        <p>Version 1.0.0</p>
        <p>A comprehensive accessibility automation tool for users without hands.</p>
        <p>
        Features:
        <ul>
            <li>Voice control (English + Bengali)</li>
            <li>Nose/eye tracking</li>
            <li>Browser automation</li>
            <li>GUI automation (UFO2 + GUIrilla)</li>
            <li>Macro recording/playback</li>
            <li>App launcher</li>
        </ul>
        </p>
        <p>License: MIT</p>
        <p><a href="https://github.com/adibgafur/accessibility-automation-agent">
        GitHub Repository</a></p>
        """

        dialog = QDialog(self)
        dialog.setWindowTitle("About")
        layout = QVBoxLayout(dialog)

        label = QLabel(about_text)
        label.setOpenExternalLinks(True)
        layout.addWidget(label)

        close_button = QPushButton(get_ui_string("quit", self.current_language))
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)

        dialog.setMinimumSize(600, 400)
        dialog.exec()

    def closeEvent(self, event):
        """Handle window close event."""
        self.status_timer.stop()
        self.quit_requested.emit()
        super().closeEvent(event)


__all__ = ["MainWindow"]
