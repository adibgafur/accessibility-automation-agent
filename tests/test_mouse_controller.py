"""
Tests for src.core.mouse_controller.

These tests verify the MouseController's public API without requiring
a real display or pyautogui. The pyautogui module is fully mocked.
"""

import time
from collections import namedtuple
from typing import Any, Dict
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from src.utils.error_handler import AutomationError


# Named tuples that mimic pyautogui return types
_Point = namedtuple("Point", ["x", "y"])
_Size = namedtuple("Size", ["width", "height"])


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch):
    """Supply sensible config defaults so MouseController.__init__ works."""
    from src.utils.config_manager import ConfigManager

    defaults = {
        "mouse.move_duration": 0.1,
        "mouse.smooth_tween": "easeOutQuad",
        "mouse.type_interval": 0.02,
        "mouse.failsafe": True,
        "mouse.pause": 0.01,
    }

    original_get = ConfigManager.get

    def patched_get(self_or_key, key=None, default=None):
        """Handle both ConfigManager().get(k,d) and config.get(k,d)."""
        # ConfigManager.get is called as config.get(key, default)
        if key is None:
            # Called as get(key) — self_or_key is the key
            lookup_key = self_or_key
            fallback = default
        else:
            lookup_key = key
            fallback = default

        if lookup_key in defaults:
            return defaults[lookup_key]
        return fallback

    monkeypatch.setattr(ConfigManager, "get", patched_get)


@pytest.fixture()
def mock_pyautogui():
    """Create a comprehensive mock of the pyautogui module."""
    mock = MagicMock()
    mock.FAILSAFE = True
    mock.PAUSE = 0.01
    mock.size.return_value = _Size(1920, 1080)
    mock.position.return_value = _Point(500, 300)
    return mock


@pytest.fixture()
def controller(mock_pyautogui, monkeypatch):
    """
    Return a MouseController with pyautogui pre-injected.

    This avoids the lazy import and gives tests direct access to the mock.
    """
    from src.core.mouse_controller import MouseController

    ctrl = MouseController()
    # Inject mock directly, bypassing lazy import
    ctrl._pyautogui = mock_pyautogui
    ctrl._screen_width = 1920
    ctrl._screen_height = 1080
    ctrl.current_position = (500, 300)
    return ctrl


@pytest.fixture()
def controller_no_pyautogui():
    """Return a MouseController that has NOT loaded pyautogui yet."""
    from src.core.mouse_controller import MouseController

    ctrl = MouseController()
    return ctrl


# ======================================================================
# Lazy import
# ======================================================================


class TestLazyImport:
    """Test _ensure_pyautogui lazy loading."""

    def test_pyautogui_none_before_first_call(self, controller_no_pyautogui):
        assert controller_no_pyautogui._pyautogui is None

    def test_ensure_loads_pyautogui(self, controller_no_pyautogui, monkeypatch):
        mock_pag = MagicMock()
        mock_pag.size.return_value = _Size(1920, 1080)
        mock_pag.position.return_value = _Point(0, 0)

        import importlib
        monkeypatch.setattr(
            "builtins.__import__",
            lambda name, *a, **kw: mock_pag if name == "pyautogui"
                else importlib.__import__(name, *a, **kw),
        )

        controller_no_pyautogui._ensure_pyautogui()
        assert controller_no_pyautogui._pyautogui is not None

    def test_ensure_sets_failsafe(self, controller_no_pyautogui, monkeypatch):
        mock_pag = MagicMock()
        mock_pag.size.return_value = _Size(1920, 1080)
        mock_pag.position.return_value = _Point(0, 0)

        with patch.dict("sys.modules", {"pyautogui": mock_pag}):
            controller_no_pyautogui._ensure_pyautogui()

        assert mock_pag.FAILSAFE is True

    def test_ensure_idempotent(self, controller, mock_pyautogui):
        """Calling _ensure_pyautogui twice should not re-import."""
        original = controller._pyautogui
        controller._ensure_pyautogui()
        assert controller._pyautogui is original

    def test_import_error_raises_automation_error(
        self, controller_no_pyautogui, monkeypatch
    ):
        def fail_import(name, *a, **kw):
            if name == "pyautogui":
                raise ImportError("no pyautogui")
            import importlib
            return importlib.__import__(name, *a, **kw)

        monkeypatch.setattr("builtins.__import__", fail_import)

        with pytest.raises(AutomationError, match="pyautogui not installed"):
            controller_no_pyautogui._ensure_pyautogui()


