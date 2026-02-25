"""
Voice Control Panel for the UI.

Displays voice recognition status, transcribed text,
confidence levels, and language selection.
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QComboBox,
    QGroupBox,
    QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

from loguru import logger

from .base_panel import BasePanel
from ..accessibility import Theme, get_ui_string, get_button_size


class VoiceControlPanel(BasePanel):
    """
    Panel for voice control with real-time feedback.

    Displays:
    - Listening status
    - Transcribed text
    - Confidence level
    - Language selector
    - Recognized command
    """

    listening_toggled = pyqtSignal(bool)
    language_changed = pyqtSignal(str)

    def __init__(self, language: str = "en", parent=None):
        """Initialize voice control panel."""
        super().__init__(language=language, parent=parent)

        self.is_listening = False
        self.last_transcription = ""
        self.confidence = 0.0

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        # Status section
        status_group = QGroupBox(self.get_ui_string("listening"))
        status_layout = QVBoxLayout()

        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_label)

        # Confidence bar
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setValue(0)
        status_layout.addWidget(QLabel("Confidence:"))
        status_layout.addWidget(self.confidence_bar)

        status_group.setLayout(status_layout)
        self.layout.addWidget(status_group)

        # Transcription section
        transcript_group = QGroupBox(self.get_ui_string("recording"))
        transcript_layout = QVBoxLayout()

        self.transcript_text = QTextEdit()
        self.transcript_text.setReadOnly(True)
        self.transcript_text.setMinimumHeight(120)
        self.transcript_text.setFont(QFont("Arial", 12))
        transcript_layout.addWidget(QLabel("Last Transcription:"))
        transcript_layout.addWidget(self.transcript_text)

        transcript_group.setLayout(transcript_layout)
        self.layout.addWidget(transcript_group)

        # Command section
        command_group = QGroupBox("Recognized Command")
        command_layout = QVBoxLayout()

        self.command_label = QLabel("None")
        self.command_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        command_layout.addWidget(QLabel("Last Command:"))
        command_layout.addWidget(self.command_label)

        command_group.setLayout(command_layout)
        self.layout.addWidget(command_group)

        # Language selection
        language_layout = QHBoxLayout()
        language_layout.addWidget(QLabel(self.get_ui_string("language")))

        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("বাংলা (Bangla)", "bn")
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        language_layout.addWidget(self.language_combo)
        language_layout.addStretch()

        self.layout.addLayout(language_layout)

        # Control buttons
        button_layout = QHBoxLayout()

        self.start_button = QPushButton(self.get_ui_string("start"))
        self.start_button.setMinimumSize(*get_button_size())
        self.start_button.clicked.connect(self._on_start_listening)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton(self.get_ui_string("stop"))
        self.stop_button.setMinimumSize(*get_button_size())
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._on_stop_listening)
        button_layout.addWidget(self.stop_button)

        button_layout.addStretch()
        self.layout.addLayout(button_layout)

        self.layout.addStretch()

    def _on_start_listening(self) -> None:
        """Handle start listening button click."""
        self.is_listening = True
        self.update_status("listening")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.listening_toggled.emit(True)
        logger.info("Voice listening started (UI)")

    def _on_stop_listening(self) -> None:
        """Handle stop listening button click."""
        self.is_listening = False
        self.update_status("ready")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.listening_toggled.emit(False)
        logger.info("Voice listening stopped (UI)")

    def _on_language_changed(self) -> None:
        """Handle language combo box change."""
        language_code = self.language_combo.currentData()
        self.language_changed.emit(language_code)
        logger.info(f"Voice language changed to: {language_code}")

    def update_transcription(self, text: str, confidence: float = 1.0) -> None:
        """
        Update the transcription display.

        Args:
            text: Transcribed text.
            confidence: Confidence level (0.0 - 1.0).
        """
        self.last_transcription = text
        self.confidence = confidence

        self.transcript_text.setText(f"{text}\n(Confidence: {confidence:.1%})")
        self.confidence_bar.setValue(int(confidence * 100))

        logger.debug(f"Transcription updated: '{text}' (confidence={confidence})")

    def update_command(self, command_name: str) -> None:
        """
        Update the recognized command display.

        Args:
            command_name: Name of recognized command.
        """
        self.command_label.setText(command_name)
        logger.debug(f"Command updated: {command_name}")

    def update_status(self, status: str) -> None:
        """
        Update the status display.

        Args:
            status: Status string key.
        """
        status_text = self.get_ui_string(status) if status in [
            "listening", "ready", "recording", "error"
        ] else status

        self.status_label.setText(status_text)

        # Update color based on status
        if status == "listening":
            self.status_label.setStyleSheet("color: #00DD00;")  # Green
        elif status == "error":
            self.status_label.setStyleSheet("color: #FF3333;")  # Red
        else:
            self.status_label.setStyleSheet("color: inherit;")

    def get_status(self) -> str:
        """Get current status for status bar."""
        if self.is_listening:
            return "🎤 Listening..."
        return "Ready"


__all__ = ["VoiceControlPanel"]
