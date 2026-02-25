"""
Tests for src.core.eye_tracker.

These tests verify the eye tracker's public API without requiring
a camera or MediaPipe. Heavy dependencies (cv2, mediapipe) are mocked.
"""

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, List
from unittest.mock import MagicMock, patch, PropertyMock, call

import numpy as np
import pytest

from src.core.eye_tracker import (
    EyeTracker,
    BlinkType,
    TrackingState,
    TrackingFrame,
    CalibrationData,
    CalibrationPoint,
    compute_ear,
    NOSE_TIP_INDEX,
    LEFT_EYE_INDICES,
    RIGHT_EYE_INDICES,
)
from src.utils.error_handler import CameraError, EyeTrackingError


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch):
    """Ensure config reads provide sensible defaults."""
    from src.utils.config_manager import ConfigManager

    dummy = {
        "eye_tracking": {
            "camera_index": 0,
            "fps": 30,
            "smoothing_factor": 0.7,
            "jitter_threshold": 5,
            "calibration_points": 9,
            "min_detection_confidence": 0.5,
            "min_tracking_confidence": 0.5,
        },
        "blink_detection": {
            "eye_aspect_ratio_threshold": 0.2,
            "double_blink_timeout": 300,
            "long_blink_duration_ms": 800,
            "consecutive_frames": 2,
        },
    }
    mgr = ConfigManager()
    for section, values in dummy.items():
        for k, v in values.items():
            mgr.set(f"{section}.{k}", v)


@pytest.fixture()
def tracker() -> EyeTracker:
    """Return a fresh EyeTracker instance (not started)."""
    return EyeTracker()


# ======================================================================
# Helper: Mock landmark
# ======================================================================


class MockLandmark:
    """Mimics a MediaPipe NormalizedLandmark."""

    def __init__(self, x: float, y: float, z: float = 0.0):
        self.x = x
        self.y = y
        self.z = z


def make_landmarks(
    nose_x: float = 0.5,
    nose_y: float = 0.5,
    left_ear: float = 0.35,
    right_ear: float = 0.35,
) -> list:
    """
    Create a mock list of 478 landmarks.

    Sets the nose tip at the given position and arranges eye landmarks
    so that compute_ear returns approximately the given EAR values.
    """
    # Create 478 default landmarks
    landmarks = [MockLandmark(0.5, 0.5) for _ in range(478)]

    # Set nose tip
    landmarks[NOSE_TIP_INDEX] = MockLandmark(nose_x, nose_y)

    # For EAR = (v1 + v2) / (2 * h)
    # We set h = 0.1, then v1 = v2 = ear * h = ear * 0.1
    # So vertical distances = ear * 0.1 and horizontal distance = 0.1

    for eye_indices, target_ear in [
        (LEFT_EYE_INDICES, left_ear),
        (RIGHT_EYE_INDICES, right_ear),
    ]:
        # p1 = outer corner (eye_indices[0])
        # p4 = inner corner (eye_indices[3])
        # p2 = upper lid (eye_indices[1])
        # p3 = upper lid (eye_indices[2])
        # p5 = lower lid (eye_indices[4])
        # p6 = lower lid (eye_indices[5])

        cx, cy = 0.5, 0.5
        h = 0.1  # horizontal distance

        landmarks[eye_indices[0]] = MockLandmark(cx - h / 2, cy)  # p1 outer
        landmarks[eye_indices[3]] = MockLandmark(cx + h / 2, cy)  # p4 inner

        v = target_ear * h  # vertical offset for desired EAR
        landmarks[eye_indices[1]] = MockLandmark(cx, cy - v / 2)  # p2 upper
        landmarks[eye_indices[5]] = MockLandmark(cx, cy + v / 2)  # p6 lower

        landmarks[eye_indices[2]] = MockLandmark(cx, cy - v / 2)  # p3 upper
        landmarks[eye_indices[4]] = MockLandmark(cx, cy + v / 2)  # p5 lower

    return landmarks


# ======================================================================
# Tests: Initialization
# ======================================================================