# ======================================================================
# Mouse Movement
# ======================================================================


class TestMouseMovement:
    """Test move_to and move_relative."""

    def test_move_to_basic(self, controller, mock_pyautogui):
        controller.move_to(100, 200)
        mock_pyautogui.moveTo.assert_called_once_with(100, 200, duration=0.1)
        assert controller.current_position == (100, 200)

    def test_move_to_no_smooth(self, controller, mock_pyautogui):
        controller.move_to(100, 200, smooth=False)
        mock_pyautogui.moveTo.assert_called_once_with(100, 200, duration=0)

    def test_move_to_clamps_negative(self, controller, mock_pyautogui):
        controller.move_to(-50, -100)
        mock_pyautogui.moveTo.assert_called_once_with(0, 0, duration=0.1)
        assert controller.current_position == (0, 0)

    def test_move_to_clamps_over_screen(self, controller, mock_pyautogui):
        controller.move_to(5000, 3000)
        # screen is 1920x1080, so clamped to 1919, 1079
        mock_pyautogui.moveTo.assert_called_once_with(1919, 1079, duration=0.1)
        assert controller.current_position == (1919, 1079)

    def test_move_to_increments_move_count(self, controller, mock_pyautogui):
        assert controller._move_count == 0
        controller.move_to(100, 200)
        assert controller._move_count == 1
        controller.move_to(300, 400)
        assert controller._move_count == 2

    def test_move_to_records_action_when_recording(
        self, controller, mock_pyautogui
    ):
        controller.start_recording()
        controller.move_to(100, 200)
        actions = controller.get_recorded_actions()
        assert len(actions) == 1
        assert actions[0]["type"] == "move_to"
        assert actions[0]["x"] == 100
        assert actions[0]["y"] == 200

    def test_move_to_error_raises_automation_error(
        self, controller, mock_pyautogui
    ):
        mock_pyautogui.moveTo.side_effect = RuntimeError("display error")
        with pytest.raises(AutomationError, match="Failed to move mouse"):
            controller.move_to(100, 200)

    def test_move_relative(self, controller, mock_pyautogui):
        mock_pyautogui.position.return_value = _Point(550, 350)
        controller.move_relative(50, 50)
        mock_pyautogui.moveRel.assert_called_once_with(50, 50, duration=0.1)
        assert controller.current_position == (550, 350)

    def test_move_relative_negative(self, controller, mock_pyautogui):
        mock_pyautogui.position.return_value = _Point(400, 200)
        controller.move_relative(-100, -100)
        mock_pyautogui.moveRel.assert_called_once_with(-100, -100, duration=0.1)
        assert controller.current_position == (400, 200)

    def test_move_relative_error(self, controller, mock_pyautogui):
        mock_pyautogui.moveRel.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Relative move failed"):
            controller.move_relative(10, 10)


# ======================================================================
# Clicking
# ======================================================================


class TestClicking:
    """Test click, double_click, right_click, middle_click, triple_click."""

    def test_left_click_default(self, controller, mock_pyautogui):
        controller.click()
        mock_pyautogui.click.assert_called_once_with(button="left")
        assert controller._click_count == 1

    def test_right_click(self, controller, mock_pyautogui):
        controller.right_click()
        mock_pyautogui.click.assert_called_once_with(button="right")

    def test_middle_click(self, controller, mock_pyautogui):
        controller.middle_click()
        mock_pyautogui.click.assert_called_once_with(button="middle")

    def test_click_at_position(self, controller, mock_pyautogui):
        controller.click(x=100, y=200)
        mock_pyautogui.click.assert_called_once_with(
            button="left", x=100, y=200
        )
        assert controller.current_position == (100, 200)

    def test_click_no_position_keeps_current(self, controller, mock_pyautogui):
        original = controller.current_position
        controller.click()
        assert controller.current_position == original

    def test_click_increments_count(self, controller, mock_pyautogui):
        controller.click()
        controller.click()
        controller.click()
        assert controller._click_count == 3

    def test_click_error(self, controller, mock_pyautogui):
        mock_pyautogui.click.side_effect = RuntimeError("no display")
        with pytest.raises(AutomationError, match="Click failed"):
            controller.click()

    def test_double_click(self, controller, mock_pyautogui):
        controller.double_click()
        mock_pyautogui.doubleClick.assert_called_once_with()
        assert controller._click_count == 1

    def test_double_click_at_position(self, controller, mock_pyautogui):
        controller.double_click(x=300, y=400)
        mock_pyautogui.doubleClick.assert_called_once_with(x=300, y=400)

    def test_double_click_error(self, controller, mock_pyautogui):
        mock_pyautogui.doubleClick.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Double-click failed"):
            controller.double_click()

    def test_triple_click(self, controller, mock_pyautogui):
        controller.triple_click()
        mock_pyautogui.click.assert_called_once_with(clicks=3)

    def test_triple_click_at_position(self, controller, mock_pyautogui):
        controller.triple_click(x=100, y=200)
        mock_pyautogui.click.assert_called_once_with(clicks=3, x=100, y=200)

    def test_triple_click_error(self, controller, mock_pyautogui):
        mock_pyautogui.click.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Triple-click failed"):
            controller.triple_click()

    def test_right_click_at_position(self, controller, mock_pyautogui):
        controller.right_click(x=50, y=60)
        mock_pyautogui.click.assert_called_once_with(
            button="right", x=50, y=60
        )

    def test_middle_click_at_position(self, controller, mock_pyautogui):
        controller.middle_click(x=70, y=80)
        mock_pyautogui.click.assert_called_once_with(
            button="middle", x=70, y=80
        )

    def test_click_records_action(self, controller, mock_pyautogui):
        controller.start_recording()
        controller.click(x=10, y=20)
        actions = controller.get_recorded_actions()
        assert len(actions) == 1
        assert actions[0]["type"] == "click"
        assert actions[0]["button"] == "left"


