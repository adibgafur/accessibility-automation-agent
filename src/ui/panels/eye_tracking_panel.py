"""
Eye Tracking Panel for the UI.

Displays eye tracking status, calibration controls,
and cursor position visualization.
"""

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from loguru import logger

from .base_panel import BasePanel
from ..accessibility import get_button_size, get_ui_string


class EyeTrackingPanel(BasePanel):
    """
    Panel for eye tracking control and calibration.

    Displays:
    - Tracking status
    - Calibration controls
    - Blink detection status
    - Cursor position
    """

    tracking_toggled = pyqtSignal(bool)
    calibration_requested = pyqtSignal()

    def __init__(self, language: str = "en", parent=None):
        """Initialize eye tracking panel."""
        super().__init__(language=language, parent=parent)

        self.is_tracking = False
        self.is_calibrated = False

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        # Status section
        status_group = QGroupBox(self.get_ui_string("status"))
        status_layout = QVBoxLayout()

        self.tracking_status = QLabel("Not Tracking")
        self.tracking_status.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.tracking_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.tracking_status)

        status_group.setLayout(status_layout)
        self.layout.addWidget(status_group)

        # Calibration section
        calibration_group = QGroupBox("Calibration")
        calibration_layout = QVBoxLayout()

        self.calibrated_label = QLabel("Not Calibrated")
        self.calibrated_label.setFont(QFont("Arial", 12))
        calibration_layout.addWidget(self.calibrated_label)

        calibration_button_layout = QHBoxLayout()

        self.calibrate_button = QPushButton(self.get_ui_string("calibrate"))
        self.calibrate_button.setMinimumSize(*get_button_size())
        self.calibrate_button.clicked.connect(self._on_calibrate)
        calibration_button_layout.addWidget(self.calibrate_button)

        calibration_button_layout.addStretch()
        calibration_layout.addLayout(calibration_button_layout)

        calibration_group.setLayout(calibration_layout)
        self.layout.addWidget(calibration_group)

        # Features section
        features_group = QGroupBox("Features")
        features_layout = QVBoxLayout()

        self.blink_detect_check = QCheckBox("Enable Blink Detection (for clicking)")
        self.blink_detect_check.setChecked(True)
        self.blink_detect_check.setFont(QFont("Arial", 12))
        features_layout.addWidget(self.blink_detect_check)

        self.nose_track_check = QCheckBox("Enable Nose Tracking (as cursor)")
        self.nose_track_check.setChecked(True)
        self.nose_track_check.setFont(QFont("Arial", 12))
        features_layout.addWidget(self.nose_track_check)

        features_group.setLayout(features_layout)
        self.layout.addWidget(features_group)

        # Controls
        button_layout = QHBoxLayout()

        self.start_button = QPushButton(self.get_ui_string("start"))
        self.start_button.setMinimumSize(*get_button_size())
        self.start_button.clicked.connect(self._on_start_tracking)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton(self.get_ui_string("stop"))
        self.stop_button.setMinimumSize(*get_button_size())
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._on_stop_tracking)
        button_layout.addWidget(self.stop_button)

        button_layout.addStretch()
        self.layout.addLayout(button_layout)

        self.layout.addStretch()

    def _on_start_tracking(self) -> None:
        """Handle start tracking button click."""
        if not self.is_calibrated:
            self.tracking_status.setText("ERROR: Not calibrated")
            self.tracking_status.setStyleSheet("color: #FF3333;")
            logger.warning("Attempted to start tracking without calibration")
            return

        self.is_tracking = True
        self.tracking_status.setText("Tracking")
        self.tracking_status.setStyleSheet("color: #00DD00;")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.tracking_toggled.emit(True)
        logger.info("Eye tracking started (UI)")

    def _on_stop_tracking(self) -> None:
        """Handle stop tracking button click."""
        self.is_tracking = False
        self.tracking_status.setText("Not Tracking")
        self.tracking_status.setStyleSheet("color: inherit;")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.tracking_toggled.emit(False)
        logger.info("Eye tracking stopped (UI)")

    def _on_calibrate(self) -> None:
        """Handle calibration button click."""
        self.calibration_requested.emit()
        self.is_calibrated = True
        self.calibrated_label.setText("✓ Calibrated")
        self.calibrated_label.setStyleSheet("color: #00DD00;")
        logger.info("Eye tracking calibration requested (UI)")

    def get_status(self) -> str:
        """Get current status for status bar."""
        if self.is_tracking:
            return "👁 Tracking"
        return "Ready"


__all__ = ["EyeTrackingPanel"]