class TestEyeTrackerInit:
    """Tests for EyeTracker initialization."""

    def test_creates_instance(self, tracker):
        assert tracker is not None
        assert isinstance(tracker, EyeTracker)

    def test_initial_state_is_stopped(self, tracker):
        assert tracker._state == TrackingState.STOPPED
        assert not tracker.is_running
        assert not tracker.is_calibrated

    def test_initial_nose_position_is_none(self, tracker):
        assert tracker.get_nose_position() is None
        assert tracker.get_raw_nose() is None

    def test_initial_face_not_detected(self, tracker):
        assert not tracker.is_face_detected()

    def test_initial_ear_values(self, tracker):
        left, right = tracker.get_ear()
        assert left == 1.0
        assert right == 1.0

    def test_config_values_loaded(self, tracker):
        assert tracker._camera_index == 0
        assert tracker._fps == 30
        assert tracker._smoothing == 0.7
        assert tracker._ear_threshold == 0.2
        assert tracker._double_blink_ms == 300
        assert tracker._jitter_threshold == 5

    def test_callbacks_initially_empty(self, tracker):
        assert len(tracker._on_blink) == 0
        assert len(tracker._on_double_blink) == 0
        assert len(tracker._on_long_blink) == 0
        assert len(tracker._on_face_lost) == 0
        assert len(tracker._on_face_found) == 0
        assert len(tracker._on_position_update) == 0


# ======================================================================
# Tests: CalibrationData
# ======================================================================


class TestCalibrationData:
    """Tests for CalibrationData mapping logic."""

    def test_map_to_screen_center(self):
        """Nose at center of range should map to screen center."""
        cal = CalibrationData(
            nose_min_x=0.3,
            nose_max_x=0.7,
            nose_min_y=0.3,
            nose_max_y=0.7,
            screen_width=1920,
            screen_height=1080,
        )
        # Nose at 0.5, 0.5 — after mirror inversion x becomes 0.5
        # (1.0 - 0.5 = 0.5), which is center of [0.3, 0.7]
        x, y = cal.map_to_screen(0.5, 0.5)
        assert abs(x - 960) <= 1
        assert abs(y - 540) <= 1

    def test_map_to_screen_clamps_low(self):
        """Values below the calibrated range should clamp to 0."""
        cal = CalibrationData(
            nose_min_x=0.3,
            nose_max_x=0.7,
            nose_min_y=0.3,
            nose_max_y=0.7,
            screen_width=1920,
            screen_height=1080,
        )
        # Nose far to the right in camera (high x) → after mirror, low x → 0
        x, y = cal.map_to_screen(0.9, 0.9)
        # Mirrored: 1.0 - 0.9 = 0.1, which is below min_x 0.3 → 0
        assert x == 0
        # y = 0.9 is above max_y 0.7, so it should be at screen_height - 1
        assert y == 1079

    def test_map_to_screen_clamps_high(self):
        """Values above the calibrated range should clamp to max."""
        cal = CalibrationData(
            nose_min_x=0.3,
            nose_max_x=0.7,
            nose_min_y=0.3,
            nose_max_y=0.7,
            screen_width=1920,
            screen_height=1080,
        )
        # Nose far left in camera (low x) → after mirror, high x → max
        x, y = cal.map_to_screen(0.1, 0.1)
        assert x == 1919
        assert y == 0

    def test_map_to_screen_mirror_effect(self):
        """Moving head right (lower x in camera) should move cursor right."""
        cal = CalibrationData(
            nose_min_x=0.3,
            nose_max_x=0.7,
            nose_min_y=0.3,
            nose_max_y=0.7,
            screen_width=1000,
            screen_height=1000,
        )
        # Head moves right → camera x decreases → mirrored x increases
        x_left, _ = cal.map_to_screen(0.6, 0.5)   # head left in camera
        x_right, _ = cal.map_to_screen(0.4, 0.5)   # head right in camera
        assert x_right > x_left

    def test_map_with_zero_range_uses_fallback(self):
        """If min == max (no range), fallback range of 0.4 is used."""
        cal = CalibrationData(
            nose_min_x=0.5,
            nose_max_x=0.5,  # zero range
            nose_min_y=0.5,
            nose_max_y=0.5,
            screen_width=1920,
            screen_height=1080,
        )
        # Should not crash
        x, y = cal.map_to_screen(0.5, 0.5)
        assert 0 <= x < 1920
        assert 0 <= y < 1080


# ======================================================================
# Tests: compute_ear
# ======================================================================