# ======================================================================
# Drag and Drop
# ======================================================================


class TestDragAndDrop:
    """Test start_drag, end_drag, drag_to, is_dragging."""

    def test_start_drag(self, controller, mock_pyautogui):
        assert controller.is_dragging is False
        controller.start_drag()
        mock_pyautogui.mouseDown.assert_called_once()
        assert controller.is_dragging is True
        assert controller._drag_start == (500, 300)

    def test_end_drag(self, controller, mock_pyautogui):
        controller.start_drag()
        controller.end_drag()
        mock_pyautogui.mouseUp.assert_called_once()
        assert controller.is_dragging is False
        assert controller._drag_start is None

    def test_drag_to(self, controller, mock_pyautogui):
        controller.current_position = (100, 100)
        controller.drag_to(300, 400, duration=0.5)
        mock_pyautogui.drag.assert_called_once_with(200, 300, duration=0.5)
        assert controller.current_position == (300, 400)

    def test_drag_to_records_action(self, controller, mock_pyautogui):
        controller.start_recording()
        controller.current_position = (0, 0)
        controller.drag_to(100, 200)
        actions = controller.get_recorded_actions()
        # start_drag is not called here, drag_to is the only action
        assert any(a["type"] == "drag_to" for a in actions)

    def test_start_drag_error(self, controller, mock_pyautogui):
        mock_pyautogui.mouseDown.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Start drag failed"):
            controller.start_drag()

    def test_end_drag_error(self, controller, mock_pyautogui):
        mock_pyautogui.mouseUp.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="End drag failed"):
            controller.end_drag()

    def test_drag_to_error(self, controller, mock_pyautogui):
        mock_pyautogui.drag.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Drag failed"):
            controller.drag_to(100, 200)

    def test_is_dragging_property(self, controller):
        assert controller.is_dragging is False
        controller._dragging = True
        assert controller.is_dragging is True


# ======================================================================
# Keyboard
# ======================================================================


