"""
GUI Detection - Shared Types and Base Detector Interface.

Defines the UIElement dataclass, DetectionResult, and the abstract
BaseDetector that both UFO2Detector and GUIrillaDetector implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


# ======================================================================
# Enums
# ======================================================================


class ElementType(Enum):
    """Types of UI elements that can be detected."""
    BUTTON = auto()
    TEXT_FIELD = auto()
    CHECKBOX = auto()
    RADIO_BUTTON = auto()
    DROPDOWN = auto()
    MENU = auto()
    MENU_ITEM = auto()
    TAB = auto()
    LIST_ITEM = auto()
    TREE_ITEM = auto()
    SCROLLBAR = auto()
    SLIDER = auto()
    LINK = auto()
    IMAGE = auto()
    ICON = auto()
    LABEL = auto()
    WINDOW = auto()
    DIALOG = auto()
    TOOLBAR = auto()
    STATUS_BAR = auto()
    TOOLTIP = auto()
    UNKNOWN = auto()


class DetectionSource(Enum):
    """Which engine detected the element."""
    UFO2_UIA = auto()       # UFO2 via Windows UI Automation
    UFO2_VISUAL = auto()    # UFO2 via screenshot analysis
    UFO2_HYBRID = auto()    # UFO2 combined UIA + visual
    GUIRILLA = auto()       # GUIrilla-See visual detection
    CACHED = auto()         # From cache (no fresh detection)
    MANUAL = auto()         # User-selected element


class DetectorState(Enum):
    """State of a detector engine."""
    UNLOADED = auto()
    LOADING = auto()
    READY = auto()
    DETECTING = auto()
    ERROR = auto()


# ======================================================================
# Data Classes
# ======================================================================


@dataclass
class BoundingBox:
    """Axis-aligned bounding box in screen coordinates."""
    x: int          # Top-left x
    y: int          # Top-left y
    width: int      # Width in pixels
    height: int     # Height in pixels

    @property
    def center(self) -> Tuple[int, int]:
        """Return the center point of the bounding box."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def area(self) -> int:
        """Return the area in pixels."""
        return self.width * self.height

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def contains_point(self, px: int, py: int) -> bool:
        """Check if a point is inside this bounding box."""
        return (self.x <= px < self.right and
                self.y <= py < self.bottom)

    def iou(self, other: "BoundingBox") -> float:
        """
        Compute Intersection over Union with another bounding box.

        Args:
            other: Another BoundingBox.

        Returns:
            IoU value between 0.0 and 1.0.
        """
        # Intersection
        ix1 = max(self.x, other.x)
        iy1 = max(self.y, other.y)
        ix2 = min(self.right, other.right)
        iy2 = min(self.bottom, other.bottom)

        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0

        intersection = (ix2 - ix1) * (iy2 - iy1)
        union = self.area + other.area - intersection

        if union <= 0:
            return 0.0

        return intersection / union


@dataclass
class UIElement:
    """
    A detected UI element with metadata.

    This is the common data structure returned by all detection engines.
    """
    name: str                           # Element label/name
    element_type: ElementType           # Semantic type
    bbox: BoundingBox                   # Screen-space bounding box
    confidence: float                   # Detection confidence (0..1)
    source: DetectionSource             # Which engine detected it

    # Optional metadata
    automation_id: str = ""             # UIA AutomationId (UFO2)
    class_name: str = ""                # UIA ClassName
    control_type: str = ""              # UIA ControlType name
    value: str = ""                     # Current value (text fields, etc.)
    is_enabled: bool = True             # Whether the element is interactive
    is_visible: bool = True             # Whether the element is visible
    parent_name: str = ""               # Parent element name
    properties: Dict[str, Any] = field(default_factory=dict)

    @property
    def click_point(self) -> Tuple[int, int]:
        """Return the best point to click (center of bbox)."""
        return self.bbox.center

    def matches(self, query: str) -> bool:
        """
        Check if this element matches a search query (case-insensitive).

        Matches against name, automation_id, class_name, and value.

        Args:
            query: Search string.

        Returns:
            True if any field contains the query.
        """
        q = query.lower()
        return (
            q in self.name.lower()
            or q in self.automation_id.lower()
            or q in self.class_name.lower()
            or q in self.value.lower()
        )


