"""
Eye & Nose Tracking Engine - MediaPipe + OpenCV Integration.

Provides:
    - Real-time nose-tip position tracking (used as cursor pointer)
    - Eye-blink detection (single blink = left-click, double = right-click)
    - Multi-point calibration workflow mapping nose range to screen area
    - Jitter smoothing via exponential moving average
    - Background processing thread for continuous tracking
    - Long blink detection for drag/hold operations

Dependencies:
    - mediapipe (FaceMesh with refine_landmarks)
    - opencv-python (camera capture)
    - numpy (coordinate math)

Optimised for low-spec hardware (4GB RAM, Intel i3):
    - Single face detection only
    - Configurable FPS cap
    - Lazy imports of heavy libraries
    - Minimal per-frame allocations
"""

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Deque, Dict, List, Optional, Tuple

from loguru import logger

from ..utils.config_manager import config
from ..utils.error_handler import CameraError, EyeTrackingError


# ======================================================================
# MediaPipe FaceMesh Landmark Indices
# ======================================================================

# Nose tip landmark index in MediaPipe's 468-point face mesh
NOSE_TIP_INDEX = 1

# Left eye landmarks for EAR calculation (6 points)
# Using the refined iris landmarks when available
LEFT_EYE_INDICES = [362, 385, 387, 263, 373, 380]

# Right eye landmarks for EAR calculation (6 points)
RIGHT_EYE_INDICES = [33, 160, 158, 133, 153, 144]

# Forehead / chin for head pose stability reference
FOREHEAD_INDEX = 10
CHIN_INDEX = 152


# ======================================================================
# Enums and Data Classes
# ======================================================================


class BlinkType(Enum):
    """Types of blink events detected."""
    NONE = auto()
    SINGLE = auto()       # Left click
    DOUBLE = auto()       # Right click
    LONG = auto()         # Drag / hold


class TrackingState(Enum):
    """Current state of the eye tracker."""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    CALIBRATING = auto()
    PAUSED = auto()
    ERROR = auto()


@dataclass
class CalibrationPoint:
    """A single calibration reference point."""
    screen_x: int
    screen_y: int
    nose_x: float = 0.0
    nose_y: float = 0.0
    captured: bool = False


@dataclass
class TrackingFrame:
    """Data extracted from a single camera frame."""
    timestamp: float = 0.0
    nose_x: float = 0.0         # Normalised nose x (0..1)
    nose_y: float = 0.0         # Normalised nose y (0..1)
    left_ear: float = 1.0       # Left eye aspect ratio
    right_ear: float = 1.0      # Right eye aspect ratio
    face_detected: bool = False
    screen_x: int = 0           # Mapped screen x
    screen_y: int = 0           # Mapped screen y


@dataclass
class CalibrationData:
    """Stores calibration mapping from nose range to screen area."""
    nose_min_x: float = 0.3
    nose_max_x: float = 0.7
    nose_min_y: float = 0.3
    nose_max_y: float = 0.7
    screen_width: int = 1920
    screen_height: int = 1080
    points: List[CalibrationPoint] = field(default_factory=list)
    is_valid: bool = False

    def map_to_screen(self, nose_x: float, nose_y: float) -> Tuple[int, int]:
        """
        Map normalised nose coordinates to screen coordinates.

        The mapping inverts the x-axis (mirror effect) so moving your
        head right moves the cursor right.

        Args:
            nose_x: Normalised nose x position (0..1 from camera).
            nose_y: Normalised nose y position (0..1 from camera).

        Returns:
            (screen_x, screen_y) clamped to screen bounds.
        """
        # Invert x for mirror effect
        nose_x = 1.0 - nose_x

        # Normalise within calibrated range
        range_x = self.nose_max_x - self.nose_min_x
        range_y = self.nose_max_y - self.nose_min_y

        if range_x <= 0:
            range_x = 0.4  # fallback
        if range_y <= 0:
            range_y = 0.4

        norm_x = (nose_x - self.nose_min_x) / range_x
        norm_y = (nose_y - self.nose_min_y) / range_y

        # Clamp to [0, 1]
        norm_x = max(0.0, min(1.0, norm_x))
        norm_y = max(0.0, min(1.0, norm_y))

        screen_x = int(norm_x * self.screen_width)
        screen_y = int(norm_y * self.screen_height)

        # Final clamp to screen bounds
        screen_x = max(0, min(self.screen_width - 1, screen_x))
        screen_y = max(0, min(self.screen_height - 1, screen_y))

        return (screen_x, screen_y)


# ======================================================================
# Eye Aspect Ratio Calculator
# ======================================================================


