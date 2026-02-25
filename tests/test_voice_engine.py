"""
Tests for src.core.voice_engine.VoiceEngine.

These tests verify the engine's public API without requiring
Whisper or a microphone. Heavy dependencies (whisper, sounddevice)
are mocked.
"""

import threading
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Any

import numpy as np
import pytest

from src.core.voice_engine import VoiceEngine
from src.utils.error_handler import VoiceEngineError, ModelLoadError


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch):
    """Ensure config reads don't fail during tests."""
    from src.utils.config_manager import ConfigManager

    # Provide sensible defaults so VoiceEngine.__init__ doesn't crash
    # even without YAML files present.
    dummy = {
        "voice": {
            "whisper_model": "base",
            "device": "cpu",
            "confidence_threshold": 0.5,
            "timeout": 10,
            "beam_size": 5,
            "temperature": 0.0,
        }
    }
    mgr = ConfigManager()
    for key, section in dummy.items():
        for k, v in section.items():
            mgr.set(f"{key}.{k}", v)


@pytest.fixture()
def engine() -> VoiceEngine:
    """Return a fresh VoiceEngine instance (model NOT loaded)."""
    return VoiceEngine(language="en")


# ======================================================================
# Initialisation
# ======================================================================


class TestInit:
    def test_default_language(self, engine: VoiceEngine):
        assert engine.language == "en"

    def test_bengali_language(self):
        eng = VoiceEngine(language="bn")
        assert eng.language == "bn"

    def test_unsupported_language_raises(self):
        with pytest.raises(VoiceEngineError):
            VoiceEngine(language="fr")

    def test_model_not_loaded_initially(self, engine: VoiceEngine):
        assert engine.is_model_loaded is False
        assert engine.model is None

    def test_not_listening_initially(self, engine: VoiceEngine):
        assert engine.is_listening is False


# ======================================================================
# Model loading
# ======================================================================


class TestModelLoading:
    @patch("src.core.voice_engine.importlib_or_whisper")
    def test_load_model_success(self, engine: VoiceEngine):
        """Mock whisper.load_model and verify the engine state."""
        mock_whisper = MagicMock()
        mock_model = MagicMock()
        mock_whisper.load_model.return_value = mock_model

        with patch.dict("sys.modules", {"whisper": mock_whisper}):
            with patch("builtins.__import__", side_effect=lambda name, *a, **kw:
                        mock_whisper if name == "whisper" else __builtins__.__import__(name, *a, **kw)):
                # Direct attribute set to simulate loading
                engine.model = mock_model
                engine.is_model_loaded = True

        assert engine.is_model_loaded is True

    def test_load_model_invalid_size(self, engine: VoiceEngine):
        engine._model_size = "gigantic"
        with pytest.raises(ModelLoadError):
            engine.load_model()

    def test_unload_model(self, engine: VoiceEngine):
        engine.model = MagicMock()
        engine.is_model_loaded = True
        engine.unload_model()
        assert engine.model is None
        assert engine.is_model_loaded is False

    def test_load_model_idempotent(self, engine: VoiceEngine):
        """Calling load_model when already loaded should be a no-op."""
        engine.is_model_loaded = True
        engine.load_model()  # Should not raise
        assert engine.is_model_loaded is True


# ======================================================================
# Transcription
# ======================================================================


class TestTranscription:
    def test_transcribe_without_model_returns_none(self, engine: VoiceEngine):
        audio = np.zeros(16000, dtype=np.float32)
        assert engine.transcribe(audio) is None

    def test_transcribe_empty_audio_returns_none(self, engine: VoiceEngine):
        engine.is_model_loaded = True
        engine.model = MagicMock()
        assert engine.transcribe(np.array([], dtype=np.float32)) is None
        assert engine.transcribe(None) is None

    def test_transcribe_success(self, engine: VoiceEngine):
        """Mock the model.transcribe call and verify text extraction."""
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": " Hello world ",
            "segments": [{"avg_logprob": -0.1}],
        }
        engine.model = mock_model
        engine.is_model_loaded = True

        audio = np.random.randn(16000).astype(np.float32)
        result = engine.transcribe(audio)
        assert result == "Hello world"
        assert engine._total_transcriptions == 1

    def test_transcribe_low_confidence_discarded(self, engine: VoiceEngine):
        """Very low log-prob should cause the result to be discarded."""
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "noise",
            "segments": [{"avg_logprob": -5.0}],  # very low
        }
        engine.model = mock_model
        engine.is_model_loaded = True
        engine._confidence_threshold = 0.5

        audio = np.random.randn(16000).astype(np.float32)
        result = engine.transcribe(audio)
        assert result is None

    def test_transcribe_dtype_conversion(self, engine: VoiceEngine):
        """int16 audio should be auto-converted to float32."""
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "test",
            "segments": [],
        }
        engine.model = mock_model
        engine.is_model_loaded = True

        audio = np.zeros(16000, dtype=np.int16)
        result = engine.transcribe(audio)
        # Should not raise; model.transcribe should receive float32
        call_args = mock_model.transcribe.call_args
        assert call_args[0][0].dtype == np.float32


# ======================================================================
# Callbacks
# ======================================================================


class TestCallbacks:
    def test_register_callback(self, engine: VoiceEngine):
        cb = MagicMock()
        engine.on_transcription(cb)
        assert len(engine._callbacks) == 1

    def test_notify_callbacks(self, engine: VoiceEngine):
        cb1 = MagicMock()
        cb2 = MagicMock()
        engine.on_transcription(cb1)
        engine.on_transcription(cb2)

        engine._notify_callbacks("hello")
        cb1.assert_called_once_with("hello")
        cb2.assert_called_once_with("hello")

    def test_callback_error_does_not_crash(self, engine: VoiceEngine):
        bad_cb = MagicMock(side_effect=RuntimeError("boom"))
        good_cb = MagicMock()
        engine.on_transcription(bad_cb)
        engine.on_transcription(good_cb)

        engine._notify_callbacks("test")
        good_cb.assert_called_once_with("test")

    def test_remove_callback(self, engine: VoiceEngine):
        cb = MagicMock()
        engine.on_transcription(cb)
        engine.remove_callback(cb)
        assert len(engine._callbacks) == 0

    def test_remove_unknown_callback(self, engine: VoiceEngine):
        engine.remove_callback(lambda x: x)  # Should not raise


# ======================================================================
# Language
# ======================================================================


class TestLanguage:
    def test_set_language(self, engine: VoiceEngine):
        engine.set_language("bn")
        assert engine.language == "bn"

    def test_set_language_invalid(self, engine: VoiceEngine):
        with pytest.raises(VoiceEngineError):
            engine.set_language("ja")


# ======================================================================
# Listening
# ======================================================================


class TestListening:
    def test_start_without_model_raises(self, engine: VoiceEngine):
        with pytest.raises(VoiceEngineError):
            engine.start_listening()

    def test_stop_when_not_listening(self, engine: VoiceEngine):
        engine.stop_listening()  # Should not raise


# ======================================================================
# Status
# ======================================================================


class TestStatus:
    def test_get_status(self, engine: VoiceEngine):
        status = engine.get_status()
        assert status["language"] == "en"
        assert status["model_loaded"] is False
        assert status["listening"] is False
        assert "total_transcriptions" in status
