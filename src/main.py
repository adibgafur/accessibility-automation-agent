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
    Launch the PyQt6 graphical interface.

    Will be fully implemented in Phase 9.
    """
    logger.info("Launching graphical user interface...")

    # TODO: Phase 9 implementation
    # from PyQt6.QtWidgets import QApplication
    # from ui.main_window import MainWindow
    #
    # app = QApplication(sys.argv)
    # window = MainWindow(language=args.language)
    # window.show()
    # sys.exit(app.exec())

    logger.info("GUI launch deferred to Phase 9 - application will exit")
    notifier.notify("GUI will be available after Phase 9 implementation", "info")


def _run_headless() -> None:
    """
    Run without UI - voice and eye-tracking only.

    Will be fully implemented after core modules are complete.
    """
    logger.info("Running in headless mode...")

    # TODO: Phase 4+ implementation
    # from core.voice_engine import VoiceEngine
    # from core.eye_tracker import EyeTracker
    # from core.mouse_controller import MouseController
    #
    # voice = VoiceEngine(language=config.get("ui.language", "en"))
    # voice.load_model()
    # voice.start_listening()
    #
    # tracker = EyeTracker()
    # tracker.start()
    #
    # mouse = MouseController()
    #
    # # Main event loop
    # while True:
    #     pos = tracker.get_nose_position()
    #     if pos:
    #         mouse.move_to(*pos)
    #     if tracker.detect_blink():
    #         mouse.click()

    logger.info("Headless mode deferred to Phase 4+ - application will exit")
    notifier.notify("Headless mode will be available after Phase 4", "info")


# ------------------------------------------------------------------
# Script entry
# ------------------------------------------------------------------

if __name__ == "__main__":
    main()
