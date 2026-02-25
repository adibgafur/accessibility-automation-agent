"""
Tests for src.gui_detection module.

Tests the base types, UFO2 detector, GUIrilla detector, and hybrid
detector orchestration. Heavy dependencies (ctypes, torch, transformers)
are mocked.
"""

import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.gui_detection.base import (
    BoundingBox,
    UIElement,
    DetectionResult,
    DetectionSource,
    DetectorState,
    ElementType,
    map_uia_type,
)
from src.gui_detection.ufo2_detector import UFO2Detector, _ElementCache
from src.gui_detection.guirilla_detector import GUIrillaDetector
from src.gui_detection.hybrid_detector import HybridDetector
from src.utils.error_handler import GUIDetectionError, ModelLoadError


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(autouse=True)
def _reset_config():
    """Ensure config provides sensible defaults."""
    from src.utils.config_manager import ConfigManager

    dummy = {
        "gui_detection": {
            "primary_engine": "ufo2",
            "fallback_engine": "guirilla",
            "ufo2_confidence_threshold": 0.7,
            "guirilla_confidence_threshold": 0.5,
            "auto_switch_on_failure": True,
            "merge_results": False,
        },
        "ufo2": {
            "use_uia": True,
            "use_visual": False,
            "detection": {"max_detections": 50, "max_depth": 8},
            "uia": {"cache_timeout": 5.0},
        },
        "guirilla": {
            "model": {"name": "test-model", "device": "cpu"},
            "quantization": {"type": "fp32"},
            "inference": {"max_detections": 10, "timeout": 10.0},
            "visual": {"max_image_size": 1024},
            "cache": {"cache_dir": ".cache/test"},
        },
    }
    mgr = ConfigManager()
    for section, values in dummy.items():
        _set_nested(mgr, section, values)


def _set_nested(mgr, prefix, data):
    """Recursively set config values."""
    for k, v in data.items():
        key = f"{prefix}.{k}"
        if isinstance(v, dict):
            _set_nested(mgr, key, v)
        else:
            mgr.set(key, v)


def _make_element(
    name: str = "Button1",
    x: int = 100,
    y: int = 100,
    w: int = 80,
    h: int = 30,
    confidence: float = 0.9,
    source: DetectionSource = DetectionSource.UFO2_UIA,
    element_type: ElementType = ElementType.BUTTON,
) -> UIElement:
    """Helper to create a UIElement."""
    return UIElement(
        name=name,
        element_type=element_type,
        bbox=BoundingBox(x=x, y=y, width=w, height=h),
        confidence=confidence,
        source=source,
    )


def _make_result(
    elements=None,
    success=True,
    source=DetectionSource.UFO2_UIA,
) -> DetectionResult:
    """Helper to create a DetectionResult."""
    return DetectionResult(
        elements=elements or [],
        success=success,
        source=source,
    )


# ======================================================================
# Tests: BoundingBox
# ======================================================================


class TestBoundingBox:
    """Tests for BoundingBox dataclass."""

    def test_center(self):
        bb = BoundingBox(x=100, y=200, width=80, height=40)
        assert bb.center == (140, 220)

    def test_area(self):
        bb = BoundingBox(x=0, y=0, width=100, height=50)
        assert bb.area == 5000

    def test_right_and_bottom(self):
        bb = BoundingBox(x=10, y=20, width=30, height=40)
        assert bb.right == 40
        assert bb.bottom == 60

    def test_contains_point_inside(self):
        bb = BoundingBox(x=100, y=100, width=50, height=50)
        assert bb.contains_point(125, 125)

    def test_contains_point_corner(self):
        bb = BoundingBox(x=100, y=100, width=50, height=50)
        assert bb.contains_point(100, 100)  # top-left is included

    def test_contains_point_outside(self):
        bb = BoundingBox(x=100, y=100, width=50, height=50)
        assert not bb.contains_point(50, 50)
        assert not bb.contains_point(200, 200)

    def test_iou_identical_boxes(self):
        bb = BoundingBox(x=0, y=0, width=100, height=100)
        assert bb.iou(bb) == 1.0

    def test_iou_no_overlap(self):
        bb1 = BoundingBox(x=0, y=0, width=50, height=50)
        bb2 = BoundingBox(x=100, y=100, width=50, height=50)
        assert bb1.iou(bb2) == 0.0

    def test_iou_partial_overlap(self):
        bb1 = BoundingBox(x=0, y=0, width=100, height=100)
        bb2 = BoundingBox(x=50, y=50, width=100, height=100)
        iou = bb1.iou(bb2)
        assert 0.0 < iou < 1.0

        # Manual: intersection = 50*50=2500, union = 10000+10000-2500=17500
        assert abs(iou - 2500 / 17500) < 0.01

    def test_iou_zero_area(self):
        bb1 = BoundingBox(x=0, y=0, width=0, height=0)
        bb2 = BoundingBox(x=0, y=0, width=100, height=100)
        assert bb1.iou(bb2) == 0.0


