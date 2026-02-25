"""
Base Panel Class for UI Panels.

Provides a common interface for all automation panels with
support for theme switching, language changes, and status reporting.
"""

from typing import Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from loguru import logger

from ..accessibility import Theme, get_ui_string


class BasePanel(QWidget):
    """
    Base class for all UI panels.

    Provides:
    - Theme switching support
    - Language switching support
    - Status reporting interface
    - Standard layout setup
    """

    def __init__(self, language: str = "en", parent: Optional[QWidget] = None):
        """
        Initialize base panel.

        Args:
            language: Language code ("en" or "bn").
            parent: Parent widget.
        """
        super().__init__(parent)

        self.language = language
        self.current_theme = Theme.DARK

        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)

        logger.debug(f"BasePanel initialized | language={language}")

    def update_theme(self, theme: Theme) -> None:
        """
        Update panel theme.

        Args:
            theme: The new theme.
        """
        self.current_theme = theme
        logger.debug(f"Panel theme updated to: {theme.value}")

    def update_language(self, language: str) -> None:
        """
        Update panel language.

        Args:
            language: Language code ("en" or "bn").
        """
        self.language = language
        logger.debug(f"Panel language updated to: {language}")

    def get_status(self) -> str:
        """
        Get current panel status for status bar.

        Returns:
            Status string.
        """
        return get_ui_string("ready", self.language)

    def get_ui_string(self, key: str) -> str:
        """
        Get localized UI string for current language.

        Args:
            key: String key.

        Returns:
            Localized string.
        """
        return get_ui_string(key, self.language)


__all__ = ["BasePanel"]
