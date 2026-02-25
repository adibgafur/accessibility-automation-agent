"""
Accessibility Automation Agent - Main Entry Point.

Bootstraps the application:
    1. Parse command-line arguments
    2. Initialise logging
    3. Load configuration
    4. Launch PyQt6 UI (Phase 9) or headless mode

Usage:
    python -m src.main
    python -m src.main --language bn --log-level DEBUG
    python -m src.main --headless
"""

import sys
import argparse
from pathlib import Path

from loguru import logger

from utils.logging_config import setup_logging
from utils.config_manager import config
from utils.error_handler import (
    AccessibilityAgentError,
    ErrorRecoveryHandler,
)
from utils.accessibility_helpers import notifier
from app_controller import ApplicationController


# ------------------------------------------------------------------
# Version
# ------------------------------------------------------------------
__version__ = "0.1.0"


# ------------------------------------------------------------------
# CLI argument parser
# ------------------------------------------------------------------

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        prog="accessibility-agent",
        description=(
            "Accessibility Automation Agent - "
            "AI-powered desktop automation for users without hands"
        ),
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging verbosity (default: INFO)",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to a custom configuration YAML file",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without the graphical UI (voice + tracking only)",
    )

    parser.add_argument(
        "--language",
        choices=["en", "bn"],
        default="en",
        help="UI and voice language: en = English, bn = Bengali (default: en)",
    )

    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="Disable text-to-speech audio feedback",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser.parse_args()


# ------------------------------------------------------------------
# Application bootstrap
# ------------------------------------------------------------------

def main() -> None:
    """Main application entry point."""

    # 1. Parse arguments
    args = parse_arguments()

    # 2. Initialise logging
    setup_logging(level=args.log_level)
    logger.info("=" * 60)
    logger.info(f"  Accessibility Automation Agent v{__version__}")
    logger.info("=" * 60)

    try:
        # 3. Load / reload configuration
        config.reload()

        # Apply CLI overrides to config
        config.set("ui.language", args.language)
        if args.no_tts:
            config.set("accessibility.text_to_speech", False)

        logger.info(f"Language : {args.language}")
        logger.info(f"TTS      : {'disabled' if args.no_tts else 'enabled'}")
        logger.info(f"Headless : {args.headless}")

        # 4. Audio greeting
        if not args.no_tts:
            notifier.notify("Accessibility Automation Agent is starting", "info")

        # 5. Validate critical config keys
        missing = config.validate([
            "voice.whisper_model",
            "eye_tracking.camera_index",
            "gui_detection.primary_engine",
        ])
        if missing:
            logger.warning(f"Missing configuration keys (using defaults): {missing}")

        # 6. Launch UI or headless mode
        if args.headless:
            _run_headless()
        else:
            _run_gui(args)

    except AccessibilityAgentError as exc:
        logger.error(f"Application error: {exc.message}")
        ErrorRecoveryHandler.handle_error(exc)
        notifier.speak_error(exc.message)
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Application interrupted by user (Ctrl+C)")
        notifier.notify("Application stopped", "info")
        sys.exit(0)

    except Exception as exc:
        logger.critical(
            f"Unexpected error: {type(exc).__name__}: {exc}",
            exc_info=True,
        )
        notifier.speak_error("An unexpected error occurred. Check the logs.")
        sys.exit(1)


# ------------------------------------------------------------------
# Run modes
# ------------------------------------------------------------------

def _run_gui(args: argparse.Namespace) -> None:
    """
    Launch the PyQt6 graphical interface (Phase 9) with integration (Phase 10).

    Initializes the ApplicationController and launches the main UI window.
    """
    logger.info("Launching graphical user interface with Phase 10 integration...")

    try:
        from PyQt6.QtWidgets import QApplication
        from ui.main_window import MainWindow
        from optimization import ResourceManager

        # Create Qt application
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        # Initialize resource manager for optimization
        resource_mgr = ResourceManager()
        resource_mgr.startup()
        logger.info("Resource optimization started")

        # Create and initialize application controller
        controller = ApplicationController()
        if not controller.startup():
            logger.error("Failed to initialize application controller")
            notifier.speak_error("Failed to start application. Check logs.")
            return

        logger.info("Application controller initialized successfully")

        # Create and show main window
        window = MainWindow(language=args.language, controller=controller)
        window.show()

        logger.info("Main window displayed - application ready")
        notifier.notify(f"Accessibility Automation Agent started in {args.language}", "info")

        # Run event loop
        sys.exit(app.exec())

    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        notifier.speak_error("Failed to load UI components.")
        return
    except Exception as e:
        logger.error(f"GUI initialization error: {e}", exc_info=True)
        notifier.speak_error("An error occurred while starting the application.")
        raise


def _run_headless() -> None:
    """
    Run without UI - voice and eye-tracking only (Phase 10 integrated).

    Operates the application controller in headless mode with voice commands
    and eye tracking only.
    """
    logger.info("Running in headless mode with Phase 10 integration...")

    try:
        from optimization import ResourceManager

        # Initialize resource manager
        resource_mgr = ResourceManager()
        resource_mgr.startup()
        logger.info("Resource optimization started")

        # Create and initialize application controller
        controller = ApplicationController()
        if not controller.startup():
            logger.error("Failed to initialize application controller")
            notifier.speak_error("Failed to start application. Check logs.")
            return

        logger.info("Application controller initialized for headless mode")

        # Start voice listening
        if not controller.start_listening():
            logger.error("Failed to start voice listening")
            notifier.speak_error("Voice listening failed. Check microphone.")
            controller.shutdown()
            return

        # Start eye tracking if available
        if not controller.start_tracking():
            logger.warning("Eye tracking not available, continuing without it")

        logger.info("Headless mode active - waiting for voice commands")
        notifier.notify("Headless mode started. Ready for voice commands.", "info")

        # Main event loop - wait for KeyboardInterrupt
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Headless mode interrupted by user")

    except Exception as e:
        logger.error(f"Headless mode error: {e}", exc_info=True)
        notifier.speak_error("An error occurred in headless mode.")
        raise
    finally:
        if "controller" in locals():
            controller.shutdown()
            logger.info("Application controller shutdown")
        if "resource_mgr" in locals():
            resource_mgr.shutdown()
            logger.info("Resource management shutdown")


# ------------------------------------------------------------------
# Script entry
# ------------------------------------------------------------------

if __name__ == "__main__":
    main()
