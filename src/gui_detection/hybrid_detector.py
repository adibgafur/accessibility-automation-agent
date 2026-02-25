"""
Hybrid GUI Detector - Orchestrates UFO2 (primary) and GUIrilla (fallback).

The hybrid detector tries UFO2 first (fast, native UIA access). If UFO2
fails or returns low-confidence results (common after software updates
change UI elements), it automatically falls back to GUIrilla's visual
detection.

This design ensures reliable element detection even when:
    - The target app is updated and UIA tree changes
    - Non-standard UI frameworks are used (Electron, custom widgets)
    - UIA elements are not properly exposed

Fallback logic:
    1. Try UFO2 (UIA)
    2. If failed or confidence < threshold → try GUIrilla (visual)
    3. If both fail → return combined error
    4. Results are cached to avoid redundant detection
"""

import time
from typing import Dict, List, Optional, Tuple

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
)
from .ufo2_detector import UFO2Detector
from .guirilla_detector import GUIrillaDetector


class HybridDetector:
    """
    Orchestrator that combines UFO2 and GUIrilla detection engines.

    Strategy:
        1. UFO2 is the primary engine (fast, accurate for native UIA)
        2. GUIrilla is the fallback (visual, handles UI changes)
        3. Auto-switch on failure or low confidence
        4. Merge results from both engines when beneficial

    Usage:
        detector = HybridDetector()
        detector.load()

        # Auto-detect with fallback
        result = detector.detect(window_title="Notepad")

        # Find a specific element
        btn = detector.find_element("Save", window_title="Notepad")
        if btn:
            print(f"Click at {btn.click_point}")

    Configuration:
        - gui_detection.primary_engine: "ufo2" or "guirilla"
        - gui_detection.fallback_engine: "guirilla" or "ufo2"
        - gui_detection.auto_switch_on_failure: bool
        - gui_detection.ufo2_confidence_threshold: float
        - gui_detection.guirilla_confidence_threshold: float
    """

    def __init__(self) -> None:
        # Engines
        self._ufo2 = UFO2Detector()
        self._guirilla = GUIrillaDetector()

        # Config
        self._primary_engine: str = config.get(
            "gui_detection.primary_engine", "ufo2"
        )
        self._fallback_engine: str = config.get(
            "gui_detection.fallback_engine", "guirilla"
        )
        self._auto_switch: bool = config.get(
            "gui_detection.auto_switch_on_failure", True
        )
        self._ufo2_threshold: float = config.get(
            "gui_detection.ufo2_confidence_threshold", 0.7
        )
        self._guirilla_threshold: float = config.get(
            "gui_detection.guirilla_confidence_threshold", 0.5
        )
        self._merge_results: bool = config.get(
            "gui_detection.merge_results", False
        )

        # Statistics
        self._ufo2_successes: int = 0
        self._guirilla_successes: int = 0
        self._fallback_count: int = 0
        self._total_detections: int = 0

        logger.info(
            f"HybridDetector created | primary={self._primary_engine} | "
            f"fallback={self._fallback_engine} | auto_switch={self._auto_switch}"
        )

    # ------------------------------------------------------------------
    # Engine management
    # ------------------------------------------------------------------

    @property
    def primary(self) -> BaseDetector:
        """Return the primary detection engine."""
        if self._primary_engine == "guirilla":
            return self._guirilla
        return self._ufo2

    @property
    def fallback(self) -> BaseDetector:
        """Return the fallback detection engine."""
        if self._fallback_engine == "ufo2":
            return self._ufo2
        return self._guirilla

    def load(self, load_fallback: bool = False) -> None:
        """
        Load the detection engines.

        By default only loads the primary engine. The fallback is loaded
        lazily on first use (saves memory on low-spec hardware).

        Args:
            load_fallback: Also load the fallback engine immediately.

        Raises:
            GUIDetectionError: If the primary engine fails to load.
        """
        logger.info("Loading hybrid detector...")

        try:
            self.primary.load()
            logger.info(f"Primary engine ({self.primary.name}) loaded")
        except Exception as exc:
            logger.error(f"Primary engine failed to load: {exc}")
            # Try loading fallback as primary
            if self._auto_switch:
                logger.info("Attempting to load fallback as primary...")
                try:
                    self.fallback.load()
                    logger.info(
                        f"Fallback engine ({self.fallback.name}) loaded as primary"
                    )
                    return
                except Exception as exc2:
                    raise GUIDetectionError(
                        f"Both engines failed to load: primary={exc}, fallback={exc2}"
                    )
            raise

        if load_fallback:
            try:
                self.fallback.load()
                logger.info(f"Fallback engine ({self.fallback.name}) loaded")
            except Exception as exc:
                logger.warning(
                    f"Fallback engine failed to load (will retry later): {exc}"
                )

    def unload(self) -> None:
        """Unload both detection engines."""
        self._ufo2.unload()
        self._guirilla.unload()
        logger.info("Hybrid detector unloaded")

    def _ensure_fallback_loaded(self) -> bool:
        """
        Ensure the fallback engine is loaded (lazy loading).

        Returns:
            True if fallback is ready.
        """
        if self.fallback.is_ready:
            return True

        try:
            logger.info(f"Lazy-loading fallback engine ({self.fallback.name})...")
            self.fallback.load()
            return True
        except Exception as exc:
            logger.error(f"Failed to load fallback engine: {exc}")
            return False

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(
        self,
        window_title: Optional[str] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> DetectionResult:
        """
        Detect UI elements using the hybrid strategy.

        1. Try primary engine
        2. If failed/low confidence → try fallback
        3. Optionally merge results from both

        Args:
            window_title: Title of the target window.
            region: (x, y, w, h) region to restrict detection.

        Returns:
            DetectionResult with detected elements.
        """
        self._total_detections += 1
        start = time.time()

        # Step 1: Try primary engine
        primary_result = None
        if self.primary.is_ready:
            primary_result = self.primary.detect(
                window_title=window_title, region=region
            )

            if self._is_result_acceptable(primary_result):
                self._ufo2_successes += (
                    1 if self.primary.name == "UFO2" else 0
                )
                self._guirilla_successes += (
                    1 if self.primary.name == "GUIrilla" else 0
                )
                return primary_result

            logger.info(
                f"Primary engine ({self.primary.name}) result not acceptable: "
                f"success={primary_result.success}, "
                f"count={primary_result.count}"
            )

        # Step 2: Try fallback engine
        if self._auto_switch:
            fallback_loaded = self._ensure_fallback_loaded()
            if fallback_loaded:
                self._fallback_count += 1
                logger.info(
                    f"Falling back to {self.fallback.name} engine"
                )

                fallback_result = self.fallback.detect(
                    window_title=window_title, region=region
                )
                fallback_result.fallback_used = True

                if fallback_result.success:
                    self._guirilla_successes += (
                        1 if self.fallback.name == "GUIrilla" else 0
                    )
                    self._ufo2_successes += (
                        1 if self.fallback.name == "UFO2" else 0
                    )

                    # Optionally merge with primary results
                    if (
                        self._merge_results
                        and primary_result is not None
                        and primary_result.count > 0
                    ):
                        fallback_result = self._merge_detection_results(
                            primary_result, fallback_result
                        )

                    return fallback_result

        # Step 3: Both failed
        elapsed = (time.time() - start) * 1000
        error_msgs = []
        if primary_result:
            error_msgs.append(
                f"{self.primary.name}: {primary_result.error_message}"
            )

        return DetectionResult(
            success=False,
            error_message=" | ".join(error_msgs) or "All engines failed",
            detection_time_ms=elapsed,
            fallback_used=True,
        )

    def find_element(
        self,
        query: str,
        window_title: Optional[str] = None,
    ) -> Optional[UIElement]:
        """
        Find a specific UI element using hybrid detection.

        Args:
            query: Name/description of the element.
            window_title: Window to search in.

        Returns:
            Best matching UIElement or None.
        """
        # Try primary first
        if self.primary.is_ready:
            element = self.primary.detect_element(
                query, window_title=window_title
            )
            if element is not None and element.confidence >= self._ufo2_threshold:
                return element

        # Try fallback
        if self._auto_switch:
            fallback_loaded = self._ensure_fallback_loaded()
            if fallback_loaded:
                self._fallback_count += 1
                element = self.fallback.detect_element(
                    query, window_title=window_title
                )
                if element is not None:
                    return element

        return None

    def find_element_at(
        self,
        x: int,
        y: int,
        window_title: Optional[str] = None,
    ) -> Optional[UIElement]:
        """
        Find the UI element at a specific screen position.

        Args:
            x: Screen x coordinate.
            y: Screen y coordinate.
            window_title: Window to search in.

        Returns:
            UIElement at the given position, or None.
        """
        result = self.detect(window_title=window_title)
        if result.success:
            return result.find_at_point(x, y)
        return None

    def find_elements_by_type(
        self,
        element_type: ElementType,
        window_title: Optional[str] = None,
    ) -> List[UIElement]:
        """
        Find all elements of a given type.

        Args:
            element_type: Type of elements to find.
            window_title: Window to search in.

        Returns:
            List of matching UIElements.
        """
        result = self.detect(window_title=window_title)
        if result.success:
            return result.find_by_type(element_type)
        return []

    # ------------------------------------------------------------------
    # Result evaluation
    # ------------------------------------------------------------------

    def _is_result_acceptable(self, result: DetectionResult) -> bool:
        """
        Check whether a detection result is good enough to use.

        A result is rejected (triggering fallback) if:
            - Detection failed entirely
            - No elements were found
            - Average confidence is below threshold

        Args:
            result: DetectionResult to evaluate.

        Returns:
            True if the result is acceptable.
        """
        if not result.success:
            return False

        if result.count == 0:
            return False

        # Check average confidence
        threshold = (
            self._ufo2_threshold
            if result.source in (
                DetectionSource.UFO2_UIA,
                DetectionSource.UFO2_VISUAL,
                DetectionSource.UFO2_HYBRID,
            )
            else self._guirilla_threshold
        )

        avg_confidence = sum(
            e.confidence for e in result.elements
        ) / result.count

        if avg_confidence < threshold:
            logger.debug(
                f"Average confidence {avg_confidence:.2f} below "
                f"threshold {threshold}"
            )
            return False

        return True

    # ------------------------------------------------------------------
    # Result merging
    # ------------------------------------------------------------------

    def _merge_detection_results(
        self,
        primary: DetectionResult,
        fallback: DetectionResult,
    ) -> DetectionResult:
        """
        Merge results from primary and fallback engines.

        Uses IoU (Intersection over Union) to deduplicate elements
        that both engines detected. Keeps the higher-confidence one.

        Args:
            primary: Results from the primary engine.
            fallback: Results from the fallback engine.

        Returns:
            Merged DetectionResult.
        """
        merged_elements = list(fallback.elements)
        iou_threshold = 0.5

        for p_elem in primary.elements:
            is_duplicate = False

            for f_elem in fallback.elements:
                iou = p_elem.bbox.iou(f_elem.bbox)
                if iou >= iou_threshold:
                    is_duplicate = True
                    # Keep the one with higher confidence
                    if p_elem.confidence > f_elem.confidence:
                        idx = merged_elements.index(f_elem)
                        merged_elements[idx] = p_elem
                    break

            if not is_duplicate:
                merged_elements.append(p_elem)

        return DetectionResult(
            elements=merged_elements,
            source=fallback.source,
            success=True,
            detection_time_ms=(
                primary.detection_time_ms + fallback.detection_time_ms
            ),
            window_title=fallback.window_title or primary.window_title,
            fallback_used=True,
        )

    # ------------------------------------------------------------------
    # Status & statistics
    # ------------------------------------------------------------------

    def get_status(self) -> Dict:
        """Return status of the hybrid detector."""
        return {
            "primary_engine": self.primary.name,
            "primary_state": self.primary.state.name,
            "fallback_engine": self.fallback.name,
            "fallback_state": self.fallback.state.name,
            "auto_switch": self._auto_switch,
            "total_detections": self._total_detections,
            "ufo2_successes": self._ufo2_successes,
            "guirilla_successes": self._guirilla_successes,
            "fallback_count": self._fallback_count,
            "fallback_rate": (
                round(self._fallback_count / self._total_detections, 2)
                if self._total_detections > 0
                else 0.0
            ),
        }

    def get_engine_stats(self) -> Dict:
        """Return performance stats for both engines."""
        return {
            "ufo2": self._ufo2.get_stats(),
            "guirilla": self._guirilla.get_stats(),
        }

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_primary_engine(self, engine: str) -> None:
        """
        Switch the primary engine.

        Args:
            engine: "ufo2" or "guirilla".
        """
        if engine not in ("ufo2", "guirilla"):
            logger.error(f"Unknown engine: {engine}")
            return

        self._primary_engine = engine
        self._fallback_engine = "guirilla" if engine == "ufo2" else "ufo2"
        logger.info(
            f"Primary engine set to {engine}, "
            f"fallback set to {self._fallback_engine}"
        )

    def set_auto_switch(self, enabled: bool) -> None:
        """Enable or disable automatic fallback switching."""
        self._auto_switch = enabled
        logger.info(f"Auto-switch set to {enabled}")

    def clear_cache(self) -> None:
        """Clear detection caches for both engines."""
        self._ufo2.clear_cache()
        logger.debug("All detection caches cleared")


__all__ = ["HybridDetector"]