# ======================================================================
# Tests: UIElement
# ======================================================================


class TestUIElement:
    """Tests for UIElement dataclass."""

    def test_click_point(self):
        elem = _make_element(x=100, y=200, w=80, h=40)
        assert elem.click_point == (140, 220)

    def test_matches_name(self):
        elem = _make_element(name="Save Button")
        assert elem.matches("save")
        assert elem.matches("Save")
        assert elem.matches("button")

    def test_matches_automation_id(self):
        elem = _make_element()
        elem.automation_id = "btnSave"
        assert elem.matches("btnSave")

    def test_matches_class_name(self):
        elem = _make_element()
        elem.class_name = "Qt5Button"
        assert elem.matches("Qt5")

    def test_matches_value(self):
        elem = _make_element()
        elem.value = "Hello World"
        assert elem.matches("hello")

    def test_no_match(self):
        elem = _make_element(name="Save")
        assert not elem.matches("Delete")

    def test_default_properties(self):
        elem = _make_element()
        assert elem.is_enabled
        assert elem.is_visible
        assert elem.automation_id == ""
        assert elem.properties == {}


# ======================================================================
# Tests: DetectionResult
# ======================================================================


class TestDetectionResult:
    """Tests for DetectionResult."""

    def test_count(self):
        result = _make_result(elements=[
            _make_element("A"),
            _make_element("B"),
        ])
        assert result.count == 2

    def test_find_by_name(self):
        result = _make_result(elements=[
            _make_element("Save"),
            _make_element("Cancel"),
        ])
        found = result.find_by_name("save")
        assert found is not None
        assert found.name == "Save"

    def test_find_by_name_not_found(self):
        result = _make_result(elements=[_make_element("Save")])
        assert result.find_by_name("delete") is None

    def test_find_by_type(self):
        result = _make_result(elements=[
            _make_element("Btn", element_type=ElementType.BUTTON),
            _make_element("Text", element_type=ElementType.TEXT_FIELD),
            _make_element("Btn2", element_type=ElementType.BUTTON),
        ])
        buttons = result.find_by_type(ElementType.BUTTON)
        assert len(buttons) == 2

    def test_find_at_point(self):
        result = _make_result(elements=[
            _make_element("Big", x=0, y=0, w=500, h=500),
            _make_element("Small", x=100, y=100, w=50, h=50),
        ])
        # Point inside both — should return the smaller one
        found = result.find_at_point(120, 120)
        assert found is not None
        assert found.name == "Small"

    def test_find_at_point_none(self):
        result = _make_result(elements=[
            _make_element(x=100, y=100, w=50, h=50),
        ])
        assert result.find_at_point(0, 0) is None

    def test_filter_by_confidence(self):
        result = _make_result(elements=[
            _make_element("High", confidence=0.9),
            _make_element("Low", confidence=0.3),
            _make_element("Med", confidence=0.6),
        ])
        filtered = result.filter_by_confidence(0.5)
        assert len(filtered) == 2

    def test_sort_by_confidence(self):
        result = _make_result(elements=[
            _make_element("Low", confidence=0.3),
            _make_element("High", confidence=0.9),
            _make_element("Med", confidence=0.6),
        ])
        result.sort_by_confidence()
        assert result.elements[0].confidence == 0.9
        assert result.elements[2].confidence == 0.3