class TestKeyboard:
    """Test type_text, press_key, key_down, key_up, hotkey, press_keys_sequence."""

    def test_type_ascii_text(self, controller, mock_pyautogui):
        controller.type_text("hello")
        mock_pyautogui.write.assert_called_once_with(
            "hello", interval=0.02
        )
        assert controller._key_count == 5

    def test_type_text_custom_interval(self, controller, mock_pyautogui):
        controller.type_text("ab", interval=0.05)
        mock_pyautogui.write.assert_called_once_with("ab", interval=0.05)

    def test_type_unicode_uses_clipboard(self, controller, mock_pyautogui):
        """Bengali text should go through clipboard paste."""
        with patch("src.core.mouse_controller.time") as mock_time:
            mock_time.time.return_value = 1000
            mock_time.sleep = MagicMock()
            with patch("pyperclip.paste", return_value=""):
                with patch("pyperclip.copy") as mock_copy:
                    controller.type_text("হ্যালো")  # Bengali

        mock_copy.assert_called()
        # Should call hotkey ctrl+v for paste
        mock_pyautogui.hotkey.assert_called_with("ctrl", "v")

    def test_type_unicode_fallback_no_pyperclip(
        self, controller, mock_pyautogui, monkeypatch
    ):
        """If pyperclip is not installed, fall back to press() per char."""
        import sys

        # Remove pyperclip from importable modules
        def fail_import(name, *a, **kw):
            if name == "pyperclip":
                raise ImportError("no pyperclip")
            import importlib
            return importlib.__import__(name, *a, **kw)

        monkeypatch.setattr("builtins.__import__", fail_import)

        controller.type_text("বা")  # 2 Bengali chars
        # Fallback uses press() for each character
        assert mock_pyautogui.press.call_count == 2

    def test_type_text_records_action(self, controller, mock_pyautogui):
        controller.start_recording()
        controller.type_text("test")
        actions = controller.get_recorded_actions()
        assert actions[0]["type"] == "type_text"
        assert actions[0]["text"] == "test"

    def test_type_text_error(self, controller, mock_pyautogui):
        mock_pyautogui.write.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Type text failed"):
            controller.type_text("fail")

    def test_press_key(self, controller, mock_pyautogui):
        controller.press_key("enter")
        mock_pyautogui.press.assert_called_once_with("enter")
        assert controller._key_count == 1

    def test_press_key_records_action(self, controller, mock_pyautogui):
        controller.start_recording()
        controller.press_key("tab")
        actions = controller.get_recorded_actions()
        assert actions[0]["type"] == "press_key"
        assert actions[0]["key"] == "tab"

    def test_press_key_error(self, controller, mock_pyautogui):
        mock_pyautogui.press.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Key press failed"):
            controller.press_key("enter")

    def test_key_down(self, controller, mock_pyautogui):
        controller.key_down("shift")
        mock_pyautogui.keyDown.assert_called_once_with("shift")

    def test_key_down_error(self, controller, mock_pyautogui):
        mock_pyautogui.keyDown.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Key down failed"):
            controller.key_down("ctrl")

    def test_key_up(self, controller, mock_pyautogui):
        controller.key_up("shift")
        mock_pyautogui.keyUp.assert_called_once_with("shift")

    def test_key_up_error(self, controller, mock_pyautogui):
        mock_pyautogui.keyUp.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Key up failed"):
            controller.key_up("ctrl")

    def test_hotkey(self, controller, mock_pyautogui):
        controller.hotkey("ctrl", "c")
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "c")
        assert controller._key_count == 1

    def test_hotkey_three_keys(self, controller, mock_pyautogui):
        controller.hotkey("ctrl", "shift", "s")
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "shift", "s")

    def test_hotkey_records_action(self, controller, mock_pyautogui):
        controller.start_recording()
        controller.hotkey("alt", "f4")
        actions = controller.get_recorded_actions()
        assert actions[0]["type"] == "hotkey"
        assert actions[0]["keys"] == ["alt", "f4"]

    def test_hotkey_error(self, controller, mock_pyautogui):
        mock_pyautogui.hotkey.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Hotkey failed"):
            controller.hotkey("ctrl", "z")

    def test_press_keys_sequence(self, controller, mock_pyautogui):
        controller.press_keys_sequence(["a", "b", "c"], interval=0)
        assert mock_pyautogui.press.call_count == 3
        mock_pyautogui.press.assert_any_call("a")
        mock_pyautogui.press.assert_any_call("b")
        mock_pyautogui.press.assert_any_call("c")

    def test_press_keys_sequence_with_interval(
        self, controller, mock_pyautogui
    ):
        with patch("src.core.mouse_controller.time") as mock_time:
            mock_time.time.return_value = 1000
            controller.press_keys_sequence(["x", "y"], interval=0.1)
            # time.sleep called between keys
            assert mock_time.sleep.call_count == 2


# ======================================================================
# Clipboard Shortcuts
# ======================================================================


class TestClipboardShortcuts:
    """Test copy, paste, cut, select_all, undo, redo, save, find."""

    def test_copy(self, controller, mock_pyautogui):
        controller.copy()
        mock_pyautogui.hotkey.assert_called_with("ctrl", "c")

    def test_paste(self, controller, mock_pyautogui):
        controller.paste()
        mock_pyautogui.hotkey.assert_called_with("ctrl", "v")

    def test_cut(self, controller, mock_pyautogui):
        controller.cut()
        mock_pyautogui.hotkey.assert_called_with("ctrl", "x")

    def test_select_all(self, controller, mock_pyautogui):
        controller.select_all()
        mock_pyautogui.hotkey.assert_called_with("ctrl", "a")

    def test_undo(self, controller, mock_pyautogui):
        controller.undo()
        mock_pyautogui.hotkey.assert_called_with("ctrl", "z")

    def test_redo(self, controller, mock_pyautogui):
        controller.redo()
        mock_pyautogui.hotkey.assert_called_with("ctrl", "y")

    def test_save(self, controller, mock_pyautogui):
        controller.save()
        mock_pyautogui.hotkey.assert_called_with("ctrl", "s")

    def test_find(self, controller, mock_pyautogui):
        controller.find()
        mock_pyautogui.hotkey.assert_called_with("ctrl", "f")


