"""
Error Handling and Custom Exceptions for Accessibility Automation Agent.

Defines a hierarchy of domain-specific exceptions and an
ErrorRecoveryHandler that provides actionable recovery suggestions
for each error category.
"""

from typing import Any, Dict, List, Optional

from loguru import logger


# ======================================================================
# Base Exception
# ======================================================================


class AccessibilityAgentError(Exception):
    """
    Base exception for the Accessibility Automation Agent.

    All domain-specific errors inherit from this class so callers
    can catch broad or narrow categories as needed.

    Attributes:
        message:  Human-readable error description.
        code:     Machine-readable error code string.
        context:  Optional dict with extra diagnostic data.
    """

    def __init__(
        self,
        message: str,
        code: str = "GENERAL_ERROR",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.code = code
        self.context = context or {}
        super().__init__(self.message)
        logger.error(
            f"[{self.code}] {self.message}",
            extra={"context": self.context},
        )


# ======================================================================
# Domain-Specific Exceptions
# ======================================================================


class ConfigurationError(AccessibilityAgentError):
    """Raised when configuration loading or validation fails."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="CONFIG_ERROR", context=context)


class VoiceEngineError(AccessibilityAgentError):
    """Raised when voice recognition or audio processing fails."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="VOICE_ERROR", context=context)


class EyeTrackingError(AccessibilityAgentError):
    """Raised when eye/nose tracking or camera operations fail."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="EYE_TRACKING_ERROR", context=context)


class GUIDetectionError(AccessibilityAgentError):
    """Raised when GUI element detection (UFO2 or GUIrilla) fails."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="GUI_DETECTION_ERROR", context=context)


class AutomationError(AccessibilityAgentError):
    """Raised when a mouse, keyboard, or system automation action fails."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AUTOMATION_ERROR", context=context)


class BrowserAutomationError(AccessibilityAgentError):
    """Raised when browser automation (Selenium) fails."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="BROWSER_ERROR", context=context)


class UIError(AccessibilityAgentError):
    """Raised when the PyQt6 UI encounters a rendering or interaction error."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="UI_ERROR", context=context)


class MacroError(AccessibilityAgentError):
    """Raised when macro recording, storage, or playback fails."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="MACRO_ERROR", context=context)


class CameraError(AccessibilityAgentError):
    """Raised when the camera device cannot be accessed."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="CAMERA_ERROR", context=context)


class ModelLoadError(AccessibilityAgentError):
    """Raised when a ML model (Whisper, GUIrilla, etc.) fails to load."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="MODEL_LOAD_ERROR", context=context)


# ======================================================================
# Recovery Handler
# ======================================================================


class ErrorRecoveryHandler:
    """
    Provides actionable recovery suggestions for each error type.

    Usage:
        try:
            ...
        except VoiceEngineError as e:
            ErrorRecoveryHandler.handle_error(e)
    """

    RECOVERY_SUGGESTIONS: Dict[str, List[str]] = {
        "VoiceEngineError": [
            "Check that the microphone is connected and working",
            "Verify microphone permissions in Windows Settings > Privacy",
            "Try recalibrating voice sensitivity in Settings",
            "Ensure the Whisper model has been downloaded to .cache/",
            "Switch to a smaller Whisper model (tiny/base) if memory is low",
        ],
        "EyeTrackingError": [
            "Check that the webcam is connected and not used by another app",
            "Verify camera permissions in Windows Settings > Privacy",
            "Run the calibration wizard from Eye Tracker panel",
            "Improve lighting conditions (avoid backlighting)",
            "Clean the camera lens",
        ],
        "GUIDetectionError": [
            "The application UI may have changed - falling back to GUIrilla",
            "Try manual element selection from the detection panel",
            "Check if the target application needs an update",
            "Restart the target application and retry",
            "Increase the detection confidence threshold in Settings",
        ],
        "BrowserAutomationError": [
            "Check that Chrome/Firefox is installed and up to date",
            "Verify that the WebDriver matches the browser version",
            "Clear the browser cache and retry",
            "Try switching from Chrome to Firefox (or vice versa)",
            "Check your internet connection",
        ],
        "ConfigurationError": [
            "Verify YAML syntax in config/ files (use a YAML validator)",
            "Check file permissions for the config/ directory",
            "Restore defaults by deleting config/ and restarting",
            "Review environment variables starting with APP_",
        ],
        "CameraError": [
            "Ensure the webcam is connected and recognised by Windows",
            "Close other applications that may be using the camera",
            "Try a different camera_index in Settings (0, 1, 2, ...)",
            "Update webcam drivers from Device Manager",
        ],
        "ModelLoadError": [
            "Ensure you have enough disk space for model files",
            "Check your internet connection for model downloads",
            "Try a smaller model variant to reduce memory usage",
            "Clear the model cache and re-download",
        ],
        "MacroError": [
            "Check that the macro file exists and is valid JSON",
            "Verify file write permissions in data/macros/",
            "Try re-recording the macro",
        ],
        "AutomationError": [
            "Ensure the target window is in the foreground",
            "Check that no system dialog is blocking the action",
            "Run the application as Administrator if required",
        ],
        "UIError": [
            "Try restarting the application",
            "Switch themes in Settings to see if the issue persists",
            "Check the error log at logs/errors.log for details",
        ],
    }

    @staticmethod
    def get_suggestions(error_type: str) -> List[str]:
        """
        Return recovery suggestions for a given error type name.

        Args:
            error_type: The exception class name (e.g., ``"VoiceEngineError"``).

        Returns:
            A list of human-readable recovery suggestions.
        """
        return ErrorRecoveryHandler.RECOVERY_SUGGESTIONS.get(
            error_type,
            ["Check logs/errors.log for more details"],
        )

    @staticmethod
    def handle_error(exception: Exception) -> List[str]:
        """
        Log the error and return recovery suggestions.

        Args:
            exception: The caught exception.

        Returns:
            List of recovery suggestions.
        """
        error_type = type(exception).__name__
        logger.error(f"Handling error: {error_type} - {exception}")

        suggestions = ErrorRecoveryHandler.get_suggestions(error_type)
        if suggestions:
            logger.info(f"Recovery suggestions for {error_type}:")
            for idx, suggestion in enumerate(suggestions, 1):
                logger.info(f"  {idx}. {suggestion}")

        return suggestions


__all__ = [
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
]