# ======================================================================
# Tests: map_uia_type
# ======================================================================


class TestMapUIAType:
    """Tests for UIA type mapping."""

    def test_known_types(self):
        assert map_uia_type("Button") == ElementType.BUTTON
        assert map_uia_type("Edit") == ElementType.TEXT_FIELD
        assert map_uia_type("CheckBox") == ElementType.CHECKBOX
        assert map_uia_type("MenuItem") == ElementType.MENU_ITEM

    def test_unknown_type(self):
        assert map_uia_type("SomethingWeird") == ElementType.UNKNOWN


# ======================================================================
# Tests: _ElementCache
# ======================================================================


class TestElementCache:
    """Tests for the UFO2 element cache."""

    def test_put_and_get(self):
        cache = _ElementCache(ttl_seconds=5.0)
        result = _make_result()
        cache.put("key1", result)
        assert cache.get("key1") is result

    def test_cache_miss(self):
        cache = _ElementCache()
        assert cache.get("nonexistent") is None

    def test_cache_expiry(self):
        cache = _ElementCache(ttl_seconds=0.01)
        cache.put("key1", _make_result())
        time.sleep(0.02)
        assert cache.get("key1") is None

    def test_clear(self):
        cache = _ElementCache()
        cache.put("k1", _make_result())
        cache.put("k2", _make_result())
        assert cache.size == 2
        cache.clear()
        assert cache.size == 0


# ======================================================================
# Tests: UFO2Detector
# ======================================================================


class TestUFO2Detector:
    """Tests for UFO2Detector."""

    def test_initial_state(self):
        d = UFO2Detector()
        assert d.state == DetectorState.UNLOADED
        assert not d.is_ready
        assert d.name == "UFO2"

    @patch("src.gui_detection.ufo2_detector.ctypes", create=True)
    def test_load_success(self, mock_ctypes):
        """Loading should set state to READY."""
        d = UFO2Detector()
        mock_user32 = MagicMock()
        mock_user32.GetDesktopWindow.return_value = 12345

        # Mock the ctypes import inside the load method
        import sys
        mock_ctypes_module = MagicMock()
        mock_ctypes_module.windll.user32 = mock_user32

        with patch.dict(sys.modules, {"ctypes": mock_ctypes_module, "ctypes.wintypes": MagicMock()}):
            d.load()

        assert d.state == DetectorState.READY
        assert d.is_ready

    def test_detect_when_not_loaded(self):
        d = UFO2Detector()
        result = d.detect()
        assert not result.success
        assert "not loaded" in result.error_message

    def test_unload(self):
        d = UFO2Detector()
        d._state = DetectorState.READY
        d.unload()
        assert d.state == DetectorState.UNLOADED

    def test_classify_element(self):
        d = UFO2Detector()
        assert d._classify_element("Button") == ElementType.BUTTON
        assert d._classify_element("Edit") == ElementType.TEXT_FIELD
        assert d._classify_element("ComboBox") == ElementType.DROPDOWN
        assert d._classify_element("Static") == ElementType.LABEL
        assert d._classify_element("CustomWidget") == ElementType.UNKNOWN

    def test_get_stats(self):
        d = UFO2Detector()
        stats = d.get_stats()
        assert stats["name"] == "UFO2"
        assert stats["state"] == "UNLOADED"
        assert stats["detection_count"] == 0

    def test_cache_operations(self):
        d = UFO2Detector()
        assert d.get_cache_size() == 0
        d._cache.put("test", _make_result())
        assert d.get_cache_size() == 1
        d.clear_cache()
        assert d.get_cache_size() == 0