class TestComputeEAR:
    """Tests for the Eye Aspect Ratio calculation."""

    def test_open_eye_high_ear(self):
        """Open eyes should have EAR > 0.25."""
        landmarks = make_landmarks(left_ear=0.35, right_ear=0.35)
        left_ear = compute_ear(landmarks, LEFT_EYE_INDICES)
        right_ear = compute_ear(landmarks, RIGHT_EYE_INDICES)

        assert left_ear > 0.25
        assert right_ear > 0.25

    def test_closed_eye_low_ear(self):
        """Closed eyes should have EAR < 0.15."""
        landmarks = make_landmarks(left_ear=0.05, right_ear=0.05)
        left_ear = compute_ear(landmarks, LEFT_EYE_INDICES)
        right_ear = compute_ear(landmarks, RIGHT_EYE_INDICES)

        assert left_ear < 0.15
        assert right_ear < 0.15

    def test_ear_symmetry(self):
        """Left and right EAR should be similar when set equally."""
        landmarks = make_landmarks(left_ear=0.3, right_ear=0.3)
        left = compute_ear(landmarks, LEFT_EYE_INDICES)
        right = compute_ear(landmarks, RIGHT_EYE_INDICES)

        assert abs(left - right) < 0.05

    def test_ear_with_zero_horizontal_returns_default(self):
        """If horizontal distance is 0, should return 1.0 (default open)."""
        landmarks = [MockLandmark(0.5, 0.5) for _ in range(478)]
        # All points at same position → horizontal distance = 0
        for idx in LEFT_EYE_INDICES:
            landmarks[idx] = MockLandmark(0.5, 0.5)

        ear = compute_ear(landmarks, LEFT_EYE_INDICES)
        assert ear == 1.0  # Default (avoid div by zero)

    def test_ear_handles_exception_gracefully(self):
        """On exception, compute_ear should return 1.0."""
        ear = compute_ear([], LEFT_EYE_INDICES)  # empty list → IndexError
        assert ear == 1.0


# ======================================================================
# Tests: Smoothing
# ======================================================================


class TestSmoothing:
    """Tests for position smoothing."""

    def test_first_position_no_smoothing(self, tracker):
        """First position should be returned as-is."""
        result = tracker._smooth_position(500, 300)
        assert result == (500, 300)

    def test_smoothing_applied(self, tracker):
        """Subsequent positions should be smoothed."""
        tracker._nose_position = (500, 300)
        result = tracker._smooth_position(600, 400)

        # alpha=0.7: sx = 0.7*500 + 0.3*600 = 530
        #            sy = 0.7*300 + 0.3*400 = 330
        assert result == (530, 330)

    def test_jitter_dead_zone(self, tracker):
        """Movement smaller than jitter threshold should be ignored."""
        tracker._nose_position = (500, 300)
        tracker._jitter_threshold = 10

        # Move by only 3 pixels — within dead zone
        result = tracker._smooth_position(503, 302)
        assert result == (500, 300)

    def test_movement_beyond_dead_zone(self, tracker):
        """Movement beyond jitter threshold should be smoothed."""
        tracker._nose_position = (500, 300)
        tracker._jitter_threshold = 5

        # Move by 20 pixels — outside dead zone
        result = tracker._smooth_position(520, 320)
        assert result != (500, 300)


# ======================================================================
# Tests: Calibration
# ======================================================================


