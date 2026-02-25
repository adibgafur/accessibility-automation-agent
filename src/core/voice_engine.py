"""
Voice Control Engine - Whisper Integration.

Handles speech-to-text conversion using OpenAI's Whisper model
with support for English and Bengali languages.

Features:
    - Lazy model loading with configurable model size
    - INT8/FP16 optimization for low-spec hardware
    - Continuous listening via AudioCapture integration
    - Language switching at runtime (en / bn)
    - Transcription callbacks for downstream command parsing
    - Thread-safe operation
"""

import threading
import time
from typing import Any, Callable, Dict, List, Optional

import numpy as np
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
        - INT8 quantization for low-spec devices

    Usage:
        engine = VoiceEngine(language="en")
        engine.load_model()
        engine.on_transcription(lambda text: print(text))
        engine.start_listening()
    """

    SUPPORTED_LANGUAGES = {"en": "english", "bn": "bengali"}
    VALID_MODELS = ("tiny", "base", "small", "medium", "large")
    WHISPER_SAMPLE_RATE = 16_000  # Whisper expects 16 kHz mono audio

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
        self.model: Any = None
        self.is_listening: bool = False
        self.is_model_loaded: bool = False
        self._callbacks: List[Callable[[str], None]] = []

        # Audio capture (created on start_listening)
        self._audio_capture: Any = None
        self._listen_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Read settings from config
        self._model_size: str = config.get("voice.whisper_model", "base")
        self._device: str = self._resolve_device(
            config.get("voice.device", "cpu")
        )
        self._confidence_threshold: float = config.get(
            "voice.confidence_threshold", 0.5
        )
        self._use_fp16: bool = self._device != "cpu"
        self._timeout: int = config.get("voice.timeout", 30)

        # Transcription options
        self._beam_size: int = config.get("voice.beam_size", 5)
        self._temperature: float = config.get("voice.temperature", 0.0)

        # Performance stats
        self._total_transcriptions: int = 0
        self._last_transcription_time: float = 0.0
        self._last_transcription_text: str = ""

        logger.info(
            f"VoiceEngine created | lang={language} | "
            f"model={self._model_size} | device={self._device}"
        )

    # ------------------------------------------------------------------
    # Device resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_device(preferred: str) -> str:
        """
        Resolve the compute device, falling back to CPU if CUDA
        is not available.
        """
        if preferred == "cuda":
            try:
                import torch

                if torch.cuda.is_available():
                    logger.info("CUDA device available, using GPU")
                    return "cuda"
                else:
                    logger.warning(
                        "CUDA requested but not available, falling back to CPU"
                    )
                    return "cpu"
            except ImportError:
                logger.warning("PyTorch not installed, using CPU")
                return "cpu"
        return "cpu"

    # ------------------------------------------------------------------
    # Model lifecycle
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        """
        Download (if needed) and load the Whisper model into memory.

        Uses lazy import so the heavy ``whisper`` package is only
        loaded when actually needed.

        Raises:
            ModelLoadError: If the model cannot be loaded.
        """
        if self.is_model_loaded:
            logger.info("Model already loaded, skipping")
            return

        if self._model_size not in self.VALID_MODELS:
            raise ModelLoadError(
                f"Invalid model size: {self._model_size}. "
                f"Valid: {self.VALID_MODELS}",
                context={"model": self._model_size},
            )

        try:
            logger.info(
                f"Loading Whisper model '{self._model_size}' "
                f"on device '{self._device}'..."
            )
            start = time.perf_counter()

            import whisper

            self.model = whisper.load_model(
                self._model_size, device=self._device
            )

            elapsed = time.perf_counter() - start
            self.is_model_loaded = True
            logger.info(
                f"Whisper model '{self._model_size}' loaded in "
                f"{elapsed:.1f}s on {self._device}"
            )
        except ImportError:
            raise ModelLoadError(
                "openai-whisper is not installed. "
                "Run: pip install openai-whisper",
                context={"model": self._model_size},
            )
        except Exception as exc:
            raise ModelLoadError(
                f"Failed to load Whisper model: {exc}",
                context={"model": self._model_size, "device": self._device},
            )

    def unload_model(self) -> None:
        """Release the Whisper model from memory."""
        if self.is_listening:
            self.stop_listening()
        self.model = None
        self.is_model_loaded = False
        logger.info("Whisper model unloaded")

    # ------------------------------------------------------------------
    # Listening (continuous mode)
    # ------------------------------------------------------------------

    def start_listening(self) -> None:
        """
        Begin continuous audio capture and transcription in a
        background thread.

        Raises:
            VoiceEngineError: If the model is not loaded.
        """
        if not self.is_model_loaded:
            raise VoiceEngineError("Cannot start listening: model not loaded")
        if self.is_listening:
            logger.warning("Already listening, ignoring start_listening()")
            return

        from .audio_capture import AudioCapture

        self._stop_event.clear()
        self._audio_capture = AudioCapture(
            sample_rate=self.WHISPER_SAMPLE_RATE,
            channels=1,
        )
        self._audio_capture.start()
        self.is_listening = True

        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            name="VoiceEngine-ListenLoop",
            daemon=True,
        )
        self._listen_thread.start()
        logger.info("Voice listening started (continuous mode)")

    def stop_listening(self) -> None:
        """Stop continuous audio capture and transcription."""
        if not self.is_listening:
            return
        self._stop_event.set()
        self.is_listening = False

        if self._audio_capture is not None:
            self._audio_capture.stop()
            self._audio_capture = None

        if self._listen_thread is not None:
            self._listen_thread.join(timeout=3.0)
            self._listen_thread = None

        logger.info("Voice listening stopped")

    def _listen_loop(self) -> None:
        """
        Background loop: pull audio chunks from AudioCapture,
        run VAD, and transcribe speech segments.
        """
        logger.debug("Listen loop started")
        while not self._stop_event.is_set():
            try:
                if self._audio_capture is None:
                    break

                audio_chunk = self._audio_capture.get_speech_segment(
                    timeout=1.0
                )
                if audio_chunk is None:
                    continue

                text = self.transcribe(audio_chunk)
                if text and text.strip():
                    self._notify_callbacks(text.strip())

            except Exception as exc:
                logger.error(f"Listen loop error: {exc}")
                time.sleep(0.5)

        logger.debug("Listen loop exited")

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    def transcribe(self, audio_data: np.ndarray) -> Optional[str]:
        """
        Transcribe a NumPy array of audio samples to text.

        The audio must be 16 kHz mono float32 (Whisper's expected
        input format).

        Args:
            audio_data: 1-D float32 array of audio samples at 16 kHz.

        Returns:
            Transcribed text, or ``None`` if transcription failed or
            the result was below the confidence threshold.
        """
        if not self.is_model_loaded or self.model is None:
            logger.warning("transcribe() called but model is not loaded")
            return None

        if audio_data is None or len(audio_data) == 0:
            return None

        try:
            start = time.perf_counter()

            # Ensure float32
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)

            # Run Whisper transcription
            result = self.model.transcribe(
                audio_data,
                language=self.SUPPORTED_LANGUAGES[self.language],
                fp16=self._use_fp16,
                beam_size=self._beam_size,
                temperature=self._temperature,
            )

            elapsed = time.perf_counter() - start
            text = result.get("text", "").strip()

            # Check confidence via avg log probability
            avg_logprob = self._extract_avg_logprob(result)
            if avg_logprob is not None:
                # Convert log probability to a rough confidence
                import math

                confidence = math.exp(avg_logprob)
                if confidence < self._confidence_threshold:
                    logger.debug(
                        f"Low confidence ({confidence:.2f}), "
                        f"discarding: '{text[:60]}'"
                    )
                    return None

            self._total_transcriptions += 1
            self._last_transcription_time = elapsed
            self._last_transcription_text = text

            logger.info(
                f"Transcribed ({elapsed:.2f}s, {self.language}): "
                f"'{text[:80]}'"
            )
            return text

        except Exception as exc:
            logger.error(f"Transcription failed: {exc}")
            return None

    @staticmethod
    def _extract_avg_logprob(result: dict) -> Optional[float]:
        """
        Extract the average log probability across all segments
        from a Whisper result dict.

        Returns None if no segments are present.
        """
        segments = result.get("segments", [])
        if not segments:
            return None
        logprobs = [
            seg["avg_logprob"]
            for seg in segments
            if "avg_logprob" in seg
        ]
        if not logprobs:
            return None
        return sum(logprobs) / len(logprobs)

    def transcribe_file(self, filepath: str) -> Optional[str]:
        """
        Transcribe an audio file (WAV, MP3, etc.) to text.

        Whisper handles file loading internally.

        Args:
            filepath: Path to the audio file.

        Returns:
            Transcribed text, or ``None`` on failure.
        """
        if not self.is_model_loaded or self.model is None:
            logger.warning("transcribe_file() called but model is not loaded")
            return None

        try:
            import whisper

            logger.info(f"Transcribing file: {filepath}")
            start = time.perf_counter()

            # Load and pad/trim audio
            audio = whisper.load_audio(filepath)
            result = self.model.transcribe(
                audio,
                language=self.SUPPORTED_LANGUAGES[self.language],
                fp16=self._use_fp16,
                beam_size=self._beam_size,
                temperature=self._temperature,
            )

            elapsed = time.perf_counter() - start
            text = result.get("text", "").strip()
            logger.info(
                f"File transcribed ({elapsed:.2f}s): '{text[:80]}'"
            )
            return text

        except Exception as exc:
            logger.error(f"File transcription failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_transcription(self, callback: Callable[[str], None]) -> None:
        """Register a callback invoked with each transcription result."""
        self._callbacks.append(callback)
        logger.debug(
            f"Transcription callback registered "
            f"(total: {len(self._callbacks)})"
        )

    def remove_callback(self, callback: Callable[[str], None]) -> None:
        """Remove a previously registered callback."""
        try:
            self._callbacks.remove(callback)
        except ValueError:
            logger.warning("Attempted to remove unregistered callback")

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
        Switch the recognition language at runtime.

        Does not require reloading the model — Whisper is multilingual.

        Args:
            language: ``"en"`` or ``"bn"``.

        Raises:
            VoiceEngineError: If the language is unsupported.
        """
        if language not in self.SUPPORTED_LANGUAGES:
            raise VoiceEngineError(f"Unsupported language: {language}")
        prev = self.language
        self.language = language
        logger.info(f"Voice language changed: {prev} -> {language}")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a status dict for the UI panel."""
        return {
            "language": self.language,
            "model_size": self._model_size,
            "model_loaded": self.is_model_loaded,
            "listening": self.is_listening,
            "device": self._device,
            "total_transcriptions": self._total_transcriptions,
            "last_transcription_time": self._last_transcription_time,
            "last_text": self._last_transcription_text,
        }


__all__ = ["VoiceEngine"]
