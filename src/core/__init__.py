"""
Core engine modules for the Accessibility Automation Agent.

Provides voice recognition, eye tracking, and mouse/keyboard control.
"""

from .voice_engine import VoiceEngine
from .eye_tracker import EyeTracker
from .mouse_controller import MouseController

__all__ = [
    "VoiceEngine",
    "EyeTracker",
    "MouseController",
]
