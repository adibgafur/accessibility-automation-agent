"""
Mouse Control Panel for the UI.

Displays mouse position, click types, drag controls,
and recording status.
"""

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from loguru import logger

from .base_panel import BasePanel
from ..accessibility import get_button_size


class MouseControlPanel(BasePanel):
    """
    Panel for mouse control.

    Displays:
    - Current cursor position
    - Click type selector
    - Drag controls
    - Recording status
    """

    click_requested = pyqtSignal(str)  # click_type
    drag_requested = pyqtSignal(str)  # direction
    recording_toggled = pyqtSignal(bool)

    def __init__(self, language: str = "en", parent=None):
        """Initialize mouse panel."""
        super().__init__(language=language, parent=parent)

        self.is_recording = False
        self.cursor_x = 0
        self.cursor_y = 0

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        # Position display
        position_group = QGroupBox("Cursor Position")
        position_layout = QVBoxLayout()

        self.position_label = QLabel("Position: (0, 0)")
        self.position_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        position_layout.addWidget(self.position_label)

        position_group.setLayout(position_layout)
        self.layout.addWidget(position_group)

        # Click type selector
        click_group = QGroupBox("Click Type")
        click_layout = QVBoxLayout()

        self.click_type_combo = QComboBox()
        self.click_type_combo.addItems([
            "Left Click",
            "Right Click",
            "Double Click",
        ])
        click_layout.addWidget(self.click_type_combo)

        click_button_layout = QHBoxLayout()

        self.click_button = QPushButton(self.get_ui_string("start"))
        self.click_button.setMinimumSize(*get_button_size())
        self.click_button.clicked.connect(self._on_click)
        click_button_layout.addWidget(self.click_button)

        click_button_layout.addStretch()
        click_layout.addLayout(click_button_layout)

        click_group.setLayout(click_layout)
        self.layout.addWidget(click_group)

        # Drag controls
        drag_group = QGroupBox("Drag")
        drag_layout = QVBoxLayout()

        drag_button_layout = QHBoxLayout()

        for direction in ["Left", "Right", "Up", "Down"]:
            btn = QPushButton(direction)
            btn.setMinimumSize(*get_button_size())
            btn.clicked.connect(
                lambda checked, d=direction.lower(): self._on_drag(d)
            )
            drag_button_layout.addWidget(btn)

        drag_layout.addLayout(drag_button_layout)

        drag_group.setLayout(drag_layout)
        self.layout.addWidget(drag_group)

        # Recording section
        recording_group = QGroupBox("Action Recording")
        recording_layout = QVBoxLayout()

        self.recording_status = QLabel("Not Recording")
        self.recording_status.setFont(QFont("Arial", 12))
        recording_layout.addWidget(self.recording_status)

        recording_button_layout = QHBoxLayout()

        self.record_button = QPushButton(self.get_ui_string("record"))
        self.record_button.setMinimumSize(*get_button_size())
        self.record_button.clicked.connect(self._on_toggle_recording)
        recording_button_layout.addWidget(self.record_button)

        recording_button_layout.addStretch()
        recording_layout.addLayout(recording_button_layout)

        recording_group.setLayout(recording_layout)
        self.layout.addWidget(recording_group)

        self.layout.addStretch()

    def _on_click(self) -> None:
        """Handle click button."""
        click_type = self.click_type_combo.currentText().lower()
        self.click_requested.emit(click_type)
        logger.info(f"Click requested: {click_type}")

    def _on_drag(self, direction: str) -> None:
        """Handle drag buttons."""
        self.drag_requested.emit(direction)
        logger.info(f"Drag requested: {direction}")

    def _on_toggle_recording(self) -> None:
        """Toggle action recording."""
        self.is_recording = not self.is_recording

        if self.is_recording:
            self.recording_status.setText("🔴 Recording...")
            self.recording_status.setStyleSheet("color: #FF3333;")
            self.record_button.setText(self.get_ui_string("stop"))
        else:
            self.recording_status.setText("Stopped")
            self.recording_status.setStyleSheet("color: inherit;")
            self.record_button.setText(self.get_ui_string("record"))

        self.recording_toggled.emit(self.is_recording)
        logger.info(f"Recording toggled: {self.is_recording}")

    def update_position(self, x: int, y: int) -> None:
        """Update cursor position display."""
        self.cursor_x = x
        self.cursor_y = y
        self.position_label.setText(f"Position: ({x}, {y})")

    def get_status(self) -> str:
        """Get current status for status bar."""
        if self.is_recording:
            return "🔴 Recording actions"
        return "Ready"


__all__ = ["MouseControlPanel"]
