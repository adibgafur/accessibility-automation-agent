"""
Tests for src.utils.error_handler — custom exceptions and recovery handler.

Covers:
    - Exception hierarchy and inheritance
    - Error codes on each exception class
    - Context data propagation
    - ErrorRecoveryHandler.get_suggestions()
    - ErrorRecoveryHandler.handle_error()
"""

import pytest

from src.utils.error_handler import (
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


# ======================================================================
# Exception hierarchy
# ======================================================================


class TestExceptionHierarchy:
    """All domain exceptions inherit from AccessibilityAgentError."""

    @pytest.mark.parametrize(
        "exc_class",
        [
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
        ],
    )
    def test_is_subclass_of_base(self, exc_class):
        assert issubclass(exc_class, AccessibilityAgentError)

    def test_base_is_exception(self):
        assert issubclass(AccessibilityAgentError, Exception)


# ======================================================================
# Error codes
# ======================================================================


class TestErrorCodes:
    """Each exception carries a unique, machine-readable error code."""

    @pytest.mark.parametrize(
        "exc_class, expected_code",
        [
            (ConfigurationError, "CONFIG_ERROR"),
            (VoiceEngineError, "VOICE_ERROR"),
            (EyeTrackingError, "EYE_TRACKING_ERROR"),
            (GUIDetectionError, "GUI_DETECTION_ERROR"),
            (AutomationError, "AUTOMATION_ERROR"),
            (BrowserAutomationError, "BROWSER_ERROR"),
            (UIError, "UI_ERROR"),
            (MacroError, "MACRO_ERROR"),
            (CameraError, "CAMERA_ERROR"),
            (ModelLoadError, "MODEL_LOAD_ERROR"),
        ],
    )
    def test_error_code(self, exc_class, expected_code):
        exc = exc_class("test message")
        assert exc.code == expected_code

    def test_base_default_code(self):
        exc = AccessibilityAgentError("generic")
        assert exc.code == "GENERAL_ERROR"


# ======================================================================
# Message and context
# ======================================================================


class TestMessageAndContext:
    """Exceptions carry a message and optional context dict."""

    def test_message_stored(self):
        exc = VoiceEngineError("Mic not found")
        assert exc.message == "Mic not found"
        assert str(exc) == "Mic not found"

    def test_context_defaults_to_empty(self):
        exc = CameraError("no camera")
        assert exc.context == {}

    def test_context_passed_through(self):
        ctx = {"device": "/dev/video0", "retries": 3}
        exc = CameraError("no camera", context=ctx)
        assert exc.context == ctx
        assert exc.context["retries"] == 3


# ======================================================================
# Catchability
# ======================================================================


class TestCatchability:
    """Verify broad and narrow catches work as expected."""

    def test_catch_specific(self):
        with pytest.raises(VoiceEngineError):
            raise VoiceEngineError("test")

    def test_catch_broad(self):
        with pytest.raises(AccessibilityAgentError):
            raise BrowserAutomationError("timeout")

    def test_catch_as_exception(self):
        with pytest.raises(Exception):
            raise MacroError("bad file")


# ======================================================================
# ErrorRecoveryHandler
# ======================================================================


class TestErrorRecoveryHandler:
    """Test the static recovery-suggestion lookup and handle_error()."""

    def test_known_error_has_suggestions(self):
        suggestions = ErrorRecoveryHandler.get_suggestions("VoiceEngineError")
        assert len(suggestions) > 0
        assert any("microphone" in s.lower() for s in suggestions)

    def test_unknown_error_returns_fallback(self):
        suggestions = ErrorRecoveryHandler.get_suggestions("UnknownError")
        assert len(suggestions) == 1
        assert "logs" in suggestions[0].lower()

    @pytest.mark.parametrize(
        "error_type",
        [
            "VoiceEngineError",
            "EyeTrackingError",
            "GUIDetectionError",
            "BrowserAutomationError",
            "ConfigurationError",
            "CameraError",
            "ModelLoadError",
            "MacroError",
            "AutomationError",
            "UIError",
        ],
    )
    def test_all_known_types_have_suggestions(self, error_type):
        suggestions = ErrorRecoveryHandler.get_suggestions(error_type)
        assert isinstance(suggestions, list)
        assert len(suggestions) >= 1

    def test_handle_error_returns_suggestions(self):
        exc = VoiceEngineError("test error")
        suggestions = ErrorRecoveryHandler.handle_error(exc)
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0

    def test_handle_error_with_unknown_type(self):
        exc = RuntimeError("something unexpected")
        suggestions = ErrorRecoveryHandler.handle_error(exc)
        assert len(suggestions) == 1
        assert "logs" in suggestions[0].lower()

    def test_handle_error_with_context(self):
        exc = CameraError(
            "Camera disconnected",
            context={"camera_index": 0},
        )
        suggestions = ErrorRecoveryHandler.handle_error(exc)
        assert any("webcam" in s.lower() or "camera" in s.lower() for s in suggestions)