class TestCalibration:
    """Tests for calibration workflow."""

    def test_calibrate_sets_state(self, tracker):
        tracker.calibrate(screen_width=1920, screen_height=1080)
        assert tracker._state == TrackingState.CALIBRATING
        assert not tracker.is_calibrated

    def test_calibrate_creates_points(self, tracker):
        tracker.calibrate(screen_width=1920, screen_height=1080, num_points=9)
        assert len(tracker._calibration.points) == 9

    def test_calibrate_creates_4_points(self, tracker):
        tracker.calibrate(screen_width=1920, screen_height=1080, num_points=4)
        assert len(tracker._calibration.points) == 4

    def test_calibration_grid_covers_screen(self, tracker):
        tracker.calibrate(screen_width=1920, screen_height=1080, num_points=9)
        points = tracker.get_calibration_points()

        xs = [p.screen_x for p in points]
        ys = [p.screen_y for p in points]

        # Grid should span from margin to margin
        assert min(xs) < 300    # near left edge
        assert max(xs) > 1600   # near right edge
        assert min(ys) < 200    # near top edge
        assert max(ys) > 800    # near bottom edge

    def test_calibration_points_not_captured_initially(self, tracker):
        tracker.calibrate(screen_width=1920, screen_height=1080, num_points=4)
        for point in tracker.get_calibration_points():
            assert not point.captured

    def test_get_next_uncaptured_point(self, tracker):
        tracker.calibrate(screen_width=1920, screen_height=1080, num_points=4)
        assert tracker.get_next_uncaptured_point() == 0

    def test_capture_calibration_point_no_face(self, tracker):
        """Cannot capture if no face is detected."""
        tracker.calibrate(num_points=4)
        result = tracker.capture_calibration_point(0)
        assert not result

    def test_capture_calibration_point_with_face(self, tracker):
        """Capture should succeed when face data is available."""
        tracker.calibrate(num_points=4)

        # Simulate face detection — set raw nose position
        tracker._raw_nose = (0.5, 0.5)
        tracker._face_detected = True

        result = tracker.capture_calibration_point(0)
        assert result
        assert tracker._calibration.points[0].captured

    def test_capture_invalid_index(self, tracker):
        tracker.calibrate(num_points=4)
        result = tracker.capture_calibration_point(10)
        assert not result

    def test_finalize_calibration(self, tracker):
        """Calibration should complete after all points are captured."""
        tracker.calibrate(screen_width=1920, screen_height=1080, num_points=4)

        # Simulate captured points at various nose positions
        positions = [(0.35, 0.35), (0.65, 0.35), (0.35, 0.65), (0.65, 0.65)]
        for i, (nx, ny) in enumerate(positions):
            tracker._raw_nose = (nx, ny)
            tracker._face_detected = True
            tracker.capture_calibration_point(i)

        assert tracker.is_calibrated
        assert tracker._calibration.is_valid
        assert tracker._state == TrackingState.RUNNING

    def test_finalize_calibration_sets_ranges(self, tracker):
        """After calibration, nose range should encompass captured points."""
        tracker.calibrate(screen_width=1920, screen_height=1080, num_points=4)

        positions = [(0.35, 0.35), (0.65, 0.35), (0.35, 0.65), (0.65, 0.65)]
        for i, (nx, ny) in enumerate(positions):
            tracker._raw_nose = (nx, ny)
            tracker._face_detected = True
            tracker.capture_calibration_point(i)

        cal = tracker._calibration
        assert cal.nose_min_x < 0.35
        assert cal.nose_max_x > 0.65
        assert cal.nose_min_y < 0.35
        assert cal.nose_max_y > 0.65


# ======================================================================
# Tests: Callbacks
# ======================================================================


class TestCallbacks:
    """Tests for callback registration."""

    def test_register_blink_callback(self, tracker):
        cb = MagicMock()
        tracker.on_blink(cb)
        assert cb in tracker._on_blink

    def test_register_double_blink_callback(self, tracker):
        cb = MagicMock()
        tracker.on_double_blink(cb)
        assert cb in tracker._on_double_blink

    def test_register_long_blink_callback(self, tracker):
        cb = MagicMock()
        tracker.on_long_blink(cb)
        assert cb in tracker._on_long_blink

    def test_register_face_lost_callback(self, tracker):
        cb = MagicMock()
        tracker.on_face_lost(cb)
        assert cb in tracker._on_face_lost

    def test_register_face_found_callback(self, tracker):
        cb = MagicMock()
        tracker.on_face_found(cb)
        assert cb in tracker._on_face_found

    def test_register_position_update_callback(self, tracker):
        cb = MagicMock()
        tracker.on_position_update(cb)
        assert cb in tracker._on_position_update

    def test_remove_all_callbacks(self, tracker):
        tracker.on_blink(MagicMock())
        tracker.on_double_blink(MagicMock())
        tracker.on_long_blink(MagicMock())
        tracker.on_face_lost(MagicMock())
        tracker.on_face_found(MagicMock())
        tracker.on_position_update(MagicMock())

        tracker.remove_all_callbacks()

        assert len(tracker._on_blink) == 0
        assert len(tracker._on_double_blink) == 0
        assert len(tracker._on_long_blink) == 0
        assert len(tracker._on_face_lost) == 0
        assert len(tracker._on_face_found) == 0
        assert len(tracker._on_position_update) == 0

    def test_fire_single_blink_calls_callbacks(self, tracker):
        cb1 = MagicMock()
        cb2 = MagicMock()
        tracker.on_blink(cb1)
        tracker.on_blink(cb2)

        tracker._fire_single_blink()

        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_fire_double_blink_calls_callbacks(self, tracker):
        cb = MagicMock()
        tracker.on_double_blink(cb)

        tracker._fire_double_blink()

        cb.assert_called_once()

    def test_fire_long_blink_calls_callbacks(self, tracker):
        cb = MagicMock()
        tracker.on_long_blink(cb)

        tracker._fire_long_blink()

        cb.assert_called_once()

    def test_callback_error_does_not_propagate(self, tracker):
        """Errors in callbacks should be caught, not propagated."""
        def bad_callback():
            raise RuntimeError("callback error")

        tracker.on_blink(bad_callback)

        # Should not raise
        tracker._fire_single_blink()