def compute_ear(landmarks: list, eye_indices: List[int]) -> float:
    """
    Compute the Eye Aspect Ratio (EAR) for blink detection.

    EAR = (|p2-p6| + |p4-p4|) / (2 * |p1-p4|)

    Where p1..p6 are the six landmark points around the eye:
        p1 = outer corner, p4 = inner corner
        p2, p6 = upper lid, p3, p5 = lower lid

    A low EAR (<= threshold) indicates a closed eye (blink).

    Args:
        landmarks: List of MediaPipe NormalizedLandmark objects.
        eye_indices: Six landmark indices for one eye.

    Returns:
        EAR value (float). Typically 0.2-0.4 when open, <0.2 when closed.
    """
    try:
        # numpy is lazy-imported at module level in EyeTracker
        import numpy as np

        points = []
        for idx in eye_indices:
            lm = landmarks[idx]
            points.append([lm.x, lm.y])

        points = np.array(points, dtype=np.float64)

        # Vertical distances
        v1 = np.linalg.norm(points[1] - points[5])  # |p2-p6|
        v2 = np.linalg.norm(points[2] - points[4])  # |p3-p5|

        # Horizontal distance
        h = np.linalg.norm(points[0] - points[3])    # |p1-p4|

        if h < 1e-6:
            return 1.0  # Avoid division by zero

        ear = (v1 + v2) / (2.0 * h)
        return float(ear)

    except Exception:
        return 1.0  # Default to "open" on error


# ======================================================================
# Main EyeTracker Class
# ======================================================================