# ======================================================================
# Window Shortcuts
# ======================================================================


class TestWindowShortcuts:
    """Test close_tab, new_tab, switch_window, minimize_window, etc."""

    def test_close_tab(self, controller, mock_pyautogui):
        controller.close_tab()
        mock_pyautogui.hotkey.assert_called_with("ctrl", "w")

    def test_new_tab(self, controller, mock_pyautogui):
        controller.new_tab()
        mock_pyautogui.hotkey.assert_called_with("ctrl", "t")

    def test_switch_window(self, controller, mock_pyautogui):
        controller.switch_window()
        mock_pyautogui.hotkey.assert_called_with("alt", "tab")

    def test_minimize_window(self, controller, mock_pyautogui):
        controller.minimize_window()
        mock_pyautogui.hotkey.assert_called_with("win", "d")

    def test_screenshot_key(self, controller, mock_pyautogui):
        controller.screenshot_key()
        mock_pyautogui.hotkey.assert_called_with("win", "shift", "s")

    def test_task_manager(self, controller, mock_pyautogui):
        controller.task_manager()
        mock_pyautogui.hotkey.assert_called_with("ctrl", "shift", "escape")


# ======================================================================
# Scrolling
# ======================================================================


class TestScrolling:
    """Test scroll and scroll_horizontal."""

    def test_scroll_up(self, controller, mock_pyautogui):
        controller.scroll(5)
        mock_pyautogui.scroll.assert_called_once_with(5)

    def test_scroll_down(self, controller, mock_pyautogui):
        controller.scroll(-3)
        mock_pyautogui.scroll.assert_called_once_with(-3)

    def test_scroll_default(self, controller, mock_pyautogui):
        controller.scroll()
        mock_pyautogui.scroll.assert_called_once_with(3)

    def test_scroll_records_action(self, controller, mock_pyautogui):
        controller.start_recording()
        controller.scroll(10)
        actions = controller.get_recorded_actions()
        assert actions[0]["type"] == "scroll"
        assert actions[0]["clicks"] == 10

    def test_scroll_error(self, controller, mock_pyautogui):
        mock_pyautogui.scroll.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Scroll failed"):
            controller.scroll()

    def test_scroll_horizontal_right(self, controller, mock_pyautogui):
        controller.scroll_horizontal(5)
        mock_pyautogui.hscroll.assert_called_once_with(5)

    def test_scroll_horizontal_left(self, controller, mock_pyautogui):
        controller.scroll_horizontal(-3)
        mock_pyautogui.hscroll.assert_called_once_with(-3)

    def test_scroll_horizontal_error(self, controller, mock_pyautogui):
        mock_pyautogui.hscroll.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Horizontal scroll failed"):
            controller.scroll_horizontal()


# ======================================================================
# Screen Info & Position
# ======================================================================


class TestScreenInfo:
    """Test get_position, get_screen_size, set_screen_size, config setters."""

    def test_get_position(self, controller, mock_pyautogui):
        mock_pyautogui.position.return_value = _Point(123, 456)
        pos = controller.get_position()
        assert pos == (123, 456)
        assert controller.current_position == (123, 456)

    def test_get_position_error_returns_cached(
        self, controller, mock_pyautogui
    ):
        controller.current_position = (999, 888)
        mock_pyautogui.position.side_effect = RuntimeError("fail")
        pos = controller.get_position()
        assert pos == (999, 888)

    def test_get_screen_size(self, controller):
        assert controller.get_screen_size() == (1920, 1080)

    def test_set_screen_size(self, controller):
        controller.set_screen_size(3840, 2160)
        assert controller.get_screen_size() == (3840, 2160)
        assert controller._screen_width == 3840
        assert controller._screen_height == 2160

    def test_set_move_duration(self, controller):
        controller.set_move_duration(0.5)
        assert controller._move_duration == 0.5

    def test_set_move_duration_clamps_min(self, controller):
        controller.set_move_duration(-1.0)
        assert controller._move_duration == 0.0

    def test_set_move_duration_clamps_max(self, controller):
        controller.set_move_duration(10.0)
        assert controller._move_duration == 2.0

    def test_set_type_interval(self, controller):
        controller.set_type_interval(0.1)
        assert controller._type_interval == 0.1

    def test_set_type_interval_clamps_min(self, controller):
        controller.set_type_interval(-0.5)
        assert controller._type_interval == 0.0

    def test_set_type_interval_clamps_max(self, controller):
        controller.set_type_interval(5.0)
        assert controller._type_interval == 1.0