# ======================================================================
# Tests: Blink Detection Logic
# ======================================================================


class TestBlinkDetection:
    """Tests for the blink state machine."""

    def test_detect_blink_returns_false_when_stopped(self, tracker):
        assert not tracker.detect_blink()

    def test_detect_blink_returns_true_when_ear_below_threshold(self, tracker):
        tracker._left_ear = 0.1
        tracker._right_ear = 0.1
        assert tracker.detect_blink()

    def test_detect_blink_returns_false_when_ear_above_threshold(self, tracker):
        tracker._left_ear = 0.35
        tracker._right_ear = 0.35
        assert not tracker.detect_blink()

    def test_process_blink_increments_closed_frames(self, tracker):
        """Closed eyes should increment consecutive_closed_frames."""
        frame = TrackingFrame(
            left_ear=0.1,
            right_ear=0.1,
            face_detected=True,
        )
        tracker._process_blink(frame)
        assert tracker._consecutive_closed_frames == 1

    def test_process_blink_multiple_closed_frames(self, tracker):
        frame = TrackingFrame(
            left_ear=0.1,
            right_ear=0.1,
            face_detected=True,
        )
        tracker._process_blink(frame)
        tracker._process_blink(frame)
        tracker._process_blink(frame)
        assert tracker._consecutive_closed_frames == 3

    def test_open_frame_resets_closed_count(self, tracker):
        """Opening eyes should reset the closed frame counter."""
        closed = TrackingFrame(left_ear=0.1, right_ear=0.1, face_detected=True)
        open_frame = TrackingFrame(
            left_ear=0.35, right_ear=0.35, face_detected=True
        )

        tracker._process_blink(closed)
        tracker._process_blink(closed)
        tracker._process_blink(open_frame)

        assert tracker._consecutive_closed_frames == 0

    def test_single_frame_blink_ignored(self, tracker):
        """A single closed frame (< consecutive_frames threshold) should not
        trigger a blink."""
        cb = MagicMock()
        tracker.on_blink(cb)
        tracker._consecutive_frames_for_blink = 2

        closed = TrackingFrame(left_ear=0.1, right_ear=0.1, face_detected=True)
        open_frame = TrackingFrame(
            left_ear=0.35, right_ear=0.35, face_detected=True
        )

        # Only one closed frame
        tracker._process_blink(closed)
        tracker._process_blink(open_frame)

        # Wait for potential timer
        time.sleep(0.5)
        cb.assert_not_called()


# ======================================================================
# Tests: Face detection events
# ======================================================================


class TestFaceEvents:
    """Tests for face-found and face-lost transitions."""

    def test_face_found_fires_callback(self, tracker):
        cb = MagicMock()
        tracker.on_face_found(cb)

        frame = TrackingFrame(
            face_detected=True,
            screen_x=960,
            screen_y=540,
            nose_x=0.5,
            nose_y=0.5,
            left_ear=0.35,
            right_ear=0.35,
        )
        tracker._handle_face_detected(frame)

        cb.assert_called_once()

    def test_face_found_only_fires_on_transition(self, tracker):
        """face-found should only fire once when face first appears."""
        cb = MagicMock()
        tracker.on_face_found(cb)

        frame = TrackingFrame(
            face_detected=True,
            screen_x=960,
            screen_y=540,
            left_ear=0.35,
            right_ear=0.35,
        )

        tracker._handle_face_detected(frame)
        tracker._handle_face_detected(frame)
        tracker._handle_face_detected(frame)

        cb.assert_called_once()

    def test_face_lost_fires_callback(self, tracker):
        cb = MagicMock()
        tracker.on_face_lost(cb)

        # First, detect face
        tracker._face_detected = True

        # Then lose it
        tracker._handle_face_lost()

        cb.assert_called_once()

    def test_face_lost_only_fires_on_transition(self, tracker):
        """face-lost should only fire when transitioning from detected."""
        cb = MagicMock()
        tracker.on_face_lost(cb)

        # Not detected → lost: should NOT fire (was already not detected)
        tracker._handle_face_lost()
        cb.assert_not_called()

    def test_position_update_callback(self, tracker):
        cb = MagicMock()
        tracker.on_position_update(cb)

        frame = TrackingFrame(
            face_detected=True,
            screen_x=800,
            screen_y=600,
            left_ear=0.35,
            right_ear=0.35,
        )
        tracker._handle_face_detected(frame)

        cb.assert_called_once_with(800, 600)

    def test_nose_position_updated_on_face_detected(self, tracker):
        frame = TrackingFrame(
            face_detected=True,
            screen_x=123,
            screen_y=456,
            nose_x=0.4,
            nose_y=0.6,
            left_ear=0.3,
            right_ear=0.3,
        )
        tracker._handle_face_detected(frame)

        assert tracker.get_nose_position() == (123, 456)
        assert tracker.get_raw_nose() == (0.4, 0.6)
        assert tracker.is_face_detected()


