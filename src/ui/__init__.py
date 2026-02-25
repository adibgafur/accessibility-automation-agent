"""
UI modules for the Accessibility Automation Agent.

Provides the PyQt6 accessible graphical interface with accessibility
styling, main window, and panels for all automation features.
Implemented in Phase 9.

Modules:
    - accessibility: High-contrast themes, styling, localization
    - main_window: Main application window with tabbed interface
    - panels: Individual UI panels for each feature
"""

from .accessibility import (
    Theme,
    get_stylesheet,
    get_ui_string,
    get_accessible_font,
)
from .main_window import MainWindow

__all__ = [
    "Theme",
    "get_stylesheet",
    "get_ui_string",
    "get_accessible_font",
    "MainWindow",
]
