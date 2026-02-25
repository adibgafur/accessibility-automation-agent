"""
Voice Control Engine - Whisper Integration.

Handles speech-to-text conversion using OpenAI's Whisper model
with support for English and Bengali languages.

This module will be fully implemented in Phase 4.
Current state: interface stubs with logging.
"""

from typing import Callable, List, Optional

from loguru import logger

from ..utils.config_manager import config
from ..utils.error_handler import VoiceEngineError, ModelLoadError


class VoiceEngine:
    """
    Speech-to-text engine powered by OpenAI Whisper.

    Supports:
        - English (``en``) and Bengali (``bn``)
        - Continuous listening with callbacks
        - Configurable model size (tiny / base / small / medium)
        - Offline processing (no internet required after model download)

    Usage (Phase 4+):
        engine = VoiceEngine(language="en")
        engine.load_model()
        engine.start_listening()
    """

    SUPPORTED_LANGUAGES = {"en": "english", "bn": "bengali"}

    def __init__(self, language: str = "en") -> None:
        """
        Initialise the voice engine.

        Args:
            language: ISO 639-1 code (``"en"`` or ``"bn"``).

        Raises:
            VoiceEngineError: If the language is not supported.
        """
        if language not in self.SUPPORTED_LANGUAGES:
            raise VoiceEngineError(
                f"Unsupported language: {language}. "
                f"Supported: {list(self.SUPPORTED_LANGUAGES.keys())}"
            )

        self.language = language
        self.model = None
        self.is_listening = False
        self.is_model_loaded = False
        self._callbacks: List[Callable[[str], None]] = []

        # Read settings from config
        self._model_size: str = config.get("voice.whisper_model", "base")
        self._device: str = config.get("voice.device", "cpu")
        self._confidence_threshold: float = config.get(
            "voice.confidence_threshold", 0.5
        )

        logger.info(
            f"VoiceEngine created | lang={language} | "
            f"model={self._model_size} | device={self._device}"
        )

    # ------------------------------------------------------------------
    # Model lifecycle
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        """
        Download (if needed) and load the Whisper model.

        Raises:
            ModelLoadError: If the model cannot be loaded.
        """
        try:
            logger.info(f"Loading Whisper model '{self._model_size}'...")
            # TODO: Phase 4 implementation
            # import whisper
            # self.model = whisper.load_model(
            #     self._model_size, device=self._device
            # )
            self.is_model_loaded = True
            logger.info("Whisper model loaded successfully (stub)")
        except Exception as exc:
            raise ModelLoadError(
                f"Failed to load Whisper model: {exc}",
                context={"model": self._model_size, "device": self._device},
            )

    def unload_model(self) -> None:
        """Release model from memory."""
        self.model = None
        self.is_model_loaded = False
        logger.info("Whisper model unloaded")

    # ------------------------------------------------------------------
    # Listening
    # ------------------------------------------------------------------

    def start_listening(self) -> None:
        """
        Begin capturing audio from the microphone.

        Raises:
            VoiceEngineError: If the model is not loaded.
        """
        if not self.is_model_loaded:
            raise VoiceEngineError("Cannot start listening: model not loaded")
        self.is_listening = True
        logger.info("Voice listening started")
        # TODO: Phase 4 - open audio stream with sounddevice

    def stop_listening(self) -> None:
        """Stop capturing audio."""
        self.is_listening = False
        logger.info("Voice listening stopped")

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    def transcribe(self, audio_data) -> Optional[str]:
        """
        Transcribe raw audio data to text.

        Args:
            audio_data: NumPy array of audio samples.

        Returns:
            Transcribed text, or ``None`` on failure.
        """
        if not self.is_model_loaded:
            logger.warning("transcribe() called but model is not loaded")
            return None

        # TODO: Phase 4 implementation
        # result = self.model.transcribe(
        #     audio_data, language=self.SUPPORTED_LANGUAGES[self.language]
        # )
        # return result["text"]
        logger.debug("transcribe() stub called")
        return None

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_transcription(self, callback: Callable[[str], None]) -> None:
        """Register a callback invoked with each transcription result."""
        self._callbacks.append(callback)

    def _notify_callbacks(self, text: str) -> None:
        """Dispatch transcribed text to all registered callbacks."""
        for cb in self._callbacks:
            try:
                cb(text)
            except Exception as exc:
                logger.error(f"Transcription callback error: {exc}")

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------

    def set_language(self, language: str) -> None:
        """
        Switch the recognition language.

        Args:
            language: ``"en"`` or ``"bn"``.
        """
        if language not in self.SUPPORTED_LANGUAGES:
            raise VoiceEngineError(f"Unsupported language: {language}")
        self.language = language
        logger.info(f"Voice language changed to: {language}")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return a status dict for the UI panel."""
        return {
            "language": self.language,
            "model_size": self._model_size,
            "model_loaded": self.is_model_loaded,
            "listening": self.is_listening,
            "device": self._device,
        }


__all__ = ["VoiceEngine"]