# ======================================================================
# Tests: Configuration
# ======================================================================


class TestConfiguration:
    """Tests for runtime configuration changes."""

    def test_set_smoothing(self, tracker):
        tracker.set_smoothing(0.5)
        assert tracker._smoothing == 0.5

    def test_set_smoothing_clamps_low(self, tracker):
        tracker.set_smoothing(-0.5)
        assert tracker._smoothing == 0.0

    def test_set_smoothing_clamps_high(self, tracker):
        tracker.set_smoothing(1.5)
        assert tracker._smoothing == 0.99

    def test_set_ear_threshold(self, tracker):
        tracker.set_ear_threshold(0.25)
        assert tracker._ear_threshold == 0.25

    def test_set_ear_threshold_clamps_low(self, tracker):
        tracker.set_ear_threshold(0.05)
        assert tracker._ear_threshold == 0.1

    def test_set_ear_threshold_clamps_high(self, tracker):
        tracker.set_ear_threshold(0.8)
        assert tracker._ear_threshold == 0.5

    def test_set_camera(self, tracker):
        tracker.set_camera(2)
        assert tracker._camera_index == 2


# ======================================================================
# Tests: Status
# ======================================================================


class TestStatus:
    """Tests for status reporting."""

    def test_get_status_structure(self, tracker):
        status = tracker.get_status()

        assert "running" in status
        assert "state" in status
        assert "calibrated" in status
        assert "face_detected" in status
        assert "nose_position" in status
        assert "camera_index" in status
        assert "fps_target" in status
        assert "smoothing" in status
        assert "ear_threshold" in status
        assert "frame_count" in status

    def test_get_status_initial_values(self, tracker):
        status = tracker.get_status()

        assert status["running"] is False
        assert status["state"] == "STOPPED"
        assert status["calibrated"] is False
        assert status["face_detected"] is False
        assert status["nose_position"] is None

    def test_get_fps_no_data(self, tracker):
        assert tracker.get_fps() == 0.0

    def test_get_fps_with_data(self, tracker):
        # Simulate frame times of ~33ms each (≈30 fps)
        for _ in range(10):
            tracker._frame_times.append(0.033)

        fps = tracker.get_fps()
        assert 28.0 < fps < 32.0

    def test_get_performance_stats(self, tracker):
        stats = tracker.get_performance_stats()

        assert "fps" in stats
        assert "avg_latency_ms" in stats
        assert "total_frames" in stats
        assert "uptime_seconds" in stats
        assert "face_detected" in stats


# ======================================================================
# Tests: Camera lifecycle (mocked)
# ======================================================================