# ======================================================================
# Action Recording
# ======================================================================


class TestActionRecording:
    """Test start_recording, stop_recording, get_recorded_actions."""

    def test_not_recording_by_default(self, controller):
        assert controller._record_actions is False

    def test_start_recording(self, controller):
        controller.start_recording()
        assert controller._record_actions is True
        assert controller._action_history == []

    def test_stop_recording_returns_actions(
        self, controller, mock_pyautogui
    ):
        controller.start_recording()
        controller.click()
        controller.press_key("enter")
        actions = controller.stop_recording()

        assert controller._record_actions is False
        assert len(actions) == 2
        assert actions[0]["type"] == "click"
        assert actions[1]["type"] == "press_key"

    def test_stop_recording_returns_copy(self, controller, mock_pyautogui):
        """Returned list should be a copy, not the internal list."""
        controller.start_recording()
        controller.click()
        actions = controller.stop_recording()
        actions.clear()
        # Internal history should still have the action
        assert len(controller._action_history) == 1

    def test_get_recorded_actions_returns_copy(
        self, controller, mock_pyautogui
    ):
        controller.start_recording()
        controller.click()
        actions = controller.get_recorded_actions()
        actions.clear()
        assert len(controller._action_history) == 1

    def test_start_recording_clears_history(
        self, controller, mock_pyautogui
    ):
        controller.start_recording()
        controller.click()
        assert len(controller._action_history) == 1

        # Start a new recording — should clear
        controller.start_recording()
        assert len(controller._action_history) == 0

    def test_no_recording_when_not_started(
        self, controller, mock_pyautogui
    ):
        controller.click()
        controller.move_to(100, 200)
        assert len(controller._action_history) == 0

    def test_recorded_action_has_timestamp(
        self, controller, mock_pyautogui
    ):
        controller.start_recording()
        controller.click()
        action = controller._action_history[0]
        assert "timestamp" in action
        assert isinstance(action["timestamp"], float)

    def test_recorded_action_has_position(
        self, controller, mock_pyautogui
    ):
        controller.start_recording()
        controller.click()
        action = controller._action_history[0]
        assert "position" in action


# ======================================================================
# Replay Actions
# ======================================================================


