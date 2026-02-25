"""
Application Controller - Main coordinator for all automation modules.

Orchestrates communication between UI, voice control, eye tracking,
GUI automation, browser control, macro system, and app launcher.

Features:
    - Central coordination of all automation modules
    - Event-driven architecture for real-time feedback
    - Error recovery and fallback mechanisms
    - Lazy loading of expensive modules
    - Resource management (cleanup on shutdown)
    - Multi-threaded operation for responsiveness
    - Configuration management
    - Logging of all operations
"""

import threading
from typing import Optional, Dict, Any, Callable, List
from pathlib import Path
from enum import Enum

from loguru import logger
from PyQt6.QtCore import QObject, pyqtSignal

from src.core.voice_engine import VoiceEngine
from src.core.voice_commands import (
    VoiceCommandParser,
    CommandRegistry,
    CommandCategory,
)
from src.core.eye_tracker import EyeTracker
from src.core.mouse_controller import MouseController
from src.automation.browser_controller import BrowserController
from src.automation.macro_system import MacroManager
from src.automation.app_launcher import AppLauncher
from src.utils.config_manager import config
from src.utils.error_handler import AutomationError


class ApplicationState(Enum):
    """Application operational states."""

    IDLE = "idle"
    LISTENING = "listening"
    TRACKING = "tracking"
    RECORDING = "recording"
    EXECUTING = "executing"
    ERROR = "error"


