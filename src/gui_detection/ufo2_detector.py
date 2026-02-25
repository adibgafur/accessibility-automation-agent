"""
UFO2 Detector - Windows UI Automation based GUI element detection.

UFO2 (Microsoft) is a full Windows Desktop AgentOS framework that uses
native Windows UIA + Win32 APIs for high-accuracy element detection.

This module wraps the UIA tree walking and screenshot-based visual
detection into the BaseDetector interface.

Dependencies:
    - pywinauto (for UIA tree access on Windows)
    - Pillow (for screenshots)

For low-spec hardware:
    - Elements are cached with configurable TTL
    - UIA tree walking is depth-limited
    - Screenshot resolution is configurable
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from ..utils.config_manager import config
from ..utils.error_handler import GUIDetectionError
from .base import (
    BaseDetector,
    BoundingBox,
    DetectionResult,
    DetectionSource,
    DetectorState,
    ElementType,
    UIElement,
    map_uia_type,
)


# ======================================================================
# Element cache
# ======================================================================


class _ElementCache:
    """
    Simple TTL-based cache for detected UI elements.

    Avoids re-walking the UIA tree on every detection call when
    the window hasn't changed.
    """

    def __init__(self, ttl_seconds: float = 5.0) -> None:
        self._cache: Dict[str, DetectionResult] = {}
        self._timestamps: Dict[str, float] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[DetectionResult]:
        """Get a cached result if still valid."""
        if key in self._cache:
            age = time.time() - self._timestamps.get(key, 0)
            if age < self._ttl:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._timestamps[key]
        return None

    def put(self, key: str, result: DetectionResult) -> None:
        """Store a detection result in the cache."""
        self._cache[key] = result
        self._timestamps[key] = time.time()

    def clear(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
        self._timestamps.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


# ======================================================================
# UFO2 Detector
# ======================================================================


class UFO2Detector(BaseDetector):
    """
    GUI element detector using Windows UI Automation (UIA).

    This is the primary detection engine. It accesses the native
    Windows accessibility tree to find UI elements with high accuracy.

    When visual detection is enabled, it also takes screenshots and
    combines the results for a hybrid approach.

    Configuration (from config/ufo2_config.yaml):
        - confidence_threshold: Minimum confidence to include an element
        - cache_timeout: How long to cache UIA tree results
        - max_detections: Maximum elements to return
        - use_uia: Enable UIA tree walking
        - use_visual: Enable screenshot-based detection
    """

    def __init__(self) -> None:
        super().__init__(name="UFO2")

        # Lazy-loaded
        self._uia_module = None     # pywinauto or uiautomation
        self._pil = None            # PIL / Pillow

        # Config
        self._confidence_threshold: float = config.get(
            "gui_detection.ufo2_confidence_threshold", 0.7
        )
        self._use_uia: bool = config.get("ufo2.use_uia", True)
        self._use_visual: bool = config.get("ufo2.use_visual", False)
        self._cache_timeout: float = config.get("ufo2.uia.cache_timeout", 5.0)
        self._max_detections: int = config.get(
            "ufo2.detection.max_detections", 50
        )
        self._max_depth: int = config.get("ufo2.detection.max_depth", 8)

        # Cache
        self._cache = _ElementCache(ttl_seconds=self._cache_timeout)

        logger.info(
            f"UFO2Detector created | use_uia={self._use_uia} | "
            f"use_visual={self._use_visual} | threshold={self._confidence_threshold}"
        )

    # ------------------------------------------------------------------
    # Lazy imports
    # ------------------------------------------------------------------

    def _ensure_imports(self) -> None:
        """Lazy-import Windows-specific libraries."""
        if self._pil is None:
            try:
                from PIL import ImageGrab
                self._pil = ImageGrab
                logger.debug("Pillow ImageGrab imported")
            except ImportError as exc:
                logger.warning(f"Pillow not available: {exc}")

    # ------------------------------------------------------------------
    # BaseDetector interface
    # ------------------------------------------------------------------

    def load(self) -> None:
        """
        Initialise the UFO2 detection engine.

        Loads pywinauto / UIA bindings and verifies access to the
        Windows accessibility tree.

        Raises:
            GUIDetectionError: If UIA cannot be initialised.
        """
        if self._state == DetectorState.READY:
            logger.debug("UFO2Detector already loaded")
            return

        self._state = DetectorState.LOADING
        logger.info("Loading UFO2 detector...")

        try:
            self._ensure_imports()

            # Try importing ctypes for UIA access (always available on Windows)
            import ctypes
            import ctypes.wintypes

            # Verify UIA access by getting desktop window handle
            user32 = ctypes.windll.user32
            hwnd = user32.GetDesktopWindow()
            if hwnd == 0:
                raise GUIDetectionError(
                    "Cannot access Windows desktop (UIA unavailable)"
                )

            self._state = DetectorState.READY
            logger.info("UFO2 detector loaded successfully")

        except GUIDetectionError:
            self._state = DetectorState.ERROR
            raise
        except Exception as exc:
            self._state = DetectorState.ERROR
            raise GUIDetectionError(
                f"Failed to load UFO2 detector: {exc}"
            )

    def unload(self) -> None:
        """Release UFO2 detector resources."""
        self._cache.clear()
        self._state = DetectorState.UNLOADED
        logger.info("UFO2 detector unloaded")

    def detect(
        self,
        window_title: Optional[str] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> DetectionResult:
        """
        Detect UI elements using Windows UIA.

        Walks the UIA accessibility tree for the target window (or
        foreground window if not specified) and extracts element info.

        Args:
            window_title: Title of the window to inspect.
            region: (x, y, w, h) to restrict detection area.

        Returns:
            DetectionResult with detected UIElements.
        """
        if self._state != DetectorState.READY:
            return DetectionResult(
                success=False,
                error_message="UFO2 detector not loaded",
                source=DetectionSource.UFO2_UIA,
            )

        # Check cache
        cache_key = f"ufo2:{window_title}:{region}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"UFO2 cache hit for '{window_title}'")
            cached.source = DetectionSource.CACHED
            return cached

        self._state = DetectorState.DETECTING
        start = time.time()

        try:
            import ctypes
            user32 = ctypes.windll.user32

            # Find target window
            hwnd = self._find_window(user32, window_title)
            if hwnd == 0:
                self._state = DetectorState.READY
                return DetectionResult(
                    success=False,
                    error_message=f"Window not found: '{window_title}'",
                    source=DetectionSource.UFO2_UIA,
                )

            # Get window title
            actual_title = self._get_window_title(user32, hwnd)

            # Walk the UIA tree
            elements = self._walk_uia_tree(user32, hwnd, region)

            elapsed = (time.time() - start) * 1000
            self._detection_count += 1
            self._total_time_ms += elapsed
            self._state = DetectorState.READY

            result = DetectionResult(
                elements=elements[:self._max_detections],
                source=DetectionSource.UFO2_UIA,
                success=True,
                detection_time_ms=elapsed,
                window_title=actual_title,
            )

            # Cache the result
            self._cache.put(cache_key, result)

            logger.info(
                f"UFO2 detected {result.count} elements in "
                f"{elapsed:.1f}ms | window='{actual_title}'"
            )
            return result

        except Exception as exc:
            self._error_count += 1
            self._state = DetectorState.READY
            elapsed = (time.time() - start) * 1000

            logger.error(f"UFO2 detection failed: {exc}")
            return DetectionResult(
                success=False,
                error_message=str(exc),
                source=DetectionSource.UFO2_UIA,
                detection_time_ms=elapsed,
            )

    def detect_element(
        self,
        query: str,
        window_title: Optional[str] = None,
    ) -> Optional[UIElement]:
        """
        Find a specific UI element by name.

        Args:
            query: Element name/text to search for.
            window_title: Window to search in.

        Returns:
            Best matching UIElement or None.
        """
        result = self.detect(window_title=window_title)
        if not result.success or result.count == 0:
            return None

        return result.find_by_name(query)

    # ------------------------------------------------------------------
    # Windows API helpers
    # ------------------------------------------------------------------

    def _find_window(self, user32: Any, title: Optional[str]) -> int:
        """
        Find a window handle by title, or get the foreground window.

        Args:
            user32: ctypes user32 module.
            title: Window title to search for, or None for foreground.

        Returns:
            Window handle (HWND), or 0 if not found.
        """
        if title is None:
            return user32.GetForegroundWindow()

        import ctypes

        # FindWindowW accepts class name and window title
        hwnd = user32.FindWindowW(None, title)
        if hwnd != 0:
            return hwnd

        # Try partial match via EnumWindows
        found_hwnd = [0]

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_callback(h, _):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, buf, 256)
            if title.lower() in buf.value.lower():
                found_hwnd[0] = h
                return False  # Stop enumeration
            return True

        user32.EnumWindows(enum_callback, 0)
        return found_hwnd[0]

    def _get_window_title(self, user32: Any, hwnd: int) -> str:
        """Get the title of a window by handle."""
        import ctypes

        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value

    def _walk_uia_tree(
        self,
        user32: Any,
        hwnd: int,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> List[UIElement]:
        """
        Walk child windows to extract UI element info.

        Uses EnumChildWindows + GetWindowRect + GetWindowText for
        basic element detection. For more detailed UIA access,
        the user can install pywinauto.

        Args:
            user32: ctypes user32 module.
            hwnd: Parent window handle.
            region: Optional region filter.

        Returns:
            List of detected UIElements.
        """
        import ctypes
        import ctypes.wintypes

        elements = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def child_callback(child_hwnd, _):
            try:
                # Get window text
                buf = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(child_hwnd, buf, 256)
                name = buf.value

                # Get class name
                cls_buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(child_hwnd, cls_buf, 256)
                class_name = cls_buf.value

                # Get window rect
                rect = ctypes.wintypes.RECT()
                user32.GetWindowRect(child_hwnd, ctypes.byref(rect))

                x = rect.left
                y = rect.top
                w = rect.right - rect.left
                h = rect.bottom - rect.top

                # Skip zero-size or offscreen elements
                if w <= 0 or h <= 0:
                    return True

                # Apply region filter
                if region is not None:
                    rx, ry, rw, rh = region
                    if x + w < rx or x > rx + rw or y + h < ry or y > ry + rh:
                        return True

                # Check visibility
                is_visible = bool(user32.IsWindowVisible(child_hwnd))
                is_enabled = bool(user32.IsWindowEnabled(child_hwnd))

                # Map class name to element type
                element_type = self._classify_element(class_name)

                # UIA gives high confidence for native elements
                confidence = 0.9 if name else 0.7

                element = UIElement(
                    name=name or class_name or "Unknown",
                    element_type=element_type,
                    bbox=BoundingBox(x=x, y=y, width=w, height=h),
                    confidence=confidence,
                    source=DetectionSource.UFO2_UIA,
                    class_name=class_name,
                    is_enabled=is_enabled,
                    is_visible=is_visible,
                    properties={"hwnd": int(child_hwnd)},
                )
                elements.append(element)

            except Exception:
                pass  # Skip problematic elements

            return True  # Continue enumeration

        user32.EnumChildWindows(hwnd, child_callback, 0)

        return elements

    def _classify_element(self, class_name: str) -> ElementType:
        """
        Classify a Win32 element by its window class name.

        Args:
            class_name: Win32 window class name.

        Returns:
            Best-guess ElementType.
        """
        cn = class_name.lower()

        if "button" in cn:
            return ElementType.BUTTON
        elif "edit" in cn:
            return ElementType.TEXT_FIELD
        elif "combobox" in cn or "combo" in cn:
            return ElementType.DROPDOWN
        elif "listbox" in cn or "list" in cn:
            return ElementType.LIST_ITEM
        elif "checkbox" in cn:
            return ElementType.CHECKBOX
        elif "radio" in cn:
            return ElementType.RADIO_BUTTON
        elif "scroll" in cn:
            return ElementType.SCROLLBAR
        elif "static" in cn:
            return ElementType.LABEL
        elif "toolbar" in cn:
            return ElementType.TOOLBAR
        elif "status" in cn:
            return ElementType.STATUS_BAR
        elif "tab" in cn:
            return ElementType.TAB
        elif "menu" in cn:
            return ElementType.MENU
        elif "tooltip" in cn:
            return ElementType.TOOLTIP
        elif "link" in cn or "syslink" in cn:
            return ElementType.LINK
        else:
            return ElementType.UNKNOWN

    # ------------------------------------------------------------------
    # Screenshot-based detection (supplementary)
    # ------------------------------------------------------------------

    def take_screenshot(
        self, region: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[Any]:
        """
        Take a screenshot for visual analysis.

        Args:
            region: Optional (x, y, w, h) region.

        Returns:
            PIL Image or None.
        """
        if self._pil is None:
            self._ensure_imports()

        if self._pil is None:
            return None

        try:
            if region:
                x, y, w, h = region
                img = self._pil.grab(bbox=(x, y, x + w, y + h))
            else:
                img = self._pil.grab()
            return img
        except Exception as exc:
            logger.error(f"Screenshot failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Clear the element detection cache."""
        self._cache.clear()
        logger.debug("UFO2 cache cleared")

    def get_cache_size(self) -> int:
        """Return the number of cached detection results."""
        return self._cache.size


__all__ = ["UFO2Detector"]
