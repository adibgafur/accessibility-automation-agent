"""
Browser Automation Panel for the UI.

Displays browser controls, search, navigation,
and tab management.
"""

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QLineEdit,
    QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from loguru import logger

from .base_panel import BasePanel
from ..accessibility import get_button_size


class BrowserAutomationPanel(BasePanel):
    """
    Panel for browser automation.

    Displays:
    - Browser selector
    - Search controls
    - Navigation buttons
    - Tab management
    - Form input controls
    """

    search_requested = pyqtSignal(str)  # search term
    navigate_requested = pyqtSignal(str)  # url or command
    tab_action_requested = pyqtSignal(str)  # action (new, close, next, prev)

    def __init__(self, language: str = "en", parent=None):
        """Initialize browser panel."""
        super().__init__(language=language, parent=parent)

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        # Browser selector
        browser_group = QGroupBox("Browser Selection")
        browser_layout = QVBoxLayout()

        self.browser_combo = QComboBox()
        self.browser_combo.addItems([
            "Chrome",
            "Firefox",
            "Edge",
        ])
        browser_layout.addWidget(QLabel("Choose Browser:"))
        browser_layout.addWidget(self.browser_combo)

        browser_group.setLayout(browser_layout)
        self.layout.addWidget(browser_group)

        # Search section
        search_group = QGroupBox("Search")
        search_layout = QVBoxLayout()

        search_input_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search term...")
        self.search_input.setFont(QFont("Arial", 12))
        self.search_input.setMinimumHeight(40)
        search_input_layout.addWidget(self.search_input)

        search_button = QPushButton(self.get_ui_string("start"))
        search_button.setMinimumSize(*get_button_size())
        search_button.clicked.connect(self._on_search)
        search_input_layout.addWidget(search_button)

        search_layout.addLayout(search_input_layout)

        search_group.setLayout(search_layout)
        self.layout.addWidget(search_group)

        # Navigation section
        nav_group = QGroupBox("Navigation")
        nav_layout = QVBoxLayout()

        nav_button_layout = QHBoxLayout()

        back_btn = QPushButton("← Back")
        back_btn.setMinimumSize(*get_button_size())
        back_btn.clicked.connect(lambda: self._on_navigate("back"))
        nav_button_layout.addWidget(back_btn)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setMinimumSize(*get_button_size())
        refresh_btn.clicked.connect(lambda: self._on_navigate("refresh"))
        nav_button_layout.addWidget(refresh_btn)

        forward_btn = QPushButton("Forward →")
        forward_btn.setMinimumSize(*get_button_size())
        forward_btn.clicked.connect(lambda: self._on_navigate("forward"))
        nav_button_layout.addWidget(forward_btn)

        nav_layout.addLayout(nav_button_layout)

        nav_group.setLayout(nav_layout)
        self.layout.addWidget(nav_group)

        # Tab management
        tab_group = QGroupBox("Tab Management")
        tab_layout = QVBoxLayout()

        tab_button_layout = QHBoxLayout()

        new_tab = QPushButton("+New Tab")
        new_tab.setMinimumSize(*get_button_size())
        new_tab.clicked.connect(lambda: self._on_tab_action("new"))
        tab_button_layout.addWidget(new_tab)

        prev_tab = QPushButton("← Prev")
        prev_tab.setMinimumSize(*get_button_size())
        prev_tab.clicked.connect(lambda: self._on_tab_action("prev"))
        tab_button_layout.addWidget(prev_tab)

        next_tab = QPushButton("Next →")
        next_tab.setMinimumSize(*get_button_size())
        next_tab.clicked.connect(lambda: self._on_tab_action("next"))
        tab_button_layout.addWidget(next_tab)

        close_tab = QPushButton("✕ Close")
        close_tab.setMinimumSize(*get_button_size())
        close_tab.clicked.connect(lambda: self._on_tab_action("close"))
        tab_button_layout.addWidget(close_tab)

        tab_layout.addLayout(tab_button_layout)

        tab_group.setLayout(tab_layout)
        self.layout.addWidget(tab_group)

        self.layout.addStretch()

    def _on_search(self) -> None:
        """Handle search button."""
        search_term = self.search_input.text()
        if search_term:
            self.search_requested.emit(search_term)
            logger.info(f"Search requested: {search_term}")

    def _on_navigate(self, action: str) -> None:
        """Handle navigation."""
        self.navigate_requested.emit(action)
        logger.info(f"Navigation: {action}")

    def _on_tab_action(self, action: str) -> None:
        """Handle tab action."""
        self.tab_action_requested.emit(action)
        logger.info(f"Tab action: {action}")

    def get_status(self) -> str:
        """Get current status for status bar."""
        return f"Browser: {self.browser_combo.currentText()}"


__all__ = ["BrowserAutomationPanel"]
