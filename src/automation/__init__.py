"""
Automation modules for the Accessibility Automation Agent.

Provides browser automation (Selenium), application launching,
and macro recording/playback. Implemented in Phases 6-8.

Modules:
    - browser_controller: Selenium-based browser automation with voice commands.
    - (Phase 7) app_launcher: Application discovery and launching.
    - (Phase 8) macro_system: Macro recording and playback.
"""

from .browser_controller import BrowserController

__all__ = ["BrowserController"]
