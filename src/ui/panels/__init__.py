"""
UI Panel widgets for the Accessibility Automation Agent.

Individual panels for voice control, eye tracking, mouse control,
browser automation, macro system, app launcher, and settings.
Implemented in Phase 9.
"""

from .base_panel import BasePanel
from .voice_panel import VoiceControlPanel
from .eye_tracking_panel import EyeTrackingPanel
from .mouse_panel import MouseControlPanel
from .browser_panel import BrowserAutomationPanel
from .macro_panel import MacroSystemPanel
from .app_launcher_panel import AppLauncherPanel
from .settings_panel import SettingsPanel

__all__ = [
    "BasePanel",
    "VoiceControlPanel",
    "EyeTrackingPanel",
    "MouseControlPanel",
    "BrowserAutomationPanel",
    "MacroSystemPanel",
    "AppLauncherPanel",
    "SettingsPanel",
]