class TestReplayActions:
    """Test replay_actions and _execute_action."""

    def test_replay_empty_list(self, controller):
        # Should not raise
        controller.replay_actions([])

    def test_replay_click(self, controller, mock_pyautogui):
        actions = [
            {
                "type": "click",
                "timestamp": 1000.0,
                "position": (100, 200),
                "button": "left",
                "x": None,
                "y": None,
            }
        ]
        controller.replay_actions(actions)
        mock_pyautogui.click.assert_called_once_with(
            button="left", x=None, y=None
        )

    def test_replay_move_to(self, controller, mock_pyautogui):
        actions = [
            {
                "type": "move_to",
                "timestamp": 1000.0,
                "position": (100, 200),
                "x": 300,
                "y": 400,
                "smooth": True,
            }
        ]
        controller.replay_actions(actions)
        mock_pyautogui.moveTo.assert_called_once()

    def test_replay_type_text(self, controller, mock_pyautogui):
        actions = [
            {
                "type": "type_text",
                "timestamp": 1000.0,
                "position": (100, 200),
                "text": "hello",
            }
        ]
        controller.replay_actions(actions)
        mock_pyautogui.write.assert_called_once()

    def test_replay_hotkey(self, controller, mock_pyautogui):
        actions = [
            {
                "type": "hotkey",
                "timestamp": 1000.0,
                "position": (100, 200),
                "keys": ["ctrl", "s"],
            }
        ]
        controller.replay_actions(actions)
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "s")

    def test_replay_scroll(self, controller, mock_pyautogui):
        actions = [
            {
                "type": "scroll",
                "timestamp": 1000.0,
                "position": (100, 200),
                "clicks": -5,
            }
        ]
        controller.replay_actions(actions)
        mock_pyautogui.scroll.assert_called_once_with(-5)

    def test_replay_press_key(self, controller, mock_pyautogui):
        actions = [
            {
                "type": "press_key",
                "timestamp": 1000.0,
                "position": (100, 200),
                "key": "enter",
            }
        ]
        controller.replay_actions(actions)
        mock_pyautogui.press.assert_called_once_with("enter")

    def test_replay_double_click(self, controller, mock_pyautogui):
        actions = [
            {
                "type": "double_click",
                "timestamp": 1000.0,
                "position": (100, 200),
                "x": None,
                "y": None,
            }
        ]
        controller.replay_actions(actions)
        mock_pyautogui.doubleClick.assert_called_once()

    def test_replay_triple_click(self, controller, mock_pyautogui):
        actions = [
            {
                "type": "triple_click",
                "timestamp": 1000.0,
                "position": (100, 200),
                "x": None,
                "y": None,
            }
        ]
        controller.replay_actions(actions)
        mock_pyautogui.click.assert_called_once()

    def test_replay_start_and_end_drag(self, controller, mock_pyautogui):
        actions = [
            {"type": "start_drag", "timestamp": 1000.0, "position": (100, 200)},
            {"type": "end_drag", "timestamp": 1001.0, "position": (300, 400)},
        ]
        with patch("src.core.mouse_controller.time") as mock_time:
            mock_time.time.return_value = 1000
            mock_time.sleep = MagicMock()
            controller.replay_actions(actions, speed=10.0)

        mock_pyautogui.mouseDown.assert_called_once()
        mock_pyautogui.mouseUp.assert_called_once()

    def test_replay_drag_to(self, controller, mock_pyautogui):
        actions = [
            {
                "type": "drag_to",
                "timestamp": 1000.0,
                "position": (100, 200),
                "x": 500,
                "y": 600,
            }
        ]
        controller.replay_actions(actions)
        mock_pyautogui.drag.assert_called_once()

    def test_replay_unknown_action_no_error(self, controller, mock_pyautogui):
        """Unknown action types should be logged but not raise."""
        actions = [
            {
                "type": "unknown_action",
                "timestamp": 1000.0,
                "position": (0, 0),
            }
        ]
        # Should not raise
        controller.replay_actions(actions)

    def test_replay_speed_multiplier(self, controller, mock_pyautogui):
        """Speed multiplier should reduce sleep time between actions."""
        actions = [
            {
                "type": "click",
                "timestamp": 1000.0,
                "position": (100, 200),
                "button": "left",
                "x": None,
                "y": None,
            },
            {
                "type": "click",
                "timestamp": 1002.0,  # 2s later
                "position": (100, 200),
                "button": "left",
                "x": None,
                "y": None,
            },
        ]
        with patch("src.core.mouse_controller.time") as mock_time:
            mock_time.time.return_value = 1000
            mock_time.sleep = MagicMock()
            controller.replay_actions(actions, speed=2.0)

            # 2s delta / 2.0 speed = 1.0s sleep
            mock_time.sleep.assert_called_with(1.0)

    def test_replay_action_error_continues(self, controller, mock_pyautogui):
        """If one action fails, replay should continue to the next."""
        mock_pyautogui.click.side_effect = [RuntimeError("fail"), None]
        actions = [
            {
                "type": "click",
                "timestamp": 1000.0,
                "position": (100, 200),
                "button": "left",
                "x": None,
                "y": None,
            },
            {
                "type": "press_key",
                "timestamp": 1000.1,
                "position": (100, 200),
                "key": "enter",
            },
        ]
        with patch("src.core.mouse_controller.time") as mock_time:
            mock_time.time.return_value = 1000
            mock_time.sleep = MagicMock()
            # Should NOT raise despite the first action failing
            controller.replay_actions(actions)

        # Second action should still have been attempted
        mock_pyautogui.press.assert_called_once_with("enter")


# ======================================================================
# Status
# ======================================================================