class TestCameraLifecycle:
    """Tests for start/stop with mocked cv2 and mediapipe."""

    @patch("src.core.eye_tracker.EyeTracker._detect_screen_size")
    def test_start_opens_camera(self, mock_screen, tracker):
        """start() should open camera and init FaceMesh."""
        mock_cv2 = MagicMock()
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.CAP_PROP_FRAME_WIDTH = 3
        mock_cv2.CAP_PROP_FRAME_HEIGHT = 4
        mock_cv2.CAP_PROP_FPS = 5

        mock_mp = MagicMock()
        mock_face_mesh_instance = MagicMock()
        mock_mp.solutions.face_mesh.FaceMesh.return_value = (
            mock_face_mesh_instance
        )

        mock_np = MagicMock()

        tracker._cv2 = mock_cv2
        tracker._mp = mock_mp
        tracker._np = mock_np

        tracker.start()

        try:
            assert tracker.is_running
            assert tracker._state == TrackingState.RUNNING
            mock_cv2.VideoCapture.assert_called_once_with(0)
        finally:
            tracker.stop()

    @patch("src.core.eye_tracker.EyeTracker._detect_screen_size")
    def test_start_raises_camera_error(self, mock_screen, tracker):
        """start() should raise CameraError if camera fails to open."""
        mock_cv2 = MagicMock()
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cv2.VideoCapture.return_value = mock_cap

        mock_mp = MagicMock()
        mock_np = MagicMock()

        tracker._cv2 = mock_cv2
        tracker._mp = mock_mp
        tracker._np = mock_np

        with pytest.raises(CameraError):
            tracker.start()

        assert tracker._state == TrackingState.ERROR

    def test_start_already_running(self, tracker):
        """Calling start() when already running should be a no-op."""
        tracker.is_running = True
        tracker.start()  # Should not raise

    def test_stop_when_not_running(self, tracker):
        """Calling stop() when not running should be safe."""
        tracker.stop()  # Should not raise

    @patch("src.core.eye_tracker.EyeTracker._detect_screen_size")
    def test_stop_releases_resources(self, mock_screen, tracker):
        """stop() should release camera and close FaceMesh."""
        mock_cv2 = MagicMock()
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.CAP_PROP_FRAME_WIDTH = 3
        mock_cv2.CAP_PROP_FRAME_HEIGHT = 4
        mock_cv2.CAP_PROP_FPS = 5

        mock_mp = MagicMock()
        mock_face_mesh = MagicMock()
        mock_mp.solutions.face_mesh.FaceMesh.return_value = mock_face_mesh

        tracker._cv2 = mock_cv2
        tracker._mp = mock_mp
        tracker._np = MagicMock()

        tracker.start()
        tracker.stop()

        assert not tracker.is_running
        assert tracker._state == TrackingState.STOPPED
        assert tracker._cap is None
        assert tracker._face_mesh is None
        mock_cap.release.assert_called_once()
        mock_face_mesh.close.assert_called_once()

    def test_pause_and_resume(self, tracker):
        """pause() and resume() should toggle state."""
        tracker._state = TrackingState.RUNNING

        tracker.pause()
        assert tracker._state == TrackingState.PAUSED

        tracker.resume()
        assert tracker._state == TrackingState.RUNNING

    def test_pause_when_not_running_no_op(self, tracker):
        """pause() should only work when running."""
        tracker._state = TrackingState.STOPPED
        tracker.pause()
        assert tracker._state == TrackingState.STOPPED

    def test_resume_when_not_paused_no_op(self, tracker):
        """resume() should only work when paused."""
        tracker._state = TrackingState.RUNNING
        tracker.resume()
        assert tracker._state == TrackingState.RUNNING


# ======================================================================
# Tests: Lazy imports
# ======================================================================


class TestLazyImports:
    """Tests for lazy import behaviour."""

    def test_ensure_imports_raises_on_missing_cv2(self, tracker):
        with patch.dict("sys.modules", {"cv2": None}):
            tracker._cv2 = None
            with pytest.raises(EyeTrackingError, match="OpenCV"):
                tracker._ensure_imports()

    def test_ensure_imports_raises_on_missing_mediapipe(self, tracker):
        import cv2 as real_cv2
        tracker._cv2 = MagicMock()  # cv2 available

        with patch.dict("sys.modules", {"mediapipe": None}):
            tracker._mp = None
            with pytest.raises(EyeTrackingError, match="MediaPipe"):
                tracker._ensure_imports()


# ======================================================================
# Tests: TrackingFrame
# ======================================================================


class TestTrackingFrame:
    """Tests for TrackingFrame dataclass."""

    def test_default_values(self):
        frame = TrackingFrame()
        assert frame.timestamp == 0.0
        assert frame.nose_x == 0.0
        assert frame.nose_y == 0.0
        assert frame.left_ear == 1.0
        assert frame.right_ear == 1.0
        assert not frame.face_detected
        assert frame.screen_x == 0
        assert frame.screen_y == 0

    def test_custom_values(self):
        frame = TrackingFrame(
            timestamp=123.456,
            nose_x=0.5,
            nose_y=0.6,
            left_ear=0.3,
            right_ear=0.25,
            face_detected=True,
            screen_x=960,
            screen_y=540,
        )
        assert frame.timestamp == 123.456
        assert frame.face_detected
        assert frame.screen_x == 960


# ======================================================================
# Tests: CalibrationPoint
# ======================================================================


class TestCalibrationPoint:
    """Tests for CalibrationPoint dataclass."""

    def test_default_not_captured(self):
        point = CalibrationPoint(screen_x=100, screen_y=200)
        assert not point.captured
        assert point.nose_x == 0.0
        assert point.nose_y == 0.0

    def test_captured_point(self):
        point = CalibrationPoint(
            screen_x=100,
            screen_y=200,
            nose_x=0.45,
            nose_y=0.55,
            captured=True,
        )
        assert point.captured
        assert point.nose_x == 0.45


