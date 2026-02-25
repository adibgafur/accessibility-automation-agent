"""
Audio Capture Module for the Accessibility Automation Agent.

Provides real-time microphone input via ``sounddevice`` with:
    - Configurable sample rate, channels, and chunk size
    - Energy-based Voice Activity Detection (VAD)
    - Speech segment buffering (collects audio while the user speaks,
      returns the complete utterance when silence is detected)
    - Thread-safe queue for consumer (VoiceEngine) integration
    - Microphone device enumeration

Designed for low-spec hardware (4 GB RAM, Intel i3):
    - Lightweight energy-based VAD (no ML model required)
    - Small ring buffer to limit memory usage
    - Configurable via config/default_settings.yaml
"""

import collections
import queue
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

from ..utils.config_manager import config
from ..utils.error_handler import VoiceEngineError


class AudioCapture:
    """
    Real-time microphone capture with voice activity detection.

    Audio is captured in small chunks. An energy-based VAD determines
    whether each chunk contains speech. Consecutive speech chunks are
    accumulated into a speech segment and placed on an internal queue.
    The VoiceEngine pulls complete segments via :meth:`get_speech_segment`.

    Usage:
        cap = AudioCapture(sample_rate=16000, channels=1)
        cap.start()
        segment = cap.get_speech_segment(timeout=5.0)
        cap.stop()
    """

    def __init__(
        self,
        sample_rate: int = 16_000,
        channels: int = 1,
        chunk_duration_ms: int = 30,
        device_index: Optional[int] = None,
    ) -> None:
        """
        Args:
            sample_rate:       Audio sample rate in Hz (default 16 000 for Whisper).
            channels:          Number of audio channels (1 = mono).
            chunk_duration_ms: Duration of each audio chunk in milliseconds.
            device_index:      Microphone device index (None = system default).
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_duration_ms = chunk_duration_ms
        self.device_index = device_index

        # Derived
        self._chunk_samples = int(sample_rate * chunk_duration_ms / 1000)

        # VAD parameters (from config or defaults)
        self._energy_threshold: float = config.get(
            "voice.vad_energy_threshold", 0.01
        )
        self._silence_duration_ms: int = config.get(
            "voice.vad_silence_duration_ms", 800
        )
        self._min_speech_duration_ms: int = config.get(
            "voice.vad_min_speech_duration_ms", 300
        )
        self._max_speech_duration_s: float = config.get(
            "voice.vad_max_speech_duration_s", 30.0
        )
        # Pre-speech padding: how many chunks of audio to keep before
        # speech onset so the beginning of the utterance is not clipped
        self._pre_speech_chunks: int = config.get(
            "voice.vad_pre_speech_chunks", 10
        )

        # Internal state
        self._stream: Any = None
        self._is_running = False
        self._stop_event = threading.Event()

        # Ring buffer for pre-speech padding
        self._ring_buffer: collections.deque = collections.deque(
            maxlen=self._pre_speech_chunks
        )

        # Accumulator for ongoing speech
        self._speech_chunks: List[np.ndarray] = []
        self._speech_start_time: float = 0.0
        self._silence_start_time: float = 0.0
        self._in_speech: bool = False

        # Output queue of complete speech segments
        self._segment_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=10)

        logger.info(
            f"AudioCapture created | rate={sample_rate} | "
            f"chunk={chunk_duration_ms}ms | "
            f"energy_threshold={self._energy_threshold}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Open the audio input stream and begin capturing.

        Raises:
            VoiceEngineError: If the stream cannot be opened.
        """
        if self._is_running:
            logger.warning("AudioCapture already running")
            return

        try:
            import sounddevice as sd

            self._stop_event.clear()
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                blocksize=self._chunk_samples,
                device=self.device_index,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._is_running = True
            logger.info("Audio capture started")
        except ImportError:
            raise VoiceEngineError(
                "sounddevice is not installed. "
                "Run: pip install sounddevice"
            )
        except Exception as exc:
            raise VoiceEngineError(
                f"Failed to open audio stream: {exc}",
                context={"device": self.device_index},
            )

    def stop(self) -> None:
        """Stop capturing and close the audio stream."""
        if not self._is_running:
            return
        self._stop_event.set()
        self._is_running = False

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:
                logger.warning(f"Error closing audio stream: {exc}")
            self._stream = None

        # Flush any in-progress speech
        self._flush_speech()
        self._speech_chunks.clear()
        self._in_speech = False

        logger.info("Audio capture stopped")

    def get_speech_segment(
        self, timeout: Optional[float] = None
    ) -> Optional[np.ndarray]:
        """
        Block until a complete speech segment is available.

        Args:
            timeout: Max seconds to wait. ``None`` blocks forever.

        Returns:
            1-D float32 NumPy array of audio, or ``None`` on timeout.
        """
        try:
            return self._segment_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def is_running(self) -> bool:
        return self._is_running

    # ------------------------------------------------------------------
    # Sounddevice callback (runs in audio thread)
    # ------------------------------------------------------------------

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        """
        Called by sounddevice for each audio chunk.

        Performs energy-based VAD and accumulates speech segments.
        """
        if status:
            logger.warning(f"Audio callback status: {status}")

        # Flatten to 1-D mono
        chunk = indata[:, 0].copy() if indata.ndim > 1 else indata.copy().ravel()
        energy = float(np.mean(chunk ** 2))
        is_speech = energy > self._energy_threshold
        now = time.monotonic()

        if not self._in_speech:
            # Store chunk in ring buffer for pre-speech padding
            self._ring_buffer.append(chunk)

            if is_speech:
                # Speech onset: flush ring buffer as pre-padding
                self._in_speech = True
                self._speech_start_time = now
                self._silence_start_time = 0.0
                self._speech_chunks = list(self._ring_buffer)
                self._speech_chunks.append(chunk)
                logger.debug(
                    f"Speech onset detected (energy={energy:.5f})"
                )
        else:
            # We are in speech mode
            self._speech_chunks.append(chunk)

            if is_speech:
                self._silence_start_time = 0.0
            else:
                if self._silence_start_time == 0.0:
                    self._silence_start_time = now
                else:
                    silence_ms = (now - self._silence_start_time) * 1000
                    if silence_ms >= self._silence_duration_ms:
                        # Silence long enough — end of utterance
                        self._flush_speech()

            # Guard: max duration exceeded
            if now - self._speech_start_time > self._max_speech_duration_s:
                logger.warning("Max speech duration exceeded, flushing")
                self._flush_speech()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _flush_speech(self) -> None:
        """
        Concatenate accumulated speech chunks and put the segment
        on the output queue if it exceeds the minimum duration.
        """
        if not self._speech_chunks:
            self._in_speech = False
            return

        segment = np.concatenate(self._speech_chunks)
        duration_ms = len(segment) / self.sample_rate * 1000

        self._speech_chunks.clear()
        self._ring_buffer.clear()
        self._in_speech = False

        if duration_ms < self._min_speech_duration_ms:
            logger.debug(
                f"Discarding short segment ({duration_ms:.0f}ms < "
                f"{self._min_speech_duration_ms}ms)"
            )
            return

        logger.debug(
            f"Speech segment ready: {duration_ms:.0f}ms, "
            f"{len(segment)} samples"
        )

        try:
            self._segment_queue.put_nowait(segment)
        except queue.Full:
            # Drop oldest segment to make room
            try:
                self._segment_queue.get_nowait()
            except queue.Empty:
                pass
            self._segment_queue.put_nowait(segment)
            logger.warning("Segment queue full, dropped oldest segment")

    # ------------------------------------------------------------------
    # Device enumeration
    # ------------------------------------------------------------------

    @staticmethod
    def list_devices() -> List[Dict[str, Any]]:
        """
        Enumerate available audio input devices.

        Returns:
            List of dicts with keys: ``index``, ``name``,
            ``max_input_channels``, ``default_samplerate``.
        """
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            inputs = []
            for i, dev in enumerate(devices):
                if dev["max_input_channels"] > 0:
                    inputs.append(
                        {
                            "index": i,
                            "name": dev["name"],
                            "max_input_channels": dev["max_input_channels"],
                            "default_samplerate": dev["default_samplerate"],
                        }
                    )
            return inputs
        except ImportError:
            logger.warning("sounddevice not installed, cannot list devices")
            return []
        except Exception as exc:
            logger.error(f"Failed to list audio devices: {exc}")
            return []

    @staticmethod
    def get_default_device() -> Optional[Dict[str, Any]]:
        """Return info about the default input device, or None."""
        try:
            import sounddevice as sd

            dev = sd.query_devices(kind="input")
            return {
                "name": dev["name"],
                "max_input_channels": dev["max_input_channels"],
                "default_samplerate": dev["default_samplerate"],
            }
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return status dict for UI / debugging."""
        return {
            "running": self._is_running,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "chunk_duration_ms": self.chunk_duration_ms,
            "device_index": self.device_index,
            "in_speech": self._in_speech,
            "queue_size": self._segment_queue.qsize(),
            "energy_threshold": self._energy_threshold,
        }


__all__ = ["AudioCapture"]
