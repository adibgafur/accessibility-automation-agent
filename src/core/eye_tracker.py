"""
Eye & Nose Tracking Engine - MediaPipe + OpenCV Integration.

Provides:
    - Real-time nose-tip position tracking (used as cursor pointer)
    - Eye-blink detection (single blink = left-click, double = right-click)
    - Calibration workflow
    - Jitter smoothing via exponential moving average

This module will be fully implemented in Phase 3.
Current state: interface stubs with logging.
"""

import time
from typing import Callable, Dict, List, Optional, Tuple

from loguru import logger

from ..utils.config_manager import config
from ..utils.error_handler import EyeTrackingError, CameraError


class EyeTracker:
    """
    Face-mesh-based eye and nose tracker using MediaPipe.

    Maps the nose-tip landmark to screen coordinates so the user can
    control the cursor by moving their head.  Blink detection triggers
    click events.

    Usage (Phase 3+):
        tracker = EyeTracker()
        tracker.start()
        pos = tracker.get_nose_position()   # (x, y) on screen
        if tracker.detect_blink():
            mouse.click()
    """

    def __init__(self) -> None:
        self._cap = None              # cv2.VideoCapture
        self._face_mesh = None        # mediapipe FaceMesh
        self.is_running: bool = False
        self.is_calibrated: bool = False

        # Current tracking data
        self._nose_position: Optional[Tuple[int, int]] = None
        self._left_ear: float = 1.0   # eye-aspect-ratio (left)
        self._right_ear: float = 1.0  # eye-aspect-ratio (right)

        # Blink state
        self._last_blink_time: float = 0.0
        self._blink_count: int = 0

        # Callbacks
        self._on_blink: List[Callable[[], None]] = []
        self._on_double_blink: List[Callable[[], None]] = []

        # Settings from config
        self._camera_index: int = config.get("eye_tracking.camera_index", 0)
        self._fps: int = config.get("eye_tracking.fps", 30)
        self._smoothing: float = config.get("eye_tracking.smoothing_factor", 0.7)
        self._ear_threshold: float = config.get(
            "blink_detection.eye_aspect_ratio_threshold", 0.2
        )
        self._double_blink_ms: int = config.get(
            "blink_detection.double_blink_timeout", 300
        )
        self._jitter_threshold: int = config.get(
            "eye_tracking.jitter_threshold", 5
        )

        # Calibration data
        self._calibration_points: List[Tuple[int, int]] = []
        self._screen_width: int = 1920
        self._screen_height: int = 1080

        logger.info(
            f"EyeTracker created | camera={self._camera_index} | "
            f"fps={self._fps} | smoothing={self._smoothing}"
        )

    # ------------------------------------------------------------------
    # Camera lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Open the camera and initialise MediaPipe FaceMesh.

        Raises:
            CameraError: If the camera cannot be opened.
        """
        try:
            logger.info(f"Opening camera index {self._camera_index}...")
            # TODO: Phase 3 implementation
            # import cv2
            # self._cap = cv2.VideoCapture(self._camera_index)
            # if not self._cap.isOpened():
            #     raise CameraError("Camera failed to open")
            # import mediapipe as mp
            # self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            #     max_num_faces=1,
            #     refine_landmarks=True,
            #     min_detection_confidence=0.5,
            #     min_tracking_confidence=0.5,
            # )
            self.is_running = True
            logger.info("EyeTracker started (stub)")
        except CameraError:
            raise
        except Exception as exc:
            raise CameraError(f"Failed to start eye tracker: {exc}")

    def stop(self) -> None:
        """Release camera and clean up resources."""
        if self._cap is not None:
            # self._cap.release()
            pass
        self._cap = None
        self._face_mesh = None
        self.is_running = False
        logger.info("EyeTracker stopped")

    # ------------------------------------------------------------------
    # Tracking
    # ------------------------------------------------------------------

    def get_nose_position(self) -> Optional[Tuple[int, int]]:
        """
        Return the current nose-tip position mapped to screen coordinates.

        Returns:
            ``(x, y)`` tuple or ``None`` if tracking is inactive.
        """
        # TODO: Phase 3 - read frame, detect landmarks, map to screen
        return self._nose_position

    def detect_blink(self) -> bool:
        """
        Check whether the user blinked since the last call.

        Returns:
            ``True`` if a blink was detected.
        """
        # TODO: Phase 3 - compute EAR from landmarks
        return False

    def detect_double_blink(self) -> bool:
        """
        Check whether the user performed a double-blink (right-click).

        Returns:
            ``True`` if two blinks occurred within the timeout window.
        """
        # TODO: Phase 3
        return False

    # ------------------------------------------------------------------
    # Smoothing
    # ------------------------------------------------------------------

    def _smooth_position(
        self, new_x: int, new_y: int
    ) -> Tuple[int, int]:
        """
        Apply exponential moving average to reduce jitter.

        Args:
            new_x: Raw detected X.
            new_y: Raw detected Y.

        Returns:
            Smoothed ``(x, y)`` coordinates.
        """
        if self._nose_position is None:
            return (new_x, new_y)

        alpha = self._smoothing
        sx = int(alpha * self._nose_position[0] + (1 - alpha) * new_x)
        sy = int(alpha * self._nose_position[1] + (1 - alpha) * new_y)
        return (sx, sy)

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def calibrate(self, screen_width: int = 1920, screen_height: int = 1080) -> None:
        """
        Run calibration to map nose range to screen area.

        Args:
            screen_width:  Monitor width in pixels.
            screen_height: Monitor height in pixels.
        """
        self._screen_width = screen_width
        self._screen_height = screen_height
        logger.info(
            f"Calibration started for {screen_width}x{screen_height}"
        )
        # TODO: Phase 3 - multi-point calibration wizard
        self.is_calibrated = True
        logger.info("Calibration completed (stub)")

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_blink(self, callback: Callable[[], None]) -> None:
        """Register callback for single-blink events."""
        self._on_blink.append(callback)

    def on_double_blink(self, callback: Callable[[], None]) -> None:
        """Register callback for double-blink events."""
        self._on_double_blink.append(callback)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict:
        """Return a status dict for the UI panel."""
        return {
            "running": self.is_running,
            "calibrated": self.is_calibrated,
            "nose_position": self._nose_position,
            "camera_index": self._camera_index,
            "fps": self._fps,
            "smoothing": self._smoothing,
        }


__all__ = ["EyeTracker"]
