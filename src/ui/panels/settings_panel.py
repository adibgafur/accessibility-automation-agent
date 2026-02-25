"""
Settings Panel for the UI.

Displays application settings, preferences,
and configuration options.
"""

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QComboBox,
    QCheckBox,
    QSlider,
    QSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from loguru import logger

from .base_panel import BasePanel
from ..accessibility import Theme, get_button_size, get_ui_string


class SettingsPanel(BasePanel):
    """
    Panel for application settings and preferences.

    Displays:
    - Theme selector
    - Language selector
    - Volume control
    - Microphone selector
    - Accessibility options
    - About information
    """

    theme_changed = pyqtSignal(str)
    language_changed = pyqtSignal(str)
    volume_changed = pyqtSignal(int)

    def __init__(self, language: str = "en", parent=None):
        """Initialize settings panel."""
        super().__init__(language=language, parent=parent)

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        # Appearance section
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QVBoxLayout()

        # Theme selector
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel(self.get_ui_string("theme")))

        self.theme_combo = QComboBox()
        self.theme_combo.addItems([
            "Light",
            "Dark",
            "High Contrast",
        ])
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.theme_combo.setMinimumHeight(40)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()

        appearance_layout.addLayout(theme_layout)

        appearance_group.setLayout(appearance_layout)
        self.layout.addWidget(appearance_group)

        # Language section
        language_group = QGroupBox(self.get_ui_string("language"))
        language_layout = QVBoxLayout()

        lang_layout = QHBoxLayout()
        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("বাংলা (Bangla)", "bn")
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        self.language_combo.setMinimumHeight(40)
        lang_layout.addWidget(self.language_combo)
        lang_layout.addStretch()

        language_layout.addLayout(lang_layout)

        language_group.setLayout(language_layout)
        self.layout.addWidget(language_group)

        # Audio section
        audio_group = QGroupBox("Audio Settings")
        audio_layout = QVBoxLayout()

        # Volume control
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel(self.get_ui_string("volume")))

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMinimumHeight(40)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        volume_layout.addWidget(self.volume_slider)

        self.volume_label = QLabel("70%")
        volume_layout.addWidget(self.volume_label)

        audio_layout.addLayout(volume_layout)

        # Microphone selector
        mic_layout = QHBoxLayout()
        mic_layout.addWidget(QLabel("Microphone:"))

        self.mic_combo = QComboBox()
        self.mic_combo.addItem("Default")
        self.mic_combo.setMinimumHeight(40)
        mic_layout.addWidget(self.mic_combo)
        mic_layout.addStretch()

        audio_layout.addLayout(mic_layout)

        audio_group.setLayout(audio_layout)
        self.layout.addWidget(audio_group)

        # Accessibility section
        access_group = QGroupBox("Accessibility")
        access_layout = QVBoxLayout()

        self.high_contrast_check = QCheckBox("Enable High Contrast Mode")
        self.high_contrast_check.setFont(QFont("Arial", 12))
        access_layout.addWidget(self.high_contrast_check)

        self.large_text_check = QCheckBox("Large Text (18pt minimum)")
        self.large_text_check.setFont(QFont("Arial", 12))
        access_layout.addWidget(self.large_text_check)

        self.keyboard_nav_check = QCheckBox("Keyboard Navigation Only")
        self.keyboard_nav_check.setFont(QFont("Arial", 12))
        access_layout.addWidget(self.keyboard_nav_check)

        self.screen_reader_check = QCheckBox("Screen Reader Optimization")
        self.screen_reader_check.setFont(QFont("Arial", 12))
        access_layout.addWidget(self.screen_reader_check)

        access_group.setLayout(access_layout)
        self.layout.addWidget(access_group)

        # System section
        system_group = QGroupBox("System")
        system_layout = QVBoxLayout()

        button_layout = QHBoxLayout()

        reset_btn = QPushButton("↻ Reset to Defaults")
        reset_btn.setMinimumSize(*get_button_size())
        reset_btn.clicked.connect(self._on_reset_settings)
        button_layout.addWidget(reset_btn)

        about_btn = QPushButton("ℹ About")
        about_btn.setMinimumSize(*get_button_size())
        about_btn.clicked.connect(self._on_about)
        button_layout.addWidget(about_btn)

        button_layout.addStretch()
        system_layout.addLayout(button_layout)

        system_group.setLayout(system_layout)
        self.layout.addWidget(system_group)

        self.layout.addStretch()

    def _on_theme_changed(self) -> None:
        """Handle theme combo change."""
        theme_name = self.theme_combo.currentText().lower().replace(" ", "_")
        self.theme_changed.emit(theme_name)
        logger.info(f"Theme changed: {theme_name}")

    def _on_language_changed(self) -> None:
        """Handle language combo change."""
        language_code = self.language_combo.currentData()
        self.language_changed.emit(language_code)
        logger.info(f"Language changed: {language_code}")

    def _on_volume_changed(self, value: int) -> None:
        """Handle volume slider change."""
        self.volume_label.setText(f"{value}%")
        self.volume_changed.emit(value)
        logger.debug(f"Volume changed: {value}%")

    def _on_reset_settings(self) -> None:
        """Reset all settings to defaults."""
        self.theme_combo.setCurrentIndex(1)  # Dark
        self.language_combo.setCurrentIndex(0)  # English
        self.volume_slider.setValue(70)
        self.high_contrast_check.setChecked(False)
        self.large_text_check.setChecked(False)
        self.keyboard_nav_check.setChecked(False)
        self.screen_reader_check.setChecked(False)
        logger.info("Settings reset to defaults")

    def _on_about(self) -> None:
        """Show about information."""
        logger.info("About dialog requested")

    def get_status(self) -> str:
        """Get current status for status bar."""
        return f"Theme: {self.theme_combo.currentText()}"


__all__ = ["SettingsPanel"]