@dataclass
class DetectionResult:
    """
    Result of a GUI detection operation.

    Contains the list of detected elements plus metadata about the
    detection (source, timing, success/failure).
    """
    elements: List[UIElement] = field(default_factory=list)
    source: DetectionSource = DetectionSource.UFO2_UIA
    success: bool = True
    error_message: str = ""
    detection_time_ms: float = 0.0
    screenshot_path: str = ""
    window_title: str = ""
    fallback_used: bool = False

    @property
    def count(self) -> int:
        """Number of elements detected."""
        return len(self.elements)

    def find_by_name(self, name: str) -> Optional[UIElement]:
        """Find the first element matching the given name."""
        for elem in self.elements:
            if elem.matches(name):
                return elem
        return None

    def find_by_type(self, element_type: ElementType) -> List[UIElement]:
        """Find all elements of a given type."""
        return [e for e in self.elements if e.element_type == element_type]

    def find_at_point(self, x: int, y: int) -> Optional[UIElement]:
        """Find the topmost element containing the given point."""
        # Return the smallest (most specific) element at this point
        candidates = [
            e for e in self.elements if e.bbox.contains_point(x, y)
        ]
        if not candidates:
            return None
        # Smallest area = most specific element
        return min(candidates, key=lambda e: e.bbox.area)

    def filter_by_confidence(self, min_confidence: float) -> List[UIElement]:
        """Return elements with confidence >= threshold."""
        return [e for e in self.elements if e.confidence >= min_confidence]

    def sort_by_confidence(self, descending: bool = True) -> None:
        """Sort elements by confidence in-place."""
        self.elements.sort(
            key=lambda e: e.confidence, reverse=descending
        )


# ======================================================================
# Abstract Base Detector
# ======================================================================


class BaseDetector(ABC):
    """
    Abstract base class for GUI element detectors.

    Both UFO2Detector and GUIrillaDetector implement this interface,
    allowing the HybridDetector to swap between them seamlessly.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._state: DetectorState = DetectorState.UNLOADED
        self._detection_count: int = 0
        self._total_time_ms: float = 0.0
        self._error_count: int = 0

    @property
    def state(self) -> DetectorState:
        return self._state

    @property
    def is_ready(self) -> bool:
        return self._state == DetectorState.READY

    @abstractmethod
    def load(self) -> None:
        """
        Load the detection model/engine.

        Raises:
            GUIDetectionError: If loading fails.
        """
        ...

    @abstractmethod
    def unload(self) -> None:
        """Release the detection model/engine and free resources."""
        ...

    @abstractmethod
    def detect(
        self,
        window_title: Optional[str] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> DetectionResult:
        """
        Detect UI elements in the current screen or a specific window.

        Args:
            window_title: Optional title of the target window.
                          If None, detects on the entire screen.
            region: Optional (x, y, w, h) region to restrict detection.

        Returns:
            DetectionResult with detected elements.
        """
        ...

    @abstractmethod
    def detect_element(
        self,
        query: str,
        window_title: Optional[str] = None,
    ) -> Optional[UIElement]:
        """
        Find a specific UI element by name/description.

        Args:
            query: Name or description of the element to find.
            window_title: Optional window to search in.

        Returns:
            The best-matching UIElement, or None.
        """
        ...

    def get_stats(self) -> Dict:
        """Return performance statistics."""
        avg_time = (
            self._total_time_ms / self._detection_count
            if self._detection_count > 0
            else 0.0
        )
        return {
            "name": self.name,
            "state": self._state.name,
            "detection_count": self._detection_count,
            "error_count": self._error_count,
            "avg_detection_time_ms": round(avg_time, 2),
            "total_time_ms": round(self._total_time_ms, 2),
        }


# ======================================================================
# Element type mapping helpers
# ======================================================================

# Map common UIA control type names to our ElementType enum
UIA_TYPE_MAP: Dict[str, ElementType] = {
    "Button": ElementType.BUTTON,
    "Edit": ElementType.TEXT_FIELD,
    "CheckBox": ElementType.CHECKBOX,
    "RadioButton": ElementType.RADIO_BUTTON,
    "ComboBox": ElementType.DROPDOWN,
    "Menu": ElementType.MENU,
    "MenuItem": ElementType.MENU_ITEM,
    "Tab": ElementType.TAB,
    "TabItem": ElementType.TAB,
    "ListItem": ElementType.LIST_ITEM,
    "TreeItem": ElementType.TREE_ITEM,
    "ScrollBar": ElementType.SCROLLBAR,
    "Slider": ElementType.SLIDER,
    "Hyperlink": ElementType.LINK,
    "Image": ElementType.IMAGE,
    "Text": ElementType.LABEL,
    "Window": ElementType.WINDOW,
    "Dialog": ElementType.DIALOG,
    "ToolBar": ElementType.TOOLBAR,
    "StatusBar": ElementType.STATUS_BAR,
    "ToolTip": ElementType.TOOLTIP,
    "Pane": ElementType.UNKNOWN,
    "Group": ElementType.UNKNOWN,
    "Custom": ElementType.UNKNOWN,
}


def map_uia_type(control_type_name: str) -> ElementType:
    """Map a UIA ControlType name to our ElementType enum."""
    return UIA_TYPE_MAP.get(control_type_name, ElementType.UNKNOWN)


__all__ = [
    "ElementType",
    "DetectionSource",
    "DetectorState",
    "BoundingBox",
    "UIElement",
    "DetectionResult",
    "BaseDetector",
    "UIA_TYPE_MAP",
    "map_uia_type",
]