# ======================================================================
# Tests: Quick calibration
# ======================================================================


class TestQuickCalibration:
    """Tests for the quick auto-calibration method."""

    def test_quick_calibrate_fails_when_not_running(self, tracker):
        result = tracker.quick_calibrate()
        assert not result

    def test_quick_calibrate_fails_when_no_face(self, tracker):
        tracker.is_running = True
        tracker._face_detected = False
        result = tracker.quick_calibrate()
        assert not result

    def test_quick_calibrate_succeeds_with_face(self, tracker):
        """Quick calibration should succeed with enough samples."""
        tracker.is_running = True
        tracker._face_detected = True
        tracker._state = TrackingState.RUNNING

        # Mock get_raw_nose to return varying positions
        positions = iter([
            (0.4, 0.4), (0.6, 0.4), (0.4, 0.6), (0.6, 0.6),
            (0.5, 0.5), (0.45, 0.55), (0.55, 0.45), (0.5, 0.5),
            (0.42, 0.48), (0.58, 0.52), (0.5, 0.5), (0.5, 0.5),
        ] * 10)  # Repeat to ensure enough samples

        def mock_raw_nose():
            try:
                return next(positions)
            except StopIteration:
                return (0.5, 0.5)

        tracker.get_raw_nose = mock_raw_nose

        result = tracker.quick_calibrate(duration=0.5)
        assert result
        assert tracker.is_calibrated
        assert tracker._calibration.is_valid


# ======================================================================
# Tests: List cameras (static method)
# ======================================================================


class TestListCameras:
    """Tests for camera enumeration."""

    @patch("src.core.eye_tracker.cv2", create=True)
    def test_list_cameras_returns_available(self, mock_cv2_module):
        """list_cameras should return info for cameras that open."""
        # We need to mock the import inside the static method
        with patch.dict("sys.modules", {"cv2": mock_cv2_module}):
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.side_effect = lambda prop: {
                mock_cv2_module.CAP_PROP_FRAME_WIDTH: 640,
                mock_cv2_module.CAP_PROP_FRAME_HEIGHT: 480,
            }.get(prop, 0)

            mock_cv2_module.VideoCapture.return_value = mock_cap
            mock_cv2_module.CAP_PROP_FRAME_WIDTH = 3
            mock_cv2_module.CAP_PROP_FRAME_HEIGHT = 4

            cameras = EyeTracker.list_cameras(max_index=2)

            assert len(cameras) == 2
            assert cameras[0]["index"] == 0
            assert cameras[1]["index"] == 1


# ======================================================================
# Tests: Enums
# ======================================================================


class TestEnums:
    """Tests for enum values."""

    def test_blink_type_values(self):
        assert BlinkType.NONE is not None
        assert BlinkType.SINGLE is not None
        assert BlinkType.DOUBLE is not None
        assert BlinkType.LONG is not None

    def test_tracking_state_values(self):
        assert TrackingState.STOPPED is not None
        assert TrackingState.STARTING is not None
        assert TrackingState.RUNNING is not None
        assert TrackingState.CALIBRATING is not None
        assert TrackingState.PAUSED is not None
        assert TrackingState.ERROR is not None

    def test_tracking_state_names(self):
        assert TrackingState.STOPPED.name == "STOPPED"
        assert TrackingState.RUNNING.name == "RUNNING"


# ======================================================================
# Tests: Thread safety
# ======================================================================


class TestThreadSafety:
    """Tests for thread-safe access to shared state."""

    def test_concurrent_position_reads(self, tracker):
        """Multiple threads should be able to read position safely."""
        tracker._nose_position = (500, 300)
        results = []

        def read_pos():
            for _ in range(100):
                pos = tracker.get_nose_position()
                if pos:
                    results.append(pos)

        threads = [threading.Thread(target=read_pos) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should return the same position
        assert all(r == (500, 300) for r in results)

    def test_concurrent_ear_reads(self, tracker):
        """Multiple threads should be able to read EAR safely."""
        tracker._left_ear = 0.3
        tracker._right_ear = 0.35
        results = []

        def read_ear():
            for _ in range(100):
                results.append(tracker.get_ear())

        threads = [threading.Thread(target=read_ear) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == (0.3, 0.35) for r in results)