class EyeTracker:
    """
    Face-mesh-based eye and nose tracker using MediaPipe.

    Maps the nose-tip landmark to screen coordinates so the user can
    control the cursor by moving their head. Blink detection triggers
    click events.

    Features:
        - Nose-tip tracking with jitter smoothing (EMA)
        - Single blink → left click callback
        - Double blink → right click callback
        - Long blink → drag/hold callback
        - Multi-point calibration
        - Background thread for continuous frame processing
        - Face-lost / face-found callbacks
        - Performance stats (FPS, latency)

    Usage:
        tracker = EyeTracker()
        tracker.on_blink(lambda: mouse.click())
        tracker.on_double_blink(lambda: mouse.right_click())
        tracker.start()

        # In your main loop:
        pos = tracker.get_nose_position()
        if pos:
            mouse.move_to(*pos)
    """

    def __init__(self) -> None:
        # Lazy-loaded heavy libraries
        self._cv2 = None
        self._mp = None
        self._np = None

        # Camera and MediaPipe handles
        self._cap = None               # cv2.VideoCapture
        self._face_mesh = None          # mediapipe FaceMesh

        # State
        self._state: TrackingState = TrackingState.STOPPED
        self.is_running: bool = False
        self.is_calibrated: bool = False

        # Current tracking data
        self._nose_position: Optional[Tuple[int, int]] = None
        self._raw_nose: Optional[Tuple[float, float]] = None
        self._left_ear: float = 1.0
        self._right_ear: float = 1.0
        self._face_detected: bool = False
        self._last_frame: Optional[TrackingFrame] = None

        # Blink detection state
        self._blink_in_progress: bool = False
        self._blink_start_time: float = 0.0
        self._last_blink_time: float = 0.0
        self._blink_count: int = 0
        self._consecutive_closed_frames: int = 0
        self._consecutive_open_frames: int = 0

        # EAR history for smoothing blink detection
        self._ear_history: Deque[float] = deque(maxlen=5)

        # Callbacks
        self._on_blink: List[Callable[[], None]] = []
        self._on_double_blink: List[Callable[[], None]] = []
        self._on_long_blink: List[Callable[[], None]] = []
        self._on_face_lost: List[Callable[[], None]] = []
        self._on_face_found: List[Callable[[], None]] = []
        self._on_position_update: List[Callable[[int, int], None]] = []

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
        self._long_blink_ms: int = config.get(
            "blink_detection.long_blink_duration_ms", 800
        )
        self._jitter_threshold: int = config.get(
            "eye_tracking.jitter_threshold", 5
        )
        self._min_detection_confidence: float = config.get(
            "eye_tracking.min_detection_confidence", 0.5
        )
        self._min_tracking_confidence: float = config.get(
            "eye_tracking.min_tracking_confidence", 0.5
        )
        self._consecutive_frames_for_blink: int = config.get(
            "blink_detection.consecutive_frames", 2
        )

        # Calibration data
        self._calibration = CalibrationData()
        self._screen_width: int = 1920
        self._screen_height: int = 1080

        # Threading
        self._tracking_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Performance stats
        self._frame_count: int = 0
        self._start_time: float = 0.0
        self._frame_times: Deque[float] = deque(maxlen=30)

        logger.info(
            f"EyeTracker created | camera={self._camera_index} | "
            f"fps={self._fps} | smoothing={self._smoothing} | "
            f"ear_threshold={self._ear_threshold}"
        )

    # ------------------------------------------------------------------
    # Lazy imports
    # ------------------------------------------------------------------

    def _ensure_imports(self) -> None:
        """Lazy-import heavy libraries on first use."""
        if self._cv2 is None:
            try:
                import cv2
                self._cv2 = cv2
                logger.debug("OpenCV imported successfully")
            except ImportError as exc:
                raise EyeTrackingError(
                    f"OpenCV not installed: {exc}. Run: pip install opencv-python"
                )

        if self._mp is None:
            try:
                import mediapipe as mp
                self._mp = mp
                logger.debug("MediaPipe imported successfully")
            except ImportError as exc:
                raise EyeTrackingError(
                    f"MediaPipe not installed: {exc}. Run: pip install mediapipe"
                )

        if self._np is None:
            try:
                import numpy as np
                self._np = np
            except ImportError as exc:
                raise EyeTrackingError(
                    f"NumPy not installed: {exc}. Run: pip install numpy"
                )

    # ------------------------------------------------------------------
    # Camera lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Open the camera and initialise MediaPipe FaceMesh.

        Starts a background thread that continuously processes frames,
        extracts landmarks, computes nose position and blink state.

        Raises:
            CameraError: If the camera cannot be opened.
            EyeTrackingError: If dependencies are missing.
        """
        if self.is_running:
            logger.warning("EyeTracker is already running")
            return

        self._ensure_imports()
        self._state = TrackingState.STARTING

        try:
            logger.info(f"Opening camera index {self._camera_index}...")
            self._cap = self._cv2.VideoCapture(self._camera_index)

            if not self._cap.isOpened():
                self._state = TrackingState.ERROR
                raise CameraError(
                    f"Camera index {self._camera_index} failed to open. "
                    "Check that the webcam is connected."
                )

            # Set camera properties for performance
            self._cap.set(self._cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._cap.set(self._cv2.CAP_PROP_FPS, self._fps)

            # Initialise MediaPipe FaceMesh
            mp_face_mesh = self._mp.solutions.face_mesh
            self._face_mesh = mp_face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=self._min_detection_confidence,
                min_tracking_confidence=self._min_tracking_confidence,
            )

            # Detect screen resolution
            self._detect_screen_size()

            # Start background tracking thread
            self._stop_event.clear()
            self.is_running = True
            self._state = TrackingState.RUNNING
            self._start_time = time.time()
            self._frame_count = 0

            self._tracking_thread = threading.Thread(
                target=self._tracking_loop,
                name="EyeTracker-Loop",
                daemon=True,
            )
            self._tracking_thread.start()

            logger.info(
                f"EyeTracker started | camera={self._camera_index} | "
                f"resolution=640x480 | fps={self._fps}"
            )

        except CameraError:
            raise
        except EyeTrackingError:
            raise
        except Exception as exc:
            self._state = TrackingState.ERROR
            raise CameraError(f"Failed to start eye tracker: {exc}")

    def stop(self) -> None:
        """Release camera, close FaceMesh, and stop the tracking thread."""
        if not self.is_running and self._state == TrackingState.STOPPED:
            return

        logger.info("Stopping EyeTracker...")
        self._stop_event.set()

        # Wait for tracking thread to finish
        if self._tracking_thread is not None and self._tracking_thread.is_alive():
            self._tracking_thread.join(timeout=3.0)
            if self._tracking_thread.is_alive():
                logger.warning("Tracking thread did not stop within timeout")

        # Release camera
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as exc:
                logger.warning(f"Error releasing camera: {exc}")
        self._cap = None

        # Close FaceMesh
        if self._face_mesh is not None:
            try:
                self._face_mesh.close()
            except Exception as exc:
                logger.warning(f"Error closing FaceMesh: {exc}")
        self._face_mesh = None

        self.is_running = False
        self._state = TrackingState.STOPPED
        self._nose_position = None
        self._face_detected = False

        logger.info("EyeTracker stopped")

    def pause(self) -> None:
        """Pause tracking without releasing the camera."""
        if self._state == TrackingState.RUNNING:
            self._state = TrackingState.PAUSED
            logger.info("EyeTracker paused")

    def resume(self) -> None:
        """Resume tracking after a pause."""
        if self._state == TrackingState.PAUSED:
            self._state = TrackingState.RUNNING
            logger.info("EyeTracker resumed")

    # ------------------------------------------------------------------
    # Screen detection
    # ------------------------------------------------------------------

    def _detect_screen_size(self) -> None:
        """Detect primary monitor resolution."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            self._screen_width = user32.GetSystemMetrics(0)
            self._screen_height = user32.GetSystemMetrics(1)
            self._calibration.screen_width = self._screen_width
            self._calibration.screen_height = self._screen_height
            logger.info(
                f"Screen resolution detected: "
                f"{self._screen_width}x{self._screen_height}"
            )
        except Exception:
            logger.warning(
                "Could not detect screen size, using default 1920x1080"
            )
            self._screen_width = 1920
            self._screen_height = 1080

    # ------------------------------------------------------------------
    # Tracking loop (background thread)
    # ------------------------------------------------------------------

    def _tracking_loop(self) -> None:
        """
        Main tracking loop running in a background thread.

        Captures frames, processes through MediaPipe, extracts nose
        position and eye aspect ratios, fires callbacks.
        """
        frame_interval = 1.0 / self._fps
        logger.debug("Tracking loop started")

        while not self._stop_event.is_set():
            if self._state == TrackingState.PAUSED:
                time.sleep(0.05)
                continue

            loop_start = time.time()

            try:
                frame_data = self._process_frame()

                if frame_data is not None:
                    with self._lock:
                        self._last_frame = frame_data

                    if frame_data.face_detected:
                        self._handle_face_detected(frame_data)
                    else:
                        self._handle_face_lost()

            except Exception as exc:
                logger.error(f"Error in tracking loop: {exc}")

            # FPS throttling
            elapsed = time.time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

            self._frame_times.append(time.time() - loop_start)
            self._frame_count += 1

        logger.debug("Tracking loop ended")

    def _process_frame(self) -> Optional[TrackingFrame]:
        """
        Read a camera frame and extract tracking data.

        Returns:
            TrackingFrame with nose position and EAR, or None on failure.
        """
        if self._cap is None or not self._cap.isOpened():
            return None

        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None

        # Convert BGR to RGB for MediaPipe
        rgb_frame = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)

        # Disable writeable flag for performance (MediaPipe optimisation)
        rgb_frame.flags.writeable = False
        results = self._face_mesh.process(rgb_frame)
        rgb_frame.flags.writeable = True

        tracking = TrackingFrame(timestamp=time.time())

        if results.multi_face_landmarks:
            face_landmarks = results.multi_face_landmarks[0]
            landmarks = face_landmarks.landmark

            # Extract nose tip (normalised 0..1)
            nose = landmarks[NOSE_TIP_INDEX]
            tracking.nose_x = nose.x
            tracking.nose_y = nose.y

            # Compute EAR for both eyes
            tracking.left_ear = compute_ear(landmarks, LEFT_EYE_INDICES)
            tracking.right_ear = compute_ear(landmarks, RIGHT_EYE_INDICES)

            # Map nose to screen coordinates
            screen_x, screen_y = self._calibration.map_to_screen(
                nose.x, nose.y
            )

            # Apply smoothing
            smoothed = self._smooth_position(screen_x, screen_y)
            tracking.screen_x = smoothed[0]
            tracking.screen_y = smoothed[1]

            tracking.face_detected = True

        return tracking

    # ------------------------------------------------------------------
    # Face event handling
    # ------------------------------------------------------------------

    def _handle_face_detected(self, frame: TrackingFrame) -> None:
        """Handle a frame where a face was successfully detected."""
        was_detected = self._face_detected

        with self._lock:
            self._face_detected = True
            self._nose_position = (frame.screen_x, frame.screen_y)
            self._raw_nose = (frame.nose_x, frame.nose_y)
            self._left_ear = frame.left_ear
            self._right_ear = frame.right_ear

        # Fire face-found callback on transition
        if not was_detected:
            logger.info("Face detected")
            for cb in self._on_face_found:
                try:
                    cb()
                except Exception as exc:
                    logger.error(f"Error in face-found callback: {exc}")

        # Fire position update callbacks
        for cb in self._on_position_update:
            try:
                cb(frame.screen_x, frame.screen_y)
            except Exception as exc:
                logger.error(f"Error in position callback: {exc}")

        # Process blink detection
        self._process_blink(frame)

    def _handle_face_lost(self) -> None:
        """Handle a frame where no face was detected."""
        was_detected = self._face_detected

        with self._lock:
            self._face_detected = False

        if was_detected:
            logger.warning("Face lost")
            for cb in self._on_face_lost:
                try:
                    cb()
                except Exception as exc:
                    logger.error(f"Error in face-lost callback: {exc}")

    # ------------------------------------------------------------------
    # Blink detection
    # ------------------------------------------------------------------

    def _process_blink(self, frame: TrackingFrame) -> None:
        """
        Detect blink events from eye aspect ratios.

        Uses consecutive-frame counting to avoid false positives from
        noise. Distinguishes single, double, and long blinks.

        Args:
            frame: Current tracking frame with EAR values.
        """
        avg_ear = (frame.left_ear + frame.right_ear) / 2.0
        self._ear_history.append(avg_ear)

        eyes_closed = avg_ear < self._ear_threshold

        if eyes_closed:
            self._consecutive_closed_frames += 1
            self._consecutive_open_frames = 0

            # Start tracking blink duration
            if not self._blink_in_progress:
                self._blink_in_progress = True
                self._blink_start_time = time.time()

        else:
            if self._blink_in_progress:
                # Blink just ended
                self._blink_in_progress = False
                blink_duration_ms = (
                    time.time() - self._blink_start_time
                ) * 1000

                if self._consecutive_closed_frames >= self._consecutive_frames_for_blink:
                    if blink_duration_ms >= self._long_blink_ms:
                        # Long blink
                        self._fire_long_blink()
                    else:
                        # Regular blink - check for double
                        now = time.time()
                        time_since_last = (
                            now - self._last_blink_time
                        ) * 1000

                        if time_since_last <= self._double_blink_ms:
                            self._blink_count += 1
                            if self._blink_count >= 2:
                                self._fire_double_blink()
                                self._blink_count = 0
                        else:
                            # Schedule single blink (wait to see if double)
                            self._blink_count = 1
                            self._last_blink_time = now

                            # Fire single blink after timeout if no second
                            # blink arrives. We use a simple timer thread.
                            threading.Timer(
                                self._double_blink_ms / 1000.0,
                                self._check_single_blink,
                                args=(now,),
                            ).start()

                self._consecutive_closed_frames = 0

            self._consecutive_open_frames += 1

    def _check_single_blink(self, blink_time: float) -> None:
        """
        Check if a blink remained single (no double blink followed).

        Called after the double-blink timeout window. Only fires the
        single-blink callback if no second blink occurred.

        Args:
            blink_time: Timestamp of the original blink.
        """
        if self._last_blink_time == blink_time and self._blink_count == 1:
            self._blink_count = 0
            self._fire_single_blink()

    def _fire_single_blink(self) -> None:
        """Fire single-blink callbacks."""
        logger.debug("Single blink detected")
        for cb in self._on_blink:
            try:
                cb()
            except Exception as exc:
                logger.error(f"Error in blink callback: {exc}")

    def _fire_double_blink(self) -> None:
        """Fire double-blink callbacks."""
        logger.debug("Double blink detected")
        for cb in self._on_double_blink:
            try:
                cb()
            except Exception as exc:
                logger.error(f"Error in double-blink callback: {exc}")

    def _fire_long_blink(self) -> None:
        """Fire long-blink callbacks."""
        logger.debug("Long blink detected")
        for cb in self._on_long_blink:
            try:
                cb()
            except Exception as exc:
                logger.error(f"Error in long-blink callback: {exc}")

    # ------------------------------------------------------------------
    # Public: position & blink queries
    # ------------------------------------------------------------------

    def get_nose_position(self) -> Optional[Tuple[int, int]]:
        """
        Return the current nose-tip position mapped to screen coordinates.

        Thread-safe. Returns the latest smoothed position.

        Returns:
            ``(x, y)`` tuple or ``None`` if tracking is inactive or
            face is not detected.
        """
        with self._lock:
            return self._nose_position

    def get_raw_nose(self) -> Optional[Tuple[float, float]]:
        """
        Return the raw normalised nose position (0..1).

        Useful for calibration and debugging.

        Returns:
            ``(x, y)`` tuple in normalised coordinates, or None.
        """
        with self._lock:
            return self._raw_nose

    def get_ear(self) -> Tuple[float, float]:
        """
        Return the current eye aspect ratios.

        Returns:
            ``(left_ear, right_ear)`` tuple.
        """
        with self._lock:
            return (self._left_ear, self._right_ear)

    def is_face_detected(self) -> bool:
        """Check whether a face is currently being tracked."""
        with self._lock:
            return self._face_detected

    def detect_blink(self) -> bool:
        """
        Check whether the user's eyes are currently closed (blink in progress).

        Returns:
            ``True`` if eyes are closed below threshold.
        """
        with self._lock:
            avg_ear = (self._left_ear + self._right_ear) / 2.0
            return avg_ear < self._ear_threshold

    def detect_double_blink(self) -> bool:
        """
        Check whether a double-blink recently occurred.

        Note: For real-time usage, prefer registering callbacks with
        ``on_double_blink()`` instead of polling this method.

        Returns:
            ``True`` if blink_count indicates a recent double blink.
        """
        return self._blink_count >= 2

    # ------------------------------------------------------------------
    # Smoothing
    # ------------------------------------------------------------------

    def _smooth_position(
        self, new_x: int, new_y: int
    ) -> Tuple[int, int]:
        """
        Apply exponential moving average to reduce jitter.

        Also applies a jitter threshold — if the movement is smaller
        than the threshold, the position is not updated (dead zone).

        Args:
            new_x: Raw detected screen X.
            new_y: Raw detected screen Y.

        Returns:
            Smoothed ``(x, y)`` screen coordinates.
        """
        if self._nose_position is None:
            return (new_x, new_y)

        old_x, old_y = self._nose_position

        # Dead zone — ignore tiny movements
        dx = abs(new_x - old_x)
        dy = abs(new_y - old_y)
        if dx < self._jitter_threshold and dy < self._jitter_threshold:
            return (old_x, old_y)

        # Exponential moving average
        alpha = self._smoothing
        sx = int(alpha * old_x + (1 - alpha) * new_x)
        sy = int(alpha * old_y + (1 - alpha) * new_y)
        return (sx, sy)

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def calibrate(
        self,
        screen_width: int = 1920,
        screen_height: int = 1080,
        num_points: int = 0,
    ) -> None:
        """
        Start the calibration process.

        Sets up calibration points and marks the tracker as calibrating.
        The actual point capture is done via ``capture_calibration_point()``.

        For quick calibration (no GUI), use ``quick_calibrate()`` instead.

        Args:
            screen_width:  Monitor width in pixels.
            screen_height: Monitor height in pixels.
            num_points: Number of calibration points (default from config).
        """
        if num_points <= 0:
            num_points = config.get("eye_tracking.calibration_points", 9)

        self._screen_width = screen_width
        self._screen_height = screen_height

        self._calibration = CalibrationData(
            screen_width=screen_width,
            screen_height=screen_height,
        )

        # Generate calibration point grid
        self._calibration.points = self._generate_calibration_grid(
            screen_width, screen_height, num_points
        )

        self._state = TrackingState.CALIBRATING
        self.is_calibrated = False

        logger.info(
            f"Calibration started | {screen_width}x{screen_height} | "
            f"{num_points} points"
        )

    def _generate_calibration_grid(
        self,
        width: int,
        height: int,
        num_points: int,
    ) -> List[CalibrationPoint]:
        """
        Generate a grid of calibration points on the screen.

        Args:
            width: Screen width.
            height: Screen height.
            num_points: Total number of points (will be arranged in
                        a grid as close to square as possible).

        Returns:
            List of CalibrationPoint objects.
        """
        import math

        # Find closest grid dimensions
        cols = int(math.ceil(math.sqrt(num_points)))
        rows = int(math.ceil(num_points / cols))

        points = []
        margin_x = int(width * 0.1)
        margin_y = int(height * 0.1)

        usable_w = width - 2 * margin_x
        usable_h = height - 2 * margin_y

        for r in range(rows):
            for c in range(cols):
                if len(points) >= num_points:
                    break

                if cols > 1:
                    x = margin_x + int(c * usable_w / (cols - 1))
                else:
                    x = width // 2

                if rows > 1:
                    y = margin_y + int(r * usable_h / (rows - 1))
                else:
                    y = height // 2

                points.append(CalibrationPoint(screen_x=x, screen_y=y))

        return points

    def capture_calibration_point(self, index: int) -> bool:
        """
        Capture the current nose position for a calibration point.

        The user should be looking at the calibration point on screen.

        Args:
            index: Index of the calibration point to capture.

        Returns:
            True if the point was captured successfully.
        """
        if index < 0 or index >= len(self._calibration.points):
            logger.error(f"Invalid calibration point index: {index}")
            return False

        raw = self.get_raw_nose()
        if raw is None:
            logger.warning("No face detected - cannot capture calibration point")
            return False

        point = self._calibration.points[index]
        point.nose_x = raw[0]
        point.nose_y = raw[1]
        point.captured = True

        logger.info(
            f"Calibration point {index} captured: "
            f"screen=({point.screen_x}, {point.screen_y}) "
            f"nose=({raw[0]:.4f}, {raw[1]:.4f})"
        )

        # Check if all points are captured
        all_captured = all(p.captured for p in self._calibration.points)
        if all_captured:
            self._finalize_calibration()

        return True

    def _finalize_calibration(self) -> None:
        """
        Compute the nose-to-screen mapping from captured calibration points.

        Calculates the min/max nose range from all captured points.
        """
        points = self._calibration.points
        nose_xs = [p.nose_x for p in points if p.captured]
        nose_ys = [p.nose_y for p in points if p.captured]

        if not nose_xs or not nose_ys:
            logger.error("No calibration points captured")
            return

        # Add a small margin (10%) around the detected range
        x_range = max(nose_xs) - min(nose_xs)
        y_range = max(nose_ys) - min(nose_ys)
        margin_x = x_range * 0.1
        margin_y = y_range * 0.1

        self._calibration.nose_min_x = min(nose_xs) - margin_x
        self._calibration.nose_max_x = max(nose_xs) + margin_x
        self._calibration.nose_min_y = min(nose_ys) - margin_y
        self._calibration.nose_max_y = max(nose_ys) + margin_y
        self._calibration.is_valid = True

        self.is_calibrated = True
        self._state = TrackingState.RUNNING

        logger.info(
            f"Calibration complete | nose range: "
            f"x=[{self._calibration.nose_min_x:.4f}, "
            f"{self._calibration.nose_max_x:.4f}] "
            f"y=[{self._calibration.nose_min_y:.4f}, "
            f"{self._calibration.nose_max_y:.4f}]"
        )

    def quick_calibrate(
        self,
        screen_width: int = 0,
        screen_height: int = 0,
        duration: float = 3.0,
    ) -> bool:
        """
        Perform a quick auto-calibration by sampling nose position.

        The user should move their head to cover their comfortable
        range of motion during the calibration period.

        Args:
            screen_width: Screen width (auto-detected if 0).
            screen_height: Screen height (auto-detected if 0).
            duration: Seconds to sample nose movement.

        Returns:
            True if calibration succeeded.
        """
        if screen_width <= 0:
            screen_width = self._screen_width
        if screen_height <= 0:
            screen_height = self._screen_height

        if not self.is_running or not self._face_detected:
            logger.warning(
                "Quick calibrate requires tracker to be running with face detected"
            )
            return False

        self._state = TrackingState.CALIBRATING
        logger.info(
            f"Quick calibration started — move your head around for "
            f"{duration} seconds"
        )

        min_x, max_x = 1.0, 0.0
        min_y, max_y = 1.0, 0.0
        samples = 0
        start = time.time()

        while time.time() - start < duration:
            raw = self.get_raw_nose()
            if raw is not None:
                min_x = min(min_x, raw[0])
                max_x = max(max_x, raw[0])
                min_y = min(min_y, raw[1])
                max_y = max(max_y, raw[1])
                samples += 1
            time.sleep(0.033)  # ~30 fps sampling

        if samples < 10:
            logger.error(f"Quick calibration failed: only {samples} samples")
            self._state = TrackingState.RUNNING
            return False

        # Add margin
        x_range = max_x - min_x
        y_range = max_y - min_y
        margin_x = x_range * 0.15
        margin_y = y_range * 0.15

        self._calibration = CalibrationData(
            nose_min_x=min_x - margin_x,
            nose_max_x=max_x + margin_x,
            nose_min_y=min_y - margin_y,
            nose_max_y=max_y + margin_y,
            screen_width=screen_width,
            screen_height=screen_height,
            is_valid=True,
        )

        self.is_calibrated = True
        self._state = TrackingState.RUNNING

        logger.info(
            f"Quick calibration complete | {samples} samples | "
            f"nose range: x=[{self._calibration.nose_min_x:.4f}, "
            f"{self._calibration.nose_max_x:.4f}] "
            f"y=[{self._calibration.nose_min_y:.4f}, "
            f"{self._calibration.nose_max_y:.4f}]"
        )
        return True

    def get_calibration_points(self) -> List[CalibrationPoint]:
        """Return the current calibration points (for UI rendering)."""
        return self._calibration.points

    def get_next_uncaptured_point(self) -> Optional[int]:
        """
        Return the index of the next uncaptured calibration point.

        Returns:
            Index of the next uncaptured point, or None if all done.
        """
        for i, point in enumerate(self._calibration.points):
            if not point.captured:
                return i
        return None

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_blink(self, callback: Callable[[], None]) -> None:
        """Register callback for single-blink events (left click)."""
        self._on_blink.append(callback)

    def on_double_blink(self, callback: Callable[[], None]) -> None:
        """Register callback for double-blink events (right click)."""
        self._on_double_blink.append(callback)

    def on_long_blink(self, callback: Callable[[], None]) -> None:
        """Register callback for long-blink events (drag/hold)."""
        self._on_long_blink.append(callback)

    def on_face_lost(self, callback: Callable[[], None]) -> None:
        """Register callback for face-lost events."""
        self._on_face_lost.append(callback)

    def on_face_found(self, callback: Callable[[], None]) -> None:
        """Register callback for face-found events."""
        self._on_face_found.append(callback)

    def on_position_update(self, callback: Callable[[int, int], None]) -> None:
        """Register callback for position update events."""
        self._on_position_update.append(callback)

    def remove_all_callbacks(self) -> None:
        """Remove all registered callbacks."""
        self._on_blink.clear()
        self._on_double_blink.clear()
        self._on_long_blink.clear()
        self._on_face_lost.clear()
        self._on_face_found.clear()
        self._on_position_update.clear()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_smoothing(self, factor: float) -> None:
        """
        Set the smoothing factor for cursor movement.

        Args:
            factor: Value between 0.0 (no smoothing) and 0.99 (maximum).
        """
        self._smoothing = max(0.0, min(0.99, factor))
        logger.info(f"Smoothing factor set to {self._smoothing}")

    def set_ear_threshold(self, threshold: float) -> None:
        """
        Set the eye aspect ratio threshold for blink detection.

        Args:
            threshold: Value between 0.1 and 0.5. Lower = less sensitive.
        """
        self._ear_threshold = max(0.1, min(0.5, threshold))
        logger.info(f"EAR threshold set to {self._ear_threshold}")

    def set_camera(self, camera_index: int) -> None:
        """
        Switch to a different camera.

        The tracker must be stopped and restarted for this to take effect.

        Args:
            camera_index: Camera device index.
        """
        self._camera_index = camera_index
        logger.info(f"Camera index set to {camera_index}")

    # ------------------------------------------------------------------
    # Status & Performance
    # ------------------------------------------------------------------

    def get_status(self) -> Dict:
        """Return a status dict for the UI panel."""
        with self._lock:
            return {
                "running": self.is_running,
                "state": self._state.name,
                "calibrated": self.is_calibrated,
                "face_detected": self._face_detected,
                "nose_position": self._nose_position,
                "left_ear": round(self._left_ear, 4),
                "right_ear": round(self._right_ear, 4),
                "camera_index": self._camera_index,
                "fps_target": self._fps,
                "fps_actual": self.get_fps(),
                "smoothing": self._smoothing,
                "ear_threshold": self._ear_threshold,
                "frame_count": self._frame_count,
            }

    def get_fps(self) -> float:
        """
        Return the actual frames-per-second being processed.

        Returns:
            Current FPS as a float, or 0.0 if not enough data.
        """
        if len(self._frame_times) < 2:
            return 0.0

        avg_frame_time = sum(self._frame_times) / len(self._frame_times)
        if avg_frame_time <= 0:
            return 0.0

        return round(1.0 / avg_frame_time, 1)

    def get_performance_stats(self) -> Dict:
        """
        Return detailed performance statistics.

        Returns:
            Dict with fps, latency, frame_count, uptime.
        """
        uptime = time.time() - self._start_time if self._start_time > 0 else 0

        avg_latency = 0.0
        if self._frame_times:
            avg_latency = (
                sum(self._frame_times) / len(self._frame_times) * 1000
            )

        return {
            "fps": self.get_fps(),
            "avg_latency_ms": round(avg_latency, 2),
            "total_frames": self._frame_count,
            "uptime_seconds": round(uptime, 1),
            "face_detected": self._face_detected,
        }

    # ------------------------------------------------------------------
    # Camera utilities
    # ------------------------------------------------------------------

    @staticmethod
    def list_cameras(max_index: int = 5) -> List[Dict]:
        """
        Enumerate available camera devices.

        Tries opening cameras at indices 0..max_index and returns
        info for those that open successfully.

        Args:
            max_index: Maximum camera index to probe.

        Returns:
            List of dicts with ``index``, ``width``, ``height`` for
            each available camera.
        """
        try:
            import cv2
        except ImportError:
            logger.error("OpenCV not installed - cannot enumerate cameras")
            return []

        cameras = []
        for idx in range(max_index):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cameras.append({
                    "index": idx,
                    "width": width,
                    "height": height,
                    "name": f"Camera {idx}",
                })
                cap.release()
        return cameras


__all__ = [
    "EyeTracker",
    "BlinkType",
    "TrackingState",
    "TrackingFrame",
    "CalibrationData",
    "CalibrationPoint",
    "compute_ear",
]