# ======================================================================
# Tests: GUIrillaDetector
# ======================================================================


class TestGUIrillaDetector:
    """Tests for GUIrillaDetector."""

    def test_initial_state(self):
        d = GUIrillaDetector()
        assert d.state == DetectorState.UNLOADED
        assert not d.is_ready
        assert d.name == "GUIrilla"

    def test_detect_when_not_loaded(self):
        d = GUIrillaDetector()
        result = d.detect()
        assert not result.success
        assert "not loaded" in result.error_message

    def test_unload(self):
        d = GUIrillaDetector()
        d._model = MagicMock()
        d._processor = MagicMock()
        d._torch = MagicMock()
        d._state = DetectorState.READY

        d.unload()

        assert d.state == DetectorState.UNLOADED
        assert d._model is None
        assert d._processor is None

    def test_classify_label(self):
        d = GUIrillaDetector()
        assert d._classify_label("Save Button") == ElementType.BUTTON
        assert d._classify_label("text input field") == ElementType.TEXT_FIELD
        assert d._classify_label("checkbox") == ElementType.CHECKBOX
        assert d._classify_label("dropdown menu") == ElementType.DROPDOWN
        assert d._classify_label("menu item") == ElementType.MENU_ITEM
        assert d._classify_label("hyperlink") == ElementType.LINK
        assert d._classify_label("icon") == ElementType.ICON
        assert d._classify_label("random thing") == ElementType.UNKNOWN

    def test_get_model_info(self):
        d = GUIrillaDetector()
        info = d.get_model_info()
        assert "model_name" in info
        assert "quantization" in info
        assert info["loaded"] is False

    def test_resize_image_no_resize_needed(self):
        """If image is small enough, no resize should happen."""
        d = GUIrillaDetector()
        d._max_image_size = 1024
        d._pil = {"Image": MagicMock()}

        mock_img = MagicMock()
        mock_img.size = (800, 600)

        result = d._resize_image(mock_img)
        assert result is mock_img  # Same object, no resize

    def test_resize_image_large(self):
        """Large images should be resized."""
        d = GUIrillaDetector()
        d._max_image_size = 1024

        mock_image_module = MagicMock()
        mock_image_module.LANCZOS = 1
        d._pil = {"Image": mock_image_module}

        mock_img = MagicMock()
        mock_img.size = (1920, 1080)
        mock_resized = MagicMock()
        mock_img.resize.return_value = mock_resized

        result = d._resize_image(mock_img)
        mock_img.resize.assert_called_once()

    def test_parse_output_text_fallback(self):
        """Test the fallback output parser."""
        d = GUIrillaDetector()
        text = "Save Button<loc_100><loc_200><loc_300><loc_400>Close<loc_500><loc_600><loc_700><loc_800>"

        elements = d._parse_output_text_fallback(
            text, img_w=999, img_h=999, offset_x=0, offset_y=0
        )

        assert len(elements) == 2
        assert elements[0].name == "Save Button"
        assert elements[1].name == "Close"


# ======================================================================
# Tests: HybridDetector
# ======================================================================


