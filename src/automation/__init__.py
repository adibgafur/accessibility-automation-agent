"""
Automation modules for the Accessibility Automation Agent.

Provides browser automation (Selenium), application launching,
and macro recording/playback. Implemented in Phases 6-8.

Modules:
    - browser_controller: Selenium-based browser automation with voice commands.
    - app_launcher: Windows app discovery and launching with voice commands.
    - (Phase 8) macro_system: Macro recording and playback.
"""

from .browser_controller import BrowserController
from .app_launcher import AppLauncher

__all__ = ["BrowserController", "AppLauncher"]
