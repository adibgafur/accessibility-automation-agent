"""
GUI Detection modules for the Accessibility Automation Agent.

Provides hybrid UI element detection using UFO2 (primary) and
GUIrilla-See-0.7B (fallback).

Architecture:
    - BaseDetector: Abstract interface implemented by both engines
    - UFO2Detector: Primary engine using Windows UIA (fast, native)
    - GUIrillaDetector: Fallback engine using visual detection (ML-based)
    - HybridDetector: Orchestrator with auto-fallback logic
"""

from .base import (
    ElementType,
    DetectionSource,
    DetectorState,
    BoundingBox,
    UIElement,
    DetectionResult,
    BaseDetector,
    UIA_TYPE_MAP,
    map_uia_type,
)
from .ufo2_detector import UFO2Detector
from .guirilla_detector import GUIrillaDetector
from .hybrid_detector import HybridDetector

__all__ = [
    # Base types
    "ElementType",
    "DetectionSource",
    "DetectorState",
    "BoundingBox",
    "UIElement",
    "DetectionResult",
    "BaseDetector",
    "UIA_TYPE_MAP",
    "map_uia_type",
    # Engines
    "UFO2Detector",
    "GUIrillaDetector",
    "HybridDetector",
]
