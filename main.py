"""
Main entry point for the Accessibility Automation Agent application.

Initializes PyQt6 application and launches the main window.
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from loguru import logger

from src.ui.main_window import MainWindow
from src.ui.accessibility import Theme
from src.utils.logging_config import configure_logging


def main() -> int:
    """
    Main entry point for the application.

    Returns:
        Exit code (0 on success).
    """
    # Configure logging
    configure_logging()

    logger.info("=" * 80)
    logger.info("Accessibility Automation Agent - Starting")
    logger.info("=" * 80)

    # Create Qt application
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("Accessibility Automation Agent")
    app.setApplicationVersion("1.0.0")
    app.setStyle("Fusion")

    # Create main window
    try:
        main_window = MainWindow()
        main_window.show()
        logger.info("Main window created and shown")
    except Exception as e:
        logger.error(f"Failed to create main window: {e}", exc_info=True)
        return 1

    # Run application
    exit_code = app.exec()

    logger.info("=" * 80)
    logger.info(f"Accessibility Automation Agent - Shutting down (exit code: {exit_code})")
    logger.info("=" * 80)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