class TestHybridDetector:
    """Tests for the HybridDetector orchestrator."""

    def test_initial_state(self):
        hd = HybridDetector()
        assert hd.primary.name == "UFO2"
        assert hd.fallback.name == "GUIrilla"

    def test_primary_fallback_engines(self):
        hd = HybridDetector()
        assert isinstance(hd._ufo2, UFO2Detector)
        assert isinstance(hd._guirilla, GUIrillaDetector)

    def test_set_primary_engine(self):
        hd = HybridDetector()
        hd.set_primary_engine("guirilla")
        assert hd.primary.name == "GUIrilla"
        assert hd.fallback.name == "UFO2"

    def test_set_auto_switch(self):
        hd = HybridDetector()
        hd.set_auto_switch(False)
        assert not hd._auto_switch

    def test_detect_uses_primary_first(self):
        """Primary engine should be tried first."""
        hd = HybridDetector()

        # Mock primary as ready with good results
        mock_result = _make_result(
            elements=[_make_element("Btn", confidence=0.9)],
            source=DetectionSource.UFO2_UIA,
        )
        hd._ufo2._state = DetectorState.READY
        hd._ufo2.detect = MagicMock(return_value=mock_result)

        result = hd.detect()

        assert result.success
        assert result.count == 1
        hd._ufo2.detect.assert_called_once()

    def test_detect_falls_back_on_primary_failure(self):
        """Should fall back to GUIrilla when UFO2 fails."""
        hd = HybridDetector()

        # Primary fails
        hd._ufo2._state = DetectorState.READY
        hd._ufo2.detect = MagicMock(
            return_value=_make_result(success=False)
        )

        # Fallback succeeds
        fallback_result = _make_result(
            elements=[_make_element("Btn", confidence=0.8)],
            source=DetectionSource.GUIRILLA,
        )
        hd._guirilla._state = DetectorState.READY
        hd._guirilla.detect = MagicMock(return_value=fallback_result)

        result = hd.detect()

        assert result.success
        assert result.fallback_used
        assert hd._fallback_count == 1

    def test_detect_falls_back_on_low_confidence(self):
        """Should fall back when primary returns low-confidence results."""
        hd = HybridDetector()
        hd._ufo2_threshold = 0.7

        # Primary returns low confidence
        low_conf_result = _make_result(
            elements=[_make_element("Btn", confidence=0.3)],
            source=DetectionSource.UFO2_UIA,
        )
        hd._ufo2._state = DetectorState.READY
        hd._ufo2.detect = MagicMock(return_value=low_conf_result)

        # Fallback returns better results
        fallback_result = _make_result(
            elements=[_make_element("Btn", confidence=0.8)],
            source=DetectionSource.GUIRILLA,
        )
        hd._guirilla._state = DetectorState.READY
        hd._guirilla.detect = MagicMock(return_value=fallback_result)

        result = hd.detect()

        assert result.success
        assert result.fallback_used

    def test_detect_no_fallback_when_disabled(self):
        """When auto_switch is False, no fallback should be attempted."""
        hd = HybridDetector()
        hd._auto_switch = False

        # Primary fails
        hd._ufo2._state = DetectorState.READY
        hd._ufo2.detect = MagicMock(
            return_value=_make_result(success=False)
        )

        result = hd.detect()
        assert not result.success

    def test_detect_both_engines_fail(self):
        """When both engines fail, should return failure."""
        hd = HybridDetector()

        hd._ufo2._state = DetectorState.READY
        hd._ufo2.detect = MagicMock(
            return_value=_make_result(success=False)
        )

        hd._guirilla._state = DetectorState.READY
        hd._guirilla.detect = MagicMock(
            return_value=_make_result(success=False)
        )

        result = hd.detect()
        assert not result.success

    def test_find_element_primary_success(self):
        hd = HybridDetector()
        elem = _make_element("Save", confidence=0.9)

        hd._ufo2._state = DetectorState.READY
        hd._ufo2.detect_element = MagicMock(return_value=elem)

        found = hd.find_element("Save")
        assert found is not None
        assert found.name == "Save"

    def test_find_element_falls_back(self):
        hd = HybridDetector()

        # Primary returns nothing
        hd._ufo2._state = DetectorState.READY
        hd._ufo2.detect_element = MagicMock(return_value=None)

        # Fallback finds it
        elem = _make_element("Save", confidence=0.7)
        hd._guirilla._state = DetectorState.READY
        hd._guirilla.detect_element = MagicMock(return_value=elem)

        found = hd.find_element("Save")
        assert found is not None
        assert found.name == "Save"

    def test_find_element_at_position(self):
        hd = HybridDetector()

        elements = [
            _make_element("Big", x=0, y=0, w=500, h=500, confidence=0.9),
            _make_element("Small", x=100, y=100, w=50, h=50, confidence=0.9),
        ]
        hd._ufo2._state = DetectorState.READY
        hd._ufo2.detect = MagicMock(
            return_value=_make_result(elements=elements)
        )

        found = hd.find_element_at(120, 120)
        assert found is not None
        assert found.name == "Small"

    def test_find_elements_by_type(self):
        hd = HybridDetector()

        elements = [
            _make_element("Btn1", element_type=ElementType.BUTTON, confidence=0.9),
            _make_element("Text1", element_type=ElementType.TEXT_FIELD, confidence=0.9),
            _make_element("Btn2", element_type=ElementType.BUTTON, confidence=0.9),
        ]
        hd._ufo2._state = DetectorState.READY
        hd._ufo2.detect = MagicMock(
            return_value=_make_result(elements=elements)
        )

        buttons = hd.find_elements_by_type(ElementType.BUTTON)
        assert len(buttons) == 2

    def test_get_status(self):
        hd = HybridDetector()
        status = hd.get_status()

        assert "primary_engine" in status
        assert "fallback_engine" in status
        assert "total_detections" in status
        assert "fallback_rate" in status

    def test_get_engine_stats(self):
        hd = HybridDetector()
        stats = hd.get_engine_stats()

        assert "ufo2" in stats
        assert "guirilla" in stats

    def test_result_acceptability_check(self):
        hd = HybridDetector()
        hd._ufo2_threshold = 0.7

        # Good result
        good = _make_result(
            elements=[_make_element(confidence=0.9)],
            source=DetectionSource.UFO2_UIA,
        )
        assert hd._is_result_acceptable(good)

        # Failed result
        bad = _make_result(success=False)
        assert not hd._is_result_acceptable(bad)

        # Empty result
        empty = _make_result(elements=[])
        assert not hd._is_result_acceptable(empty)

        # Low confidence result
        low = _make_result(
            elements=[_make_element(confidence=0.3)],
            source=DetectionSource.UFO2_UIA,
        )
        assert not hd._is_result_acceptable(low)

    def test_merge_detection_results(self):
        """Merging should deduplicate by IoU and keep higher confidence."""
        hd = HybridDetector()

        primary = _make_result(
            elements=[
                _make_element("Btn1", x=100, y=100, w=50, h=30, confidence=0.95),
                _make_element("UniqueP", x=500, y=500, w=50, h=30, confidence=0.8),
            ]
        )
        fallback = _make_result(
            elements=[
                _make_element("Btn1_v", x=105, y=102, w=48, h=28, confidence=0.7),
                _make_element("UniqueF", x=300, y=300, w=50, h=30, confidence=0.6),
            ]
        )

        merged = hd._merge_detection_results(primary, fallback)

        # Should have 3 elements: Btn1(primary wins), UniqueF, UniqueP
        assert len(merged.elements) >= 2


# ======================================================================
# Tests: Enums
# ======================================================================


class TestEnums:
    """Tests for enum values."""

    def test_element_type_values(self):
        assert ElementType.BUTTON is not None
        assert ElementType.TEXT_FIELD is not None
        assert ElementType.UNKNOWN is not None

    def test_detection_source_values(self):
        assert DetectionSource.UFO2_UIA is not None
        assert DetectionSource.GUIRILLA is not None
        assert DetectionSource.CACHED is not None

    def test_detector_state_values(self):
        assert DetectorState.UNLOADED is not None
        assert DetectorState.READY is not None
        assert DetectorState.ERROR is not None


# ======================================================================
# Tests: BaseDetector (abstract)
# ======================================================================


class TestBaseDetector:
    """Tests for BaseDetector abstract interface."""

    def test_cannot_instantiate_directly(self):
        """BaseDetector is abstract, can't be instantiated."""
        from src.gui_detection.base import BaseDetector

        with pytest.raises(TypeError):
            BaseDetector("test")

    def test_get_stats_on_subclass(self):
        d = UFO2Detector()
        stats = d.get_stats()
        assert isinstance(stats, dict)
        assert "name" in stats
        assert "detection_count" in stats
