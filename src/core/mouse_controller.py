"""
Mouse & Keyboard Input Controller.

Wraps pyautogui to provide:
    - Smooth cursor movement (for nose-tracking integration)
    - Click / double-click / right-click
    - Text typing and special key presses
    - Clipboard operations (copy, paste, select-all)
    - Input safety (fail-safe, boundaries)

This module will be fully implemented in Phase 5.
Current state: interface stubs with logging.
"""

from typing import Dict, Optional, Tuple

from loguru import logger

from ..utils.config_manager import config
from ..utils.error_handler import AutomationError


class MouseController:
    """
    High-level mouse and keyboard controller built on pyautogui.

    Designed to be driven by the EyeTracker (nose position -> cursor)
    and VoiceEngine (voice commands -> keystrokes).

    Usage (Phase 5+):
        ctrl = MouseController()
        ctrl.move_to(500, 300)
        ctrl.click()
        ctrl.type_text("Hello world")
        ctrl.hotkey("ctrl", "c")
    """

    def __init__(self) -> None:
        self.current_position: Tuple[int, int] = (0, 0)
        self._screen_width: int = 1920
        self._screen_height: int = 1080
        self._move_duration: float = 0.15  # seconds for smooth moves

        # Safety: pyautogui fail-safe (move mouse to corner to abort)
        # TODO: Phase 5 - pyautogui.FAILSAFE = True

        logger.info("MouseController created")

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
            # Clamp to screen boundaries
            x = max(0, min(x, self._screen_width - 1))
            y = max(0, min(y, self._screen_height - 1))

            # TODO: Phase 5
            # import pyautogui
            # duration = self._move_duration if smooth else 0
            # pyautogui.moveTo(x, y, duration=duration)

            self.current_position = (x, y)
            logger.debug(f"Mouse moved to ({x}, {y})")
        except Exception as exc:
            raise AutomationError(f"Failed to move mouse: {exc}")

    def move_relative(self, dx: int, dy: int) -> None:
        """Move cursor relative to its current position."""
        new_x = self.current_position[0] + dx
        new_y = self.current_position[1] + dy
        self.move_to(new_x, new_y)

    # ------------------------------------------------------------------
    # Clicking
    # ------------------------------------------------------------------

    def click(self, button: str = "left") -> None:
        """
        Click a mouse button at the current position.

        Args:
            button: ``"left"``, ``"right"``, or ``"middle"``.
        """
        try:
            # TODO: Phase 5
            # import pyautogui
            # pyautogui.click(button=button)
            logger.debug(f"{button.capitalize()} click at {self.current_position}")
        except Exception as exc:
            raise AutomationError(f"Click failed: {exc}")

    def double_click(self) -> None:
        """Double-click at the current position."""
        try:
            # TODO: Phase 5
            # import pyautogui
            # pyautogui.doubleClick()
            logger.debug(f"Double-click at {self.current_position}")
        except Exception as exc:
            raise AutomationError(f"Double-click failed: {exc}")

    def right_click(self) -> None:
        """Right-click at the current position."""
        self.click(button="right")

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def type_text(self, text: str, interval: float = 0.02) -> None:
        """
        Type a string of text character by character.

        Args:
            text:     Text to type.
            interval: Delay between keystrokes (seconds).
        """
        try:
            # TODO: Phase 5
            # import pyautogui
            # pyautogui.typewrite(text, interval=interval)
            logger.debug(f"Typed text: {text[:50]}{'...' if len(text) > 50 else ''}")
        except Exception as exc:
            raise AutomationError(f"Type text failed: {exc}")

    def press_key(self, key: str) -> None:
        """
        Press and release a single key.

        Args:
            key: Key name (e.g., ``"enter"``, ``"tab"``, ``"escape"``).
        """
        try:
            # TODO: Phase 5
            # import pyautogui
            # pyautogui.press(key)
            logger.debug(f"Key pressed: {key}")
        except Exception as exc:
            raise AutomationError(f"Key press failed: {exc}")

    def hotkey(self, *keys: str) -> None:
        """
        Press a key combination (e.g., Ctrl+C).

        Args:
            keys: One or more key names (e.g., ``"ctrl"``, ``"c"``).
        """
        try:
            # TODO: Phase 5
            # import pyautogui
            # pyautogui.hotkey(*keys)
            combo = "+".join(keys)
            logger.debug(f"Hotkey pressed: {combo}")
        except Exception as exc:
            raise AutomationError(f"Hotkey failed: {exc}")

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
            # TODO: Phase 5
            # import pyautogui
            # pyautogui.scroll(clicks)
            direction = "up" if clicks > 0 else "down"
            logger.debug(f"Scrolled {direction} by {abs(clicks)} clicks")
        except Exception as exc:
            raise AutomationError(f"Scroll failed: {exc}")

    # ------------------------------------------------------------------
    # Screen info
    # ------------------------------------------------------------------

    def set_screen_size(self, width: int, height: int) -> None:
        """Update the known screen dimensions."""
        self._screen_width = width
        self._screen_height = height
        logger.info(f"Screen size set to {width}x{height}")

    def get_position(self) -> Tuple[int, int]:
        """Return the current cursor position."""
        # TODO: Phase 5
        # import pyautogui
        # return pyautogui.position()
        return self.current_position

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict:
        """Return status dict for the UI panel."""
        return {
            "position": self.current_position,
            "screen_size": (self._screen_width, self._screen_height),
        }


__all__ = ["MouseController"]
