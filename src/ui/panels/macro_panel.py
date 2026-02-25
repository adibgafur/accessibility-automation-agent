"""
Macro System Panel for the UI.

Displays macro recording, playback, listing,
and management controls.
"""

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QDoubleSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from loguru import logger

from .base_panel import BasePanel
from ..accessibility import get_button_size


class MacroSystemPanel(BasePanel):
    """
    Panel for macro recording and playback.

    Displays:
    - Recording controls
    - Playback controls
    - Macro list
    - Speed control
    - Loop control
    """

    recording_toggled = pyqtSignal(bool)
    playback_requested = pyqtSignal(str, float, int)  # macro_name, speed, loop_count
    macro_deleted = pyqtSignal(str)

    def __init__(self, language: str = "en", parent=None):
        """Initialize macro panel."""
        super().__init__(language=language, parent=parent)

        self.is_recording = False
        self.is_playing = False

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        # Recording section
        record_group = QGroupBox("Recording")
        record_layout = QVBoxLayout()

        self.record_status = QLabel("Ready to record")
        self.record_status.setFont(QFont("Arial", 12))
        record_layout.addWidget(self.record_status)

        record_button_layout = QHBoxLayout()

        self.start_record_btn = QPushButton(self.get_ui_string("record"))
        self.start_record_btn.setMinimumSize(*get_button_size())
        self.start_record_btn.clicked.connect(self._on_start_recording)
        record_button_layout.addWidget(self.start_record_btn)

        self.stop_record_btn = QPushButton(self.get_ui_string("stop"))
        self.stop_record_btn.setMinimumSize(*get_button_size())
        self.stop_record_btn.setEnabled(False)
        self.stop_record_btn.clicked.connect(self._on_stop_recording)
        record_button_layout.addWidget(self.stop_record_btn)

        record_button_layout.addStretch()
        record_layout.addLayout(record_button_layout)

        record_group.setLayout(record_layout)
        self.layout.addWidget(record_group)

        # Macro list
        list_group = QGroupBox("Saved Macros")
        list_layout = QVBoxLayout()

        self.macro_list = QListWidget()
        self.macro_list.setMinimumHeight(150)
        list_layout.addWidget(self.macro_list)

        list_button_layout = QHBoxLayout()

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setMinimumSize(*get_button_size())
        refresh_btn.clicked.connect(self._on_refresh_list)
        list_button_layout.addWidget(refresh_btn)

        delete_btn = QPushButton("🗑 Delete")
        delete_btn.setMinimumSize(*get_button_size())
        delete_btn.clicked.connect(self._on_delete_macro)
        list_button_layout.addWidget(delete_btn)

        list_button_layout.addStretch()
        list_layout.addLayout(list_button_layout)

        list_group.setLayout(list_layout)
        self.layout.addWidget(list_group)

        # Playback controls
        playback_group = QGroupBox("Playback")
        playback_layout = QVBoxLayout()

        # Speed control
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setValue(1.0)
        self.speed_spin.setRange(0.1, 10.0)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setMinimumHeight(40)
        speed_layout.addWidget(self.speed_spin)

        speed_layout.addWidget(QLabel("x"))
        speed_layout.addStretch()
        playback_layout.addLayout(speed_layout)

        # Loop control
        loop_layout = QHBoxLayout()
        loop_layout.addWidget(QLabel("Loop Count:"))

        self.loop_spin = QSpinBox()
        self.loop_spin.setValue(1)
        self.loop_spin.setRange(0, 100)
        self.loop_spin.setMinimumHeight(40)
        loop_layout.addWidget(self.loop_spin)

        loop_layout.addWidget(QLabel("(0 = infinite)"))
        loop_layout.addStretch()
        playback_layout.addLayout(loop_layout)

        # Playback button
        playback_button_layout = QHBoxLayout()

        self.play_btn = QPushButton(self.get_ui_string("play"))
        self.play_btn.setMinimumSize(*get_button_size())
        self.play_btn.clicked.connect(self._on_play_macro)
        playback_button_layout.addWidget(self.play_btn)

        self.stop_play_btn = QPushButton(self.get_ui_string("stop"))
        self.stop_play_btn.setMinimumSize(*get_button_size())
        self.stop_play_btn.setEnabled(False)
        self.stop_play_btn.clicked.connect(self._on_stop_playback)
        playback_button_layout.addWidget(self.stop_play_btn)

        playback_button_layout.addStretch()
        playback_layout.addLayout(playback_button_layout)

        playback_group.setLayout(playback_layout)
        self.layout.addWidget(playback_group)

        self.layout.addStretch()

    def _on_start_recording(self) -> None:
        """Handle start recording."""
        self.is_recording = True
        self.record_status.setText("🔴 Recording...")
        self.record_status.setStyleSheet("color: #FF3333;")
        self.start_record_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(True)
        self.recording_toggled.emit(True)
        logger.info("Macro recording started (UI)")

    def _on_stop_recording(self) -> None:
        """Handle stop recording."""
        self.is_recording = False
        self.record_status.setText("Stopped - Save your macro")
        self.record_status.setStyleSheet("color: inherit;")
        self.start_record_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(False)
        self.recording_toggled.emit(False)
        logger.info("Macro recording stopped (UI)")

    def _on_play_macro(self) -> None:
        """Handle play macro."""
        selected_items = self.macro_list.selectedItems()
        if not selected_items:
            logger.warning("No macro selected for playback")
            return

        macro_name = selected_items[0].text()
        speed = self.speed_spin.value()
        loop_count = self.loop_spin.value()

        self.is_playing = True
        self.play_btn.setEnabled(False)
        self.stop_play_btn.setEnabled(True)

        self.playback_requested.emit(macro_name, speed, loop_count)
        logger.info(f"Macro playback requested: {macro_name} (speed={speed}, loops={loop_count})")

    def _on_stop_playback(self) -> None:
        """Handle stop playback."""
        self.is_playing = False
        self.play_btn.setEnabled(True)
        self.stop_play_btn.setEnabled(False)
        logger.info("Macro playback stopped (UI)")

    def _on_refresh_list(self) -> None:
        """Refresh the macro list (to be called with actual macro data)."""
        logger.info("Macro list refresh requested")

    def _on_delete_macro(self) -> None:
        """Delete selected macro."""
        selected_items = self.macro_list.selectedItems()
        if not selected_items:
            logger.warning("No macro selected for deletion")
            return

        macro_name = selected_items[0].text()
        self.macro_list.takeItem(self.macro_list.row(selected_items[0]))
        self.macro_deleted.emit(macro_name)
        logger.info(f"Macro deleted: {macro_name}")

    def add_macro_to_list(self, macro_name: str) -> None:
        """Add macro to the list."""
        item = QListWidgetItem(macro_name)
        self.macro_list.addItem(item)

    def get_status(self) -> str:
        """Get current status for status bar."""
        if self.is_recording:
            return "🔴 Recording macro"
        if self.is_playing:
            return "▶ Playing macro"
        return "Ready"


__all__ = ["MacroSystemPanel"]