class ApplicationController(QObject):
    """
    Main application controller coordinating all modules.

    Signals:
        state_changed: Emitted when application state changes.
        error_occurred: Emitted when an error occurs.
        status_updated: Emitted when status changes.
        action_completed: Emitted when an action completes.
    """

    state_changed = pyqtSignal(ApplicationState)
    error_occurred = pyqtSignal(str)  # error_message
    status_updated = pyqtSignal(str)  # status_message
    action_completed = pyqtSignal(str, bool)  # action_name, success

    def __init__(self):
        """Initialize application controller."""
        super().__init__()

        self.state = ApplicationState.IDLE
        self.language = config.get("language", "en")
        self.is_running = False

        # Initialize modules (lazy loading)
        self._voice_engine: Optional[VoiceEngine] = None
        self._voice_parser: Optional[VoiceCommandParser] = None
        self._command_registry: Optional[CommandRegistry] = None
        self._eye_tracker: Optional[EyeTracker] = None
        self._mouse_controller: Optional[MouseController] = None
        self._browser_controller: Optional[BrowserController] = None
        self._macro_manager: Optional[MacroManager] = None
        self._app_launcher: Optional[AppLauncher] = None

        # Thread management
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # State tracking
        self._recording_macro = False
        self._playing_macro = False
        self._tracking_active = False
        self._listening_active = False

        # Statistics
        self._actions_executed = 0
        self._errors_encountered = 0
        self._start_time = None

        logger.info(
            "ApplicationController initialized | "
            f"language={self.language} | "
            f"version=1.0.0"
        )

    # ======================================================================
    # Startup and Shutdown
    # ======================================================================

    def startup(self) -> bool:
        """
        Start the application.

        Returns:
            True if startup successful, False otherwise.
        """
        try:
            logger.info("Application startup initiated")

            if not self._init_voice_engine():
                logger.error("Failed to initialize voice engine")
                return False

            if not self._init_eye_tracker():
                logger.warning("Eye tracker initialization failed (non-critical)")

            if not self._init_mouse_controller():
                logger.error("Failed to initialize mouse controller")
                return False

            if not self._init_browser_controller():
                logger.warning("Browser controller initialization failed")

            if not self._init_macro_manager():
                logger.warning("Macro manager initialization failed (non-critical)")

            if not self._init_app_launcher():
                logger.warning("App launcher initialization failed")

            self.is_running = True
            self._set_state(ApplicationState.IDLE)

            logger.info("Application startup complete")
            return True

        except Exception as e:
            logger.error(f"Startup failed: {e}", exc_info=True)
            self.error_occurred.emit(f"Startup error: {e}")
            return False

    def shutdown(self) -> None:
        """Shut down the application gracefully."""
        try:
            logger.info("Application shutdown initiated")

            self.is_running = False
            self._stop_event.set()

            # Stop all active operations
            if self._listening_active:
                self.stop_listening()

            if self._tracking_active:
                self.stop_tracking()

            if self._playing_macro:
                self.stop_macro_playback()

            # Cleanup modules
            self._cleanup_modules()

            # Log statistics
            elapsed = self._get_elapsed_time()
            logger.info(
                f"Application shutdown complete | "
                f"actions_executed={self._actions_executed} | "
                f"errors={self._errors_encountered} | "
                f"runtime={elapsed}s"
            )

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)

    def _cleanup_modules(self) -> None:
        """Clean up and release all module resources."""
        modules_to_cleanup = [
            ("voice_engine", self._voice_engine),
            ("eye_tracker", self._eye_tracker),
            ("mouse_controller", self._mouse_controller),
            ("browser_controller", self._browser_controller),
            ("macro_manager", self._macro_manager),
            ("app_launcher", self._app_launcher),
        ]

        for module_name, module in modules_to_cleanup:
            try:
                if module and hasattr(module, "cleanup"):
                    module.cleanup()
                    logger.debug(f"Cleaned up: {module_name}")
            except Exception as e:
                logger.warning(f"Error cleaning up {module_name}: {e}")

    # ======================================================================
    # Module Initialization (Lazy Loading)
    # ======================================================================

    def _init_voice_engine(self) -> bool:
        """Initialize voice engine."""
        try:
            logger.info("Initializing voice engine...")

            self._voice_engine = VoiceEngine(language=self.language)
            self._voice_parser = VoiceCommandParser(language=self.language)
            self._command_registry = CommandRegistry()

            # Register command handlers
            self._register_command_handlers()

            logger.info("Voice engine initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Voice engine initialization failed: {e}", exc_info=True)
            return False

    def _init_eye_tracker(self) -> bool:
        """Initialize eye tracker."""
        try:
            logger.info("Initializing eye tracker...")

            self._eye_tracker = EyeTracker()
            # Set up callbacks for eye tracking events
            if hasattr(self._eye_tracker, "on_blink"):
                self._eye_tracker.on_blink(self._on_blink_detected)

            logger.info("Eye tracker initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Eye tracker initialization failed: {e}", exc_info=True)
            return False

    def _init_mouse_controller(self) -> bool:
        """Initialize mouse controller."""
        try:
            logger.info("Initializing mouse controller...")

            self._mouse_controller = MouseController()

            logger.info("Mouse controller initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Mouse controller initialization failed: {e}", exc_info=True)
            return False

    def _init_browser_controller(self) -> bool:
        """Initialize browser controller."""
        try:
            logger.info("Initializing browser controller...")

            self._browser_controller = BrowserController()

            logger.info("Browser controller initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Browser controller initialization failed: {e}", exc_info=True)
            return False

    def _init_macro_manager(self) -> bool:
        """Initialize macro manager."""
        try:
            logger.info("Initializing macro manager...")

            storage_dir = Path(config.get("data_dir", "data")) / "macros"
            self._macro_manager = MacroManager(
                storage_dir=storage_dir,
                auto_save=True,
            )

            logger.info("Macro manager initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Macro manager initialization failed: {e}", exc_info=True)
            return False

    def _init_app_launcher(self) -> bool:
        """Initialize app launcher."""
        try:
            logger.info("Initializing app launcher...")

            self._app_launcher = AppLauncher()

            logger.info("App launcher initialized successfully")
            return True

        except Exception as e:
            logger.error(f"App launcher initialization failed: {e}", exc_info=True)
            return False

    # ======================================================================
    # Voice Control
    # ======================================================================

    def start_listening(self) -> bool:
        """Start voice listening."""
        if not self._voice_engine:
            logger.error("Voice engine not initialized")
            return False

        try:
            logger.info("Starting voice listening")
            self._listening_active = True
            self._set_state(ApplicationState.LISTENING)

            # Load model if needed
            if not self._voice_engine.is_model_loaded():
                self.status_updated.emit("Loading Whisper model...")
                self._voice_engine.load_model()

            # Start listening in background
            self._voice_engine.start_listening()
            self.status_updated.emit("Listening...")

            return True

        except Exception as e:
            logger.error(f"Failed to start listening: {e}")
            self.error_occurred.emit(f"Voice error: {e}")
            return False

    def stop_listening(self) -> None:
        """Stop voice listening."""
        if self._voice_engine:
            try:
                self._voice_engine.stop_listening()
                self._listening_active = False
                self._set_state(ApplicationState.IDLE)
                self.status_updated.emit("Listening stopped")
                logger.info("Voice listening stopped")
            except Exception as e:
                logger.error(f"Error stopping listening: {e}")

    def set_language(self, language: str) -> None:
        """Set application language."""
        if language not in ("en", "bn"):
            logger.warning(f"Invalid language: {language}")
            return

        self.language = language
        config.set("language", language)

        if self._voice_parser:
            self._voice_parser.set_language(language)

        if self._voice_engine:
            self._voice_engine.set_language(language)

        logger.info(f"Language changed to: {language}")

    # ======================================================================
    # Eye Tracking
    # ======================================================================

    def start_tracking(self) -> bool:
        """Start eye/nose tracking."""
        if not self._eye_tracker:
            logger.error("Eye tracker not initialized")
            return False

        try:
            logger.info("Starting eye tracking")
            self._tracking_active = True
            self._set_state(ApplicationState.TRACKING)

            if hasattr(self._eye_tracker, "start"):
                self._eye_tracker.start()

            self.status_updated.emit("Tracking active")
            return True

        except Exception as e:
            logger.error(f"Failed to start tracking: {e}")
            self.error_occurred.emit(f"Tracking error: {e}")
            return False

    def stop_tracking(self) -> None:
        """Stop eye/nose tracking."""
        if self._eye_tracker:
            try:
                if hasattr(self._eye_tracker, "stop"):
                    self._eye_tracker.stop()

                self._tracking_active = False
                self._set_state(ApplicationState.IDLE)
                self.status_updated.emit("Tracking stopped")
                logger.info("Eye tracking stopped")
            except Exception as e:
                logger.error(f"Error stopping tracking: {e}")

    def calibrate_eye_tracker(self) -> bool:
        """Calibrate eye tracker."""
        if not self._eye_tracker:
            return False

        try:
            logger.info("Eye tracker calibration started")
            self.status_updated.emit("Calibrating eye tracker...")

            if hasattr(self._eye_tracker, "calibrate"):
                self._eye_tracker.calibrate()

            self.status_updated.emit("Calibration complete")
            logger.info("Eye tracker calibration complete")
            return True

        except Exception as e:
            logger.error(f"Calibration failed: {e}")
            self.error_occurred.emit(f"Calibration error: {e}")
            return False

    # ======================================================================
    # Mouse and Keyboard
    # ======================================================================

    def click_at_position(self, x: int, y: int, button: str = "left") -> bool:
        """Perform a click at specified position."""
        if not self._mouse_controller:
            return False

        try:
            self._set_state(ApplicationState.EXECUTING)
            self._mouse_controller.click(x, y, button=button)
            self._actions_executed += 1
            self.action_completed.emit(f"click_{button}", True)
            self._set_state(ApplicationState.IDLE)
            return True

        except Exception as e:
            logger.error(f"Click failed: {e}")
            self._errors_encountered += 1
            self.error_occurred.emit(f"Click error: {e}")
            self._set_state(ApplicationState.IDLE)
            return False

    def type_text(self, text: str) -> bool:
        """Type text."""
        if not self._mouse_controller:
            return False

        try:
            self._set_state(ApplicationState.EXECUTING)
            self._mouse_controller.type_text(text)
            self._actions_executed += 1
            self.action_completed.emit("type_text", True)
            self._set_state(ApplicationState.IDLE)
            return True

        except Exception as e:
            logger.error(f"Type text failed: {e}")
            self._errors_encountered += 1
            self.action_completed.emit("type_text", False)
            self._set_state(ApplicationState.IDLE)
            return False

    # ======================================================================
    # Macro System
    # ======================================================================

    def start_macro_recording(self, name: str, description: str = "") -> bool:
        """Start recording a macro."""
        if not self._macro_manager:
            logger.error("Macro manager not initialized")
            return False

        try:
            logger.info(f"Starting macro recording: {name}")
            self._macro_manager.start_recording(name, description)
            self._recording_macro = True
            self._set_state(ApplicationState.RECORDING)
            self.status_updated.emit(f"Recording macro: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.error_occurred.emit(f"Recording error: {e}")
            return False

    def stop_macro_recording(self) -> bool:
        """Stop recording macro."""
        if not self._macro_manager:
            return False

        try:
            actions = self._macro_manager.stop_recording()
            self._recording_macro = False
            self._set_state(ApplicationState.IDLE)
            self.status_updated.emit(f"Macro recorded ({len(actions)} actions)")
            logger.info(f"Macro recording stopped ({len(actions)} actions)")
            return True

        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            self.error_occurred.emit(f"Recording error: {e}")
            return False

    def record_action(self, action: Dict[str, Any]) -> None:
        """Record an action during macro recording."""
        if self._macro_manager and self._recording_macro:
            self._macro_manager.record_action(action)

    def play_macro(self, macro_name: str, speed: float = 1.0, loop_count: int = 1) -> bool:
        """Play a recorded macro."""
        if not self._macro_manager:
            return False

        try:
            logger.info(f"Playing macro: {macro_name} (speed={speed}, loops={loop_count})")
            self._set_state(ApplicationState.EXECUTING)
            self._playing_macro = True
            self.status_updated.emit(f"Playing macro: {macro_name}")

            macro = self._macro_manager.load_macro(macro_name)
            self._macro_manager.replay_macro(
                macro,
                speed=speed,
                loop_count=loop_count,
                action_callback=self._execute_recorded_action,
            )

            self._playing_macro = False
            self._set_state(ApplicationState.IDLE)
            self.action_completed.emit(f"play_macro_{macro_name}", True)

            return True

        except Exception as e:
            logger.error(f"Macro playback failed: {e}")
            self._errors_encountered += 1
            self._playing_macro = False
            self.error_occurred.emit(f"Playback error: {e}")
            self._set_state(ApplicationState.IDLE)
            return False

    def stop_macro_playback(self) -> None:
        """Stop macro playback."""
        if self._macro_manager:
            self._macro_manager.stop_playback()
            self._playing_macro = False
            self._set_state(ApplicationState.IDLE)
            logger.info("Macro playback stopped")

    def list_macros(self) -> List[str]:
        """Get list of saved macros."""
        if not self._macro_manager:
            return []

        try:
            macros = self._macro_manager.list_macros()
            return [m.name for m in macros]

        except Exception as e:
            logger.error(f"Error listing macros: {e}")
            return []

    # ======================================================================
    # Browser Control
    # ======================================================================

    def browser_search(self, search_term: str, browser: str = "chrome") -> bool:
        """Perform browser search."""
        if not self._browser_controller:
            return False

        try:
            logger.info(f"Browser search: {search_term}")
            self._set_state(ApplicationState.EXECUTING)
            self._browser_controller.search(search_term, browser=browser)
            self._actions_executed += 1
            self.action_completed.emit("browser_search", True)
            self._set_state(ApplicationState.IDLE)
            return True

        except Exception as e:
            logger.error(f"Browser search failed: {e}")
            self._errors_encountered += 1
            self.action_completed.emit("browser_search", False)
            self._set_state(ApplicationState.IDLE)
            return False

    # ======================================================================
    # Application Launching
    # ======================================================================

    def launch_app(self, app_name: str) -> bool:
        """Launch an application."""
        if not self._app_launcher:
            return False

        try:
            logger.info(f"Launching app: {app_name}")
            self._set_state(ApplicationState.EXECUTING)
            self._app_launcher.launch_app(app_name)
            self._actions_executed += 1
            self.action_completed.emit(f"launch_{app_name}", True)
            self._set_state(ApplicationState.IDLE)
            return True

        except Exception as e:
            logger.error(f"App launch failed: {e}")
            self._errors_encountered += 1
            self.error_occurred.emit(f"Launch error: {e}")
            self._set_state(ApplicationState.IDLE)
            return False

    def get_available_apps(self) -> List[str]:
        """Get list of available applications."""
        if not self._app_launcher:
            return []

        try:
            return self._app_launcher.list_apps()
        except Exception as e:
            logger.error(f"Error getting app list: {e}")
            return []

    # ======================================================================
    # Command Handling
    # ======================================================================

    def _register_command_handlers(self) -> None:
        """Register voice command handlers."""
        if not self._command_registry:
            return

        # Mouse commands
        self._command_registry.register("click", self._handle_click_command)
        self._command_registry.register("double_click", self._handle_double_click_command)
        self._command_registry.register("right_click", self._handle_right_click_command)

        # Macro commands
        self._command_registry.register("macro_start", self._handle_macro_start)
        self._command_registry.register("macro_stop", self._handle_macro_stop)
        self._command_registry.register("macro_play", self._handle_macro_play)

        # Browser commands
        self._command_registry.register("browser_search", self._handle_browser_search)

        # App commands
        self._command_registry.register("open_app", self._handle_open_app)

        logger.info("Command handlers registered")

    def _handle_click_command(self, command) -> None:
        """Handle click voice command."""
        logger.info("Click command received")
        # Will be implemented with eye tracker integration
        self.click_at_position(0, 0)

    def _handle_double_click_command(self, command) -> None:
        """Handle double click voice command."""
        logger.info("Double click command received")
        self.click_at_position(0, 0, button="left")

    def _handle_right_click_command(self, command) -> None:
        """Handle right click voice command."""
        logger.info("Right click command received")
        self.click_at_position(0, 0, button="right")

    def _handle_macro_start(self, command) -> None:
        """Handle macro start command."""
        logger.info("Macro start command received")
        self.start_macro_recording("voice_macro")

    def _handle_macro_stop(self, command) -> None:
        """Handle macro stop command."""
        logger.info("Macro stop command received")
        self.stop_macro_recording()

    def _handle_macro_play(self, command) -> None:
        """Handle macro play command."""
        logger.info(f"Macro play command received: {command.args}")
        if command.args:
            macro_name = command.args[0]
            self.play_macro(macro_name)

    def _handle_browser_search(self, command) -> None:
        """Handle browser search command."""
        logger.info(f"Browser search command received: {command.args}")
        if command.args:
            search_term = " ".join(command.args)
            self.browser_search(search_term)

    def _handle_open_app(self, command) -> None:
        """Handle open app command."""
        logger.info(f"Open app command received: {command.args}")
        if command.args:
            app_name = command.args[0]
            self.launch_app(app_name)

    # ======================================================================
    # Event Handlers
    # ======================================================================

    def _on_blink_detected(self) -> None:
        """Handle blink detection event."""
        logger.debug("Blink detected")
        if self._tracking_active:
            # Use blink as click action
            self.click_at_position(0, 0)

    def _execute_recorded_action(self, action: Dict[str, Any]) -> None:
        """Execute a recorded action during macro playback."""
        try:
            action_type = action.get("type")

            if action_type == "click" and self._mouse_controller:
                pos = action.get("position", (0, 0))
                self._mouse_controller.click(pos[0], pos[1])

            elif action_type == "type_text" and self._mouse_controller:
                text = action.get("text", "")
                self._mouse_controller.type_text(text)

            elif action_type == "double_click" and self._mouse_controller:
                pos = action.get("position", (0, 0))
                self._mouse_controller.double_click(pos[0], pos[1])

        except Exception as e:
            logger.error(f"Error executing recorded action: {e}")

    # ======================================================================
    # State Management
    # ======================================================================

    def _set_state(self, new_state: ApplicationState) -> None:
        """Set application state."""
        if self.state != new_state:
            self.state = new_state
            self.state_changed.emit(new_state)
            logger.debug(f"State changed to: {new_state.value}")

    def get_state(self) -> ApplicationState:
        """Get current application state."""
        return self.state

    def get_status(self) -> Dict[str, Any]:
        """Get current application status."""
        return {
            "state": self.state.value,
            "listening": self._listening_active,
            "tracking": self._tracking_active,
            "recording": self._recording_macro,
            "playing": self._playing_macro,
            "actions_executed": self._actions_executed,
            "errors": self._errors_encountered,
            "runtime": self._get_elapsed_time(),
        }

    def _get_elapsed_time(self) -> float:
        """Get elapsed time since startup."""
        if self._start_time is None:
            return 0.0

        import time
        return time.time() - self._start_time


__all__ = ["ApplicationController", "ApplicationState"]
