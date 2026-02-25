"""
Utility modules for the Accessibility Automation Agent.

Provides logging, configuration, error handling, and accessibility helpers.
"""

from .logging_config import setup_logging, get_logger
from .config_manager import ConfigManager, config
from .error_handler import (
    AccessibilityAgentError,
    ConfigurationError,
    VoiceEngineError,
    EyeTrackingError,
    GUIDetectionError,
    AutomationError,
    BrowserAutomationError,
    UIError,
    MacroError,
    CameraError,
    ModelLoadError,
    ErrorRecoveryHandler,
)
from .accessibility_helpers import (
    AccessibilityNotifier,
    KeyboardShortcutValidator,
    AccessibleColorScheme,
    AccessibleFontHelper,
    notifier,
)

__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    # Configuration
    "ConfigManager",
    "config",
    # Exceptions
    "AccessibilityAgentError",
    "ConfigurationError",
    "VoiceEngineError",
    "EyeTrackingError",
    "GUIDetectionError",
    "AutomationError",
    "BrowserAutomationError",
    "UIError",
    "MacroError",
    "CameraError",
    "ModelLoadError",
    "ErrorRecoveryHandler",
    # Accessibility
    "AccessibilityNotifier",
    "KeyboardShortcutValidator",
    "AccessibleColorScheme",
    "AccessibleFontHelper",
    "notifier",
]
