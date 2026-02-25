"""
Mouse & Keyboard Input Controller.

Wraps pyautogui to provide:
    - Smooth cursor movement (for nose-tracking integration)
    - Click / double-click / right-click / middle-click
    - Drag and drop (for long-blink integration)
    - Text typing and special key presses
    - Hotkey combos (Ctrl+C, Alt+Tab, etc.)
    - Clipboard operations (copy, paste, select-all)
    - Mouse scrolling
    - Input safety (fail-safe, screen boundary clamping)
    - Mouse position tracking (real pyautogui.position())
    - Integration hooks for EyeTracker blink events

Dependencies:
    - pyautogui (mouse/keyboard automation)
    - pyperclip (clipboard access, optional)

Optimised for accessibility:
    - Configurable move duration for smooth tracking
    - Fail-safe enabled by default (corner escape)
    - All actions logged for debugging
    - Thread-safe position updates
"""

import threading
import time
from typing import Dict, List, Optional, Tuple

from loguru import logger

from ..utils.config_manager import config
from ..utils.error_handler import AutomationError


class MouseController:
    """
    High-level mouse and keyboard controller built on pyautogui.

    Designed to be driven by the EyeTracker (nose position → cursor)
    and VoiceEngine (voice commands → keystrokes / mouse actions).

    Usage:
        ctrl = MouseController()
        ctrl.move_to(500, 300)
        ctrl.click()
        ctrl.type_text("Hello world")
        ctrl.hotkey("ctrl", "c")

    Integration with EyeTracker:
        tracker.on_blink(ctrl.click)
        tracker.on_double_blink(ctrl.right_click)
        tracker.on_long_blink(lambda: ctrl.start_drag())
        tracker.on_position_update(ctrl.move_to)
    """

    def __init__(self) -> None:
        # Lazy-loaded
        self._pyautogui = None

        # Position tracking
        self.current_position: Tuple[int, int] = (0, 0)
        self._screen_width: int = 1920
        self._screen_height: int = 1080

        # Movement settings
        self._move_duration: float = config.get(
            "mouse.move_duration", 0.1
        )
        self._smooth_tween: str = config.get(
            "mouse.smooth_tween", "easeOutQuad"
        )
        self._type_interval: float = config.get(
            "mouse.type_interval", 0.02
        )

        # Safety
        self._failsafe: bool = config.get("mouse.failsafe", True)
        self._pause: float = config.get("mouse.pause", 0.01)

        # Drag state
        self._dragging: bool = False
        self._drag_start: Optional[Tuple[int, int]] = None

        # Threading
        self._lock = threading.Lock()

        # Action history (for macro recording)
        self._action_history: List[Dict] = []
        self._record_actions: bool = False

        # Stats
        self._click_count: int = 0
        self._key_count: int = 0
        self._move_count: int = 0

        logger.info(
            f"MouseController created | duration={self._move_duration} | "
            f"failsafe={self._failsafe}"
        )

    # ------------------------------------------------------------------
    # Lazy import
    # ------------------------------------------------------------------

    def _ensure_pyautogui(self) -> None:
        """Lazy-import pyautogui and configure it."""
        if self._pyautogui is not None:
            return

        try:
            import pyautogui
            self._pyautogui = pyautogui

            # Configure safety
            pyautogui.FAILSAFE = self._failsafe
            pyautogui.PAUSE = self._pause

            # Detect actual screen size
            size = pyautogui.size()
            self._screen_width = size.width
            self._screen_height = size.height

            # Get initial position
            pos = pyautogui.position()
            self.current_position = (pos.x, pos.y)

            logger.info(
                f"pyautogui loaded | screen={self._screen_width}x"
                f"{self._screen_height} | pos={self.current_position}"
            )
        except ImportError as exc:
            raise AutomationError(
                f"pyautogui not installed: {exc}. Run: pip install pyautogui"
            )

    # ------------------------------------------------------------------
    # Mouse movement
    # ------------------------------------------------------------------

    def move_to(self, x: int, y: int, smooth: bool = True) -> None:
        """
        Move cursor to an absolute screen position.

        Args:
            x:      Target X coordinate.
            y:      Target Y coordinate.
            smooth: Use eased movement (True) or instant jump (False).

        Raises:
            AutomationError: If the move fails.
        """
        try:
            self._ensure_pyautogui()

            # Clamp to screen boundaries
            x = max(0, min(x, self._screen_width - 1))
            y = max(0, min(y, self._screen_height - 1))

            duration = self._move_duration if smooth else 0

            self._pyautogui.moveTo(x, y, duration=duration)

            with self._lock:
                self.current_position = (x, y)
                self._move_count += 1

            self._record_action("move_to", x=x, y=y, smooth=smooth)

        except AutomationError:
            raise
        except Exception as exc:
            raise AutomationError(f"Failed to move mouse: {exc}")

    def move_relative(self, dx: int, dy: int, smooth: bool = True) -> None:
        """
        Move cursor relative to its current position.

        Args:
            dx: Horizontal offset (positive = right).
            dy: Vertical offset (positive = down).
            smooth: Use eased movement.
        """
        try:
            self._ensure_pyautogui()

            duration = self._move_duration if smooth else 0
            self._pyautogui.moveRel(dx, dy, duration=duration)

            pos = self._pyautogui.position()
            with self._lock:
                self.current_position = (pos.x, pos.y)
                self._move_count += 1

            self._record_action("move_relative", dx=dx, dy=dy)

        except Exception as exc:
            raise AutomationError(f"Relative move failed: {exc}")

    # ------------------------------------------------------------------
    # Clicking
    # ------------------------------------------------------------------

    def click(self, button: str = "left", x: Optional[int] = None,
              y: Optional[int] = None) -> None:
        """
        Click a mouse button.

        Args:
            button: ``"left"``, ``"right"``, or ``"middle"``.
            x: Optional x coordinate (clicks at current pos if None).
            y: Optional y coordinate.
        """
        try:
            self._ensure_pyautogui()

            kwargs = {"button": button}
            if x is not None and y is not None:
                kwargs["x"] = x
                kwargs["y"] = y

            self._pyautogui.click(**kwargs)

            with self._lock:
                self._click_count += 1
                if x is not None and y is not None:
                    self.current_position = (x, y)

            logger.debug(
                f"{button.capitalize()} click at "
                f"{(x, y) if x is not None else self.current_position}"
            )
            self._record_action("click", button=button, x=x, y=y)

        except Exception as exc:
            raise AutomationError(f"Click failed: {exc}")

    def double_click(self, x: Optional[int] = None,
                     y: Optional[int] = None) -> None:
        """Double-click at the current or specified position."""
        try:
            self._ensure_pyautogui()

            kwargs = {}
            if x is not None and y is not None:
                kwargs["x"] = x
                kwargs["y"] = y

            self._pyautogui.doubleClick(**kwargs)

            with self._lock:
                self._click_count += 1

            logger.debug(f"Double-click at {(x, y) or self.current_position}")
            self._record_action("double_click", x=x, y=y)

        except Exception as exc:
            raise AutomationError(f"Double-click failed: {exc}")

    def right_click(self, x: Optional[int] = None,
                    y: Optional[int] = None) -> None:
        """Right-click at the current or specified position."""
        self.click(button="right", x=x, y=y)

    def middle_click(self, x: Optional[int] = None,
                     y: Optional[int] = None) -> None:
        """Middle-click at the current or specified position."""
        self.click(button="middle", x=x, y=y)

    def triple_click(self, x: Optional[int] = None,
                     y: Optional[int] = None) -> None:
        """Triple-click (select line/paragraph)."""
        try:
            self._ensure_pyautogui()

            kwargs = {"clicks": 3}
            if x is not None and y is not None:
                kwargs["x"] = x
                kwargs["y"] = y

            self._pyautogui.click(**kwargs)

            logger.debug(f"Triple-click at {(x, y) or self.current_position}")
            self._record_action("triple_click", x=x, y=y)

        except Exception as exc:
            raise AutomationError(f"Triple-click failed: {exc}")

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------

    def start_drag(self) -> None:
        """
        Start a drag operation (mouse down) at the current position.

        Triggered by long blink from EyeTracker.
        """
        try:
            self._ensure_pyautogui()

            self._pyautogui.mouseDown()
            self._dragging = True
            self._drag_start = self.current_position

            logger.debug(f"Drag started at {self.current_position}")
            self._record_action("start_drag")

        except Exception as exc:
            raise AutomationError(f"Start drag failed: {exc}")

    def end_drag(self) -> None:
        """
        End a drag operation (mouse up) at the current position.
        """
        try:
            self._ensure_pyautogui()

            self._pyautogui.mouseUp()
            self._dragging = False

            logger.debug(
                f"Drag ended at {self.current_position} "
                f"(started at {self._drag_start})"
            )
            self._record_action("end_drag")
            self._drag_start = None

        except Exception as exc:
            raise AutomationError(f"End drag failed: {exc}")

    def drag_to(self, x: int, y: int, duration: float = 0.5) -> None:
        """
        Drag from current position to target position.

        Args:
            x: Target X.
            y: Target Y.
            duration: Duration of the drag movement.
        """
        try:
            self._ensure_pyautogui()

            self._pyautogui.drag(
                x - self.current_position[0],
                y - self.current_position[1],
                duration=duration,
            )

            with self._lock:
                self.current_position = (x, y)

            logger.debug(f"Dragged to ({x}, {y})")
            self._record_action("drag_to", x=x, y=y)

        except Exception as exc:
            raise AutomationError(f"Drag failed: {exc}")

    @property
    def is_dragging(self) -> bool:
        """Check if a drag operation is in progress."""
        return self._dragging

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def type_text(self, text: str, interval: float = 0.0) -> None:
        """
        Type a string of text character by character.

        Uses pyautogui.write() which handles special characters.
        For Unicode text (Bengali, etc.), uses pyperclip + paste.

        Args:
            text:     Text to type.
            interval: Delay between keystrokes (seconds). 0 = use default.
        """
        try:
            self._ensure_pyautogui()

            if interval <= 0:
                interval = self._type_interval

            # Check for non-ASCII characters (Bengali, etc.)
            if all(ord(c) < 128 for c in text):
                self._pyautogui.write(text, interval=interval)
            else:
                # Use clipboard for Unicode
                self._type_unicode(text)

            with self._lock:
                self._key_count += len(text)

            logger.debug(
                f"Typed text: {text[:50]}{'...' if len(text) > 50 else ''}"
            )
            self._record_action("type_text", text=text)

        except Exception as exc:
            raise AutomationError(f"Type text failed: {exc}")

    def _type_unicode(self, text: str) -> None:
        """
        Type Unicode text by pasting from clipboard.

        Saves and restores the original clipboard content.
        """
        try:
            import pyperclip

            # Save original clipboard
            try:
                original = pyperclip.paste()
            except Exception:
                original = ""

            # Set text and paste
            pyperclip.copy(text)
            self._pyautogui.hotkey("ctrl", "v")

            # Small delay to let paste complete
            time.sleep(0.1)

            # Restore original clipboard
            try:
                pyperclip.copy(original)
            except Exception:
                pass

        except ImportError:
            # Fallback: type character by character using pyautogui
            logger.warning(
                "pyperclip not available, Unicode typing may not work"
            )
            for char in text:
                self._pyautogui.press(char)

    def press_key(self, key: str) -> None:
        """
        Press and release a single key.

        Args:
            key: Key name (e.g., ``"enter"``, ``"tab"``, ``"escape"``,
                 ``"space"``, ``"backspace"``, ``"delete"``).
        """
        try:
            self._ensure_pyautogui()

            self._pyautogui.press(key)

            with self._lock:
                self._key_count += 1

            logger.debug(f"Key pressed: {key}")
            self._record_action("press_key", key=key)

        except Exception as exc:
            raise AutomationError(f"Key press failed: {exc}")

    def key_down(self, key: str) -> None:
        """Hold a key down (for modifiers)."""
        try:
            self._ensure_pyautogui()
            self._pyautogui.keyDown(key)
            logger.debug(f"Key down: {key}")
        except Exception as exc:
            raise AutomationError(f"Key down failed: {exc}")

    def key_up(self, key: str) -> None:
        """Release a held key."""
        try:
            self._ensure_pyautogui()
            self._pyautogui.keyUp(key)
            logger.debug(f"Key up: {key}")
        except Exception as exc:
            raise AutomationError(f"Key up failed: {exc}")

    def hotkey(self, *keys: str) -> None:
        """
        Press a key combination (e.g., Ctrl+C).

        Args:
            keys: One or more key names (e.g., ``"ctrl"``, ``"c"``).
        """
        try:
            self._ensure_pyautogui()

            self._pyautogui.hotkey(*keys)

            combo = "+".join(keys)
            with self._lock:
                self._key_count += 1

            logger.debug(f"Hotkey pressed: {combo}")
            self._record_action("hotkey", keys=list(keys))

        except Exception as exc:
            raise AutomationError(f"Hotkey failed: {exc}")

    def press_keys_sequence(self, keys: List[str], interval: float = 0.05) -> None:
        """
        Press a sequence of keys with a delay between each.

        Args:
            keys: List of key names to press in order.
            interval: Delay between key presses.
        """
        for key in keys:
            self.press_key(key)
            if interval > 0:
                time.sleep(interval)

    # ------------------------------------------------------------------
    # Clipboard shortcuts
    # ------------------------------------------------------------------

    def copy(self) -> None:
        """Send Ctrl+C (copy to clipboard)."""
        self.hotkey("ctrl", "c")

    def paste(self) -> None:
        """Send Ctrl+V (paste from clipboard)."""
        self.hotkey("ctrl", "v")

    def cut(self) -> None:
        """Send Ctrl+X (cut to clipboard)."""
        self.hotkey("ctrl", "x")

    def select_all(self) -> None:
        """Send Ctrl+A (select all)."""
        self.hotkey("ctrl", "a")

    def undo(self) -> None:
        """Send Ctrl+Z (undo)."""
        self.hotkey("ctrl", "z")

    def redo(self) -> None:
        """Send Ctrl+Y (redo)."""
        self.hotkey("ctrl", "y")

    def save(self) -> None:
        """Send Ctrl+S (save)."""
        self.hotkey("ctrl", "s")

    def find(self) -> None:
        """Send Ctrl+F (find)."""
        self.hotkey("ctrl", "f")

    def close_tab(self) -> None:
        """Send Ctrl+W (close tab)."""
        self.hotkey("ctrl", "w")

    def new_tab(self) -> None:
        """Send Ctrl+T (new tab)."""
        self.hotkey("ctrl", "t")

    def switch_window(self) -> None:
        """Send Alt+Tab (switch window)."""
        self.hotkey("alt", "tab")

    def minimize_window(self) -> None:
        """Send Win+D (show desktop / minimize all)."""
        self.hotkey("win", "d")

    def screenshot_key(self) -> None:
        """Send Win+Shift+S (Windows screenshot tool)."""
        self.hotkey("win", "shift", "s")

    def task_manager(self) -> None:
        """Send Ctrl+Shift+Esc (task manager)."""
        self.hotkey("ctrl", "shift", "escape")

    # ------------------------------------------------------------------
    # Scrolling
    # ------------------------------------------------------------------

    def scroll(self, clicks: int = 3) -> None:
        """
        Scroll the mouse wheel.

        Args:
            clicks: Positive = scroll up, negative = scroll down.
        """
        try:
            self._ensure_pyautogui()

            self._pyautogui.scroll(clicks)

            direction = "up" if clicks > 0 else "down"
            logger.debug(f"Scrolled {direction} by {abs(clicks)} clicks")
            self._record_action("scroll", clicks=clicks)

        except Exception as exc:
            raise AutomationError(f"Scroll failed: {exc}")

    def scroll_horizontal(self, clicks: int = 3) -> None:
        """
        Scroll horizontally.

        Args:
            clicks: Positive = scroll right, negative = scroll left.
        """
        try:
            self._ensure_pyautogui()

            self._pyautogui.hscroll(clicks)

            direction = "right" if clicks > 0 else "left"
            logger.debug(f"H-scrolled {direction} by {abs(clicks)}")
            self._record_action("scroll_horizontal", clicks=clicks)

        except Exception as exc:
            raise AutomationError(f"Horizontal scroll failed: {exc}")

    # ------------------------------------------------------------------
    # Screen info & position
    # ------------------------------------------------------------------

    def get_position(self) -> Tuple[int, int]:
        """Return the actual current cursor position from pyautogui."""
        try:
            self._ensure_pyautogui()
            pos = self._pyautogui.position()
            self.current_position = (pos.x, pos.y)
            return self.current_position
        except Exception:
            return self.current_position

    def get_screen_size(self) -> Tuple[int, int]:
        """Return the screen dimensions."""
        return (self._screen_width, self._screen_height)

    def set_screen_size(self, width: int, height: int) -> None:
        """Update the known screen dimensions."""
        self._screen_width = width
        self._screen_height = height
        logger.info(f"Screen size set to {width}x{height}")

    def set_move_duration(self, duration: float) -> None:
        """
        Set the cursor movement duration.

        Args:
            duration: Seconds for smooth movement (0 = instant).
        """
        self._move_duration = max(0.0, min(2.0, duration))
        logger.info(f"Move duration set to {self._move_duration}s")

    def set_type_interval(self, interval: float) -> None:
        """
        Set the typing interval between keystrokes.

        Args:
            interval: Seconds between each keystroke.
        """
        self._type_interval = max(0.0, min(1.0, interval))

    # ------------------------------------------------------------------
    # Action recording (for macro system)
    # ------------------------------------------------------------------

    def start_recording(self) -> None:
        """Start recording actions for macro playback."""
        self._record_actions = True
        self._action_history.clear()
        logger.info("Action recording started")

    def stop_recording(self) -> List[Dict]:
        """
        Stop recording and return the recorded actions.

        Returns:
            List of action dicts with timestamps.
        """
        self._record_actions = False
        actions = list(self._action_history)
        logger.info(f"Action recording stopped: {len(actions)} actions")
        return actions

    def get_recorded_actions(self) -> List[Dict]:
        """Return the current recorded actions without stopping."""
        return list(self._action_history)

    def _record_action(self, action_type: str, **kwargs) -> None:
        """Record an action if recording is enabled."""
        if not self._record_actions:
            return

        self._action_history.append({
            "type": action_type,
            "timestamp": time.time(),
            "position": self.current_position,
            **kwargs,
        })

    def replay_actions(
        self,
        actions: List[Dict],
        speed: float = 1.0,
    ) -> None:
        """
        Replay a list of recorded actions.

        Args:
            actions: List of action dicts from stop_recording().
            speed: Playback speed multiplier (2.0 = 2x speed).
        """
        if not actions:
            return

        logger.info(f"Replaying {len(actions)} actions at {speed}x speed")

        prev_time = actions[0]["timestamp"]

        for action in actions:
            # Wait for the appropriate time delta
            delta = (action["timestamp"] - prev_time) / speed
            if delta > 0:
                time.sleep(delta)

            self._execute_action(action)
            prev_time = action["timestamp"]

        logger.info("Action replay complete")

    def _execute_action(self, action: Dict) -> None:
        """Execute a single recorded action."""
        action_type = action["type"]

        try:
            if action_type == "move_to":
                self.move_to(action["x"], action["y"],
                             smooth=action.get("smooth", True))
            elif action_type == "click":
                self.click(
                    button=action.get("button", "left"),
                    x=action.get("x"),
                    y=action.get("y"),
                )
            elif action_type == "double_click":
                self.double_click(x=action.get("x"), y=action.get("y"))
            elif action_type == "triple_click":
                self.triple_click(x=action.get("x"), y=action.get("y"))
            elif action_type == "type_text":
                self.type_text(action.get("text", ""))
            elif action_type == "press_key":
                self.press_key(action.get("key", ""))
            elif action_type == "hotkey":
                self.hotkey(*action.get("keys", []))
            elif action_type == "scroll":
                self.scroll(action.get("clicks", 3))
            elif action_type == "start_drag":
                self.start_drag()
            elif action_type == "end_drag":
                self.end_drag()
            elif action_type == "drag_to":
                self.drag_to(action["x"], action["y"])
            else:
                logger.warning(f"Unknown action type: {action_type}")
        except Exception as exc:
            logger.error(f"Error replaying action {action_type}: {exc}")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict:
        """Return status dict for the UI panel."""
        return {
            "position": self.current_position,
            "screen_size": (self._screen_width, self._screen_height),
            "dragging": self._dragging,
            "recording": self._record_actions,
            "recorded_actions": len(self._action_history),
            "move_duration": self._move_duration,
            "click_count": self._click_count,
            "key_count": self._key_count,
            "move_count": self._move_count,
            "failsafe": self._failsafe,
        }


__all__ = ["MouseController"]
