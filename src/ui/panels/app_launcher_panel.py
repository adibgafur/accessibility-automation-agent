"""
Application Launcher Panel for the UI.

Displays installed applications and launch controls.
"""

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from loguru import logger

from .base_panel import BasePanel
from ..accessibility import get_button_size, get_ui_string


class AppLauncherPanel(BasePanel):
    """
    Panel for application launching.

    Displays:
    - List of installed applications
    - Search/filter
    - Launch button
    - Recently used apps
    """

    app_launch_requested = pyqtSignal(str)  # app_name

    def __init__(self, language: str = "en", parent=None):
        """Initialize app launcher panel."""
        super().__init__(language=language, parent=parent)

        self.apps = []

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        # Search section
        search_group = QGroupBox("Find Application")
        search_layout = QVBoxLayout()

        search_input_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name...")
        self.search_input.setFont(QFont("Arial", 12))
        self.search_input.setMinimumHeight(40)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_input_layout.addWidget(self.search_input)

        search_group.setLayout(search_layout)
        search_layout.addLayout(search_input_layout)
        self.layout.addWidget(search_group)

        # Apps list
        list_group = QGroupBox(get_ui_string("status", self.language))
        list_layout = QVBoxLayout()

        self.app_list = QListWidget()
        self.app_list.setMinimumHeight(250)
        list_layout.addWidget(self.app_list)

        list_button_layout = QHBoxLayout()

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setMinimumSize(*get_button_size())
        refresh_btn.clicked.connect(self._on_refresh_apps)
        list_button_layout.addWidget(refresh_btn)

        launch_btn = QPushButton("🚀 Launch")
        launch_btn.setMinimumSize(*get_button_size())
        launch_btn.clicked.connect(self._on_launch_app)
        list_button_layout.addWidget(launch_btn)

        list_button_layout.addStretch()
        list_layout.addLayout(list_button_layout)

        list_group.setLayout(list_layout)
        self.layout.addWidget(list_group)

        self.layout.addStretch()

    def _on_search_changed(self, text: str) -> None:
        """Filter apps list based on search text."""
        self.app_list.clear()

        search_text = text.lower()
        for app in self.apps:
            if search_text in app.lower():
                item = QListWidgetItem(app)
                self.app_list.addItem(item)

        logger.debug(f"App search: '{text}'")

    def _on_refresh_apps(self) -> None:
        """Refresh application list."""
        logger.info("App list refresh requested")

    def _on_launch_app(self) -> None:
        """Launch selected application."""
        selected_items = self.app_list.selectedItems()
        if not selected_items:
            logger.warning("No app selected for launch")
            return

        app_name = selected_items[0].text()
        self.app_launch_requested.emit(app_name)
        logger.info(f"App launch requested: {app_name}")

    def set_apps(self, apps: list) -> None:
        """
        Set the list of available applications.

        Args:
            apps: List of application names.
        """
        self.apps = sorted(apps)
        self.app_list.clear()

        for app in self.apps:
            item = QListWidgetItem(app)
            self.app_list.addItem(item)

        logger.info(f"App list updated: {len(apps)} apps")

    def get_status(self) -> str:
        """Get current status for status bar."""
        return f"Apps available: {len(self.apps)}"


__all__ = ["AppLauncherPanel"]