class TestStatus:
    """Test get_status."""

    def test_status_keys(self, controller):
        status = controller.get_status()
        expected_keys = {
            "position",
            "screen_size",
            "dragging",
            "recording",
            "recorded_actions",
            "move_duration",
            "click_count",
            "key_count",
            "move_count",
            "failsafe",
        }
        assert set(status.keys()) == expected_keys

    def test_status_initial_values(self, controller):
        status = controller.get_status()
        assert status["position"] == (500, 300)
        assert status["screen_size"] == (1920, 1080)
        assert status["dragging"] is False
        assert status["recording"] is False
        assert status["recorded_actions"] == 0
        assert status["click_count"] == 0
        assert status["key_count"] == 0
        assert status["move_count"] == 0
        assert status["failsafe"] is True

    def test_status_after_actions(self, controller, mock_pyautogui):
        controller.click()
        controller.click()
        controller.move_to(100, 200)
        controller.press_key("a")

        status = controller.get_status()
        assert status["click_count"] == 2
        assert status["move_count"] == 1
        assert status["key_count"] == 1

    def test_status_recording(self, controller, mock_pyautogui):
        controller.start_recording()
        controller.click()
        status = controller.get_status()
        assert status["recording"] is True
        assert status["recorded_actions"] == 1

    def test_status_dragging(self, controller, mock_pyautogui):
        controller.start_drag()
        status = controller.get_status()
        assert status["dragging"] is True


# ======================================================================
# Configuration
# ======================================================================


class TestConfiguration:
    """Test configuration from config manager and setters."""

    def test_default_move_duration(self, controller):
        assert controller._move_duration == 0.1

    def test_default_type_interval(self, controller):
        assert controller._type_interval == 0.02

    def test_default_failsafe(self, controller):
        assert controller._failsafe is True

    def test_default_pause(self, controller):
        assert controller._pause == 0.01

    def test_move_duration_affects_move(self, controller, mock_pyautogui):
        controller.set_move_duration(0.5)
        controller.move_to(100, 200)
        mock_pyautogui.moveTo.assert_called_once_with(100, 200, duration=0.5)


# ======================================================================
# Thread Safety
# ======================================================================


class TestThreadSafety:
    """Test that position updates are thread-safe."""

    def test_concurrent_move_to(self, controller, mock_pyautogui):
        """Multiple threads updating position should not corrupt data."""
        import threading

        errors = []

        def move_worker(x, y):
            try:
                controller.move_to(x, y)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=move_worker, args=(i * 10, i * 20))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # Position should be one of the valid values
        x, y = controller.current_position
        assert 0 <= x <= 1919
        assert 0 <= y <= 1079

    def test_concurrent_click_count(self, controller, mock_pyautogui):
        """Click count should be consistent even with concurrent clicks."""
        import threading

        def click_worker():
            for _ in range(10):
                controller.click()

        threads = [threading.Thread(target=click_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert controller._click_count == 50


# ======================================================================
# Edge Cases
# ======================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_move_to_zero_zero(self, controller, mock_pyautogui):
        controller.move_to(0, 0)
        mock_pyautogui.moveTo.assert_called_once_with(0, 0, duration=0.1)

    def test_move_to_max_screen(self, controller, mock_pyautogui):
        controller.move_to(1919, 1079)
        mock_pyautogui.moveTo.assert_called_once_with(1919, 1079, duration=0.1)

    def test_type_empty_string(self, controller, mock_pyautogui):
        controller.type_text("")
        mock_pyautogui.write.assert_called_once_with("", interval=0.02)

    def test_hotkey_single_key(self, controller, mock_pyautogui):
        controller.hotkey("escape")
        mock_pyautogui.hotkey.assert_called_once_with("escape")

    def test_press_keys_sequence_empty(self, controller, mock_pyautogui):
        controller.press_keys_sequence([])
        mock_pyautogui.press.assert_not_called()

    def test_scroll_zero(self, controller, mock_pyautogui):
        controller.scroll(0)
        mock_pyautogui.scroll.assert_called_once_with(0)

    def test_drag_to_same_position(self, controller, mock_pyautogui):
        controller.current_position = (500, 300)
        controller.drag_to(500, 300)
        mock_pyautogui.drag.assert_called_once_with(0, 0, duration=0.5)

    def test_click_only_x_no_y(self, controller, mock_pyautogui):
        """If only x is provided (no y), should click at current position."""
        controller.click(x=100)
        # x=100 but y=None, so no x/y in kwargs
        mock_pyautogui.click.assert_called_once_with(button="left")

    def test_click_only_y_no_x(self, controller, mock_pyautogui):
        """If only y is provided (no x), should click at current position."""
        controller.click(y=200)
        mock_pyautogui.click.assert_called_once_with(button="left")

    def test_set_screen_size_then_clamp(self, controller, mock_pyautogui):
        """After setting a smaller screen, moves should clamp properly."""
        controller.set_screen_size(800, 600)
        controller.move_to(1000, 700)
        mock_pyautogui.moveTo.assert_called_once_with(799, 599, duration=0.1)


__all__ = []
