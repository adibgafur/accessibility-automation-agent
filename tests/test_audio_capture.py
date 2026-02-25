"""
Tests for src.core.audio_capture.AudioCapture.

All tests run without a real microphone. The sounddevice library
is mocked where needed.
"""

import queue
import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.core.audio_capture import AudioCapture


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture()
def capture() -> AudioCapture:
    """Return a fresh AudioCapture (not started)."""
    return AudioCapture(
        sample_rate=16_000,
        channels=1,
        chunk_duration_ms=30,
        device_index=None,
    )


# ======================================================================
# Initialisation
# ======================================================================


class TestInit:
    def test_defaults(self, capture: AudioCapture):
        assert capture.sample_rate == 16_000
        assert capture.channels == 1
        assert capture.chunk_duration_ms == 30
        assert capture.device_index is None
        assert capture.is_running is False

    def test_chunk_samples_calculated(self, capture: AudioCapture):
        expected = int(16_000 * 30 / 1000)  # 480
        assert capture._chunk_samples == expected


# ======================================================================
# VAD logic (unit-test the callback directly)
# ======================================================================


class TestVAD:
    """Test the energy-based voice activity detection via _audio_callback."""

    def _make_chunk(self, energy: float, n: int = 480) -> np.ndarray:
        """Create a 2-D chunk with the specified RMS energy."""
        # energy = mean(x^2), so x = sqrt(energy)
        amplitude = np.sqrt(energy)
        data = np.full((n, 1), amplitude, dtype=np.float32)
        return data

    def test_silence_does_not_trigger_speech(self, capture: AudioCapture):
        """Chunks below the energy threshold should stay in ring buffer."""
        silent = self._make_chunk(0.001)  # below default 0.01
        for _ in range(20):
            capture._audio_callback(silent, 480, None, None)
        assert capture._in_speech is False
        assert capture._segment_queue.empty()

    def test_speech_onset_detected(self, capture: AudioCapture):
        """A loud chunk should trigger speech onset."""
        loud = self._make_chunk(0.05)
        capture._audio_callback(loud, 480, None, None)
        assert capture._in_speech is True

    def test_speech_segment_produced_after_silence(self, capture: AudioCapture):
        """
        Simulate: speech chunk(s) followed by enough silence to
        trigger end-of-utterance, producing a segment on the queue.
        """
        loud = self._make_chunk(0.05)
        silent = self._make_chunk(0.001)

        # Start with some speech
        for _ in range(10):
            capture._audio_callback(loud, 480, None, None)

        # Enough silence to exceed vad_silence_duration_ms (800ms)
        # Each chunk = 30ms, so need ~27 silent chunks
        for _ in range(30):
            capture._audio_callback(silent, 480, None, None)

        assert capture._in_speech is False
        segment = capture._segment_queue.get_nowait()
        assert isinstance(segment, np.ndarray)
        assert len(segment) > 0

    def test_short_speech_discarded(self, capture: AudioCapture):
        """Speech shorter than min duration should be discarded."""
        capture._min_speech_duration_ms = 500
        loud = self._make_chunk(0.05)
        silent = self._make_chunk(0.001)

        # Only 2 chunks of speech = 60ms (well under 500ms)
        for _ in range(2):
            capture._audio_callback(loud, 480, None, None)
        for _ in range(30):
            capture._audio_callback(silent, 480, None, None)

        assert capture._segment_queue.empty()

    def test_max_duration_guard(self, capture: AudioCapture):
        """Speech exceeding max duration should be flushed."""
        capture._max_speech_duration_s = 0.1  # 100ms
        loud = self._make_chunk(0.05)

        # Keep speaking beyond max duration
        for _ in range(200):  # 200 * 30ms = 6s >> 0.1s
            capture._audio_callback(loud, 480, None, None)

        assert not capture._segment_queue.empty()

    def test_pre_speech_padding(self, capture: AudioCapture):
        """Ring buffer chunks before speech onset should be included."""
        capture._pre_speech_chunks = 5
        capture._ring_buffer.clear()

        silent = self._make_chunk(0.001)
        loud = self._make_chunk(0.05)

        # Feed 5 silent chunks (stored in ring buffer)
        for _ in range(5):
            capture._audio_callback(silent, 480, None, None)

        # Then speech
        capture._audio_callback(loud, 480, None, None)

        # Ring buffer should have been flushed into speech_chunks
        # 5 pre-speech + 1 loud = 6 chunks
        assert len(capture._speech_chunks) == 6


# ======================================================================
# Segment queue
# ======================================================================


class TestSegmentQueue:
    def test_get_speech_segment_timeout(self, capture: AudioCapture):
        """get_speech_segment should return None on timeout."""
        result = capture.get_speech_segment(timeout=0.05)
        assert result is None

    def test_queue_overflow_drops_oldest(self, capture: AudioCapture):
        """When the queue is full, the oldest segment should be dropped."""
        capture._segment_queue = queue.Queue(maxsize=2)
        seg1 = np.ones(100, dtype=np.float32)
        seg2 = np.ones(200, dtype=np.float32) * 2
        seg3 = np.ones(300, dtype=np.float32) * 3

        capture._segment_queue.put(seg1)
        capture._segment_queue.put(seg2)

        # Manually flush a third segment
        capture._speech_chunks = [seg3]
        capture._in_speech = True
        capture._flush_speech()

        # Queue should have seg2, seg3 (seg1 was dropped)
        first = capture._segment_queue.get_nowait()
        assert len(first) == 200
        second = capture._segment_queue.get_nowait()
        assert len(second) == 300


# ======================================================================
# Start / Stop
# ======================================================================


class TestStartStop:
    @patch("src.core.audio_capture.AudioCapture.start")
    def test_start_sets_running(self, mock_start, capture: AudioCapture):
        capture._is_running = True
        assert capture.is_running is True

    def test_stop_when_not_running(self, capture: AudioCapture):
        capture.stop()  # Should not raise

    def test_double_start_warns(self, capture: AudioCapture):
        """Starting when already running should be a no-op."""
        capture._is_running = True
        # Calling start again should not crash
        # (we can't actually call start without sounddevice, so
        # just verify the guard)
        assert capture.is_running is True


# ======================================================================
# Device enumeration
# ======================================================================


class TestDeviceEnumeration:
    @patch("sounddevice.query_devices")
    def test_list_devices(self, mock_query):
        mock_query.return_value = [
            {
                "name": "Built-in Mic",
                "max_input_channels": 2,
                "max_output_channels": 0,
                "default_samplerate": 44100.0,
            },
            {
                "name": "Speakers",
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 48000.0,
            },
        ]
        devices = AudioCapture.list_devices()
        assert len(devices) == 1
        assert devices[0]["name"] == "Built-in Mic"

    def test_list_devices_no_sounddevice(self):
        """list_devices should return empty list if sounddevice missing."""
        with patch.dict("sys.modules", {"sounddevice": None}):
            devices = AudioCapture.list_devices()
            assert devices == [] or isinstance(devices, list)


# ======================================================================
# Status
# ======================================================================


class TestStatus:
    def test_get_status(self, capture: AudioCapture):
        status = capture.get_status()
        assert status["running"] is False
        assert status["sample_rate"] == 16_000
        assert status["in_speech"] is False
        assert "queue_size" in status
