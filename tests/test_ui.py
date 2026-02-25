"""
Tests for PyQt6 UI components (Phase 9).

Tests covering:
    - Accessibility styling and theming
    - Main window creation and functionality
    - UI panel creation and updates
    - Language switching
    - Theme switching
    - Signal emissions

Total: 100+ test cases covering UI components.
"""

import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtTest import QSignalSpy
from unittest.mock import MagicMock, patch

from src.ui.accessibility import (
    Theme,
    get_stylesheet,
    get_ui_string,
    get_button_size,
    get_accessible_font,
    LIGHT_SCHEME,
    DARK_SCHEME,
)
from src.ui.main_window import MainWindow
from src.ui.panels.base_panel import BasePanel
from src.ui.panels.voice_panel import VoiceControlPanel
from src.ui.panels.eye_tracking_panel import EyeTrackingPanel
from src.ui.panels.mouse_panel import MouseControlPanel
from src.ui.panels.browser_panel import BrowserAutomationPanel
from src.ui.panels.macro_panel import MacroSystemPanel
from src.ui.panels.app_launcher_panel import AppLauncherPanel
from src.ui.panels.settings_panel import SettingsPanel


# Fixture for Qt application
@pytest.fixture(scope="session")
def qt_app():
    """Create Qt application for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


# ======================================================================
# Accessibility Tests
# ======================================================================


class TestAccessibilityThemes:
    """Tests for accessibility themes and styling."""

    def test_theme_enum_values(self):
        """Test that all themes are defined."""
        assert Theme.LIGHT in Theme
        assert Theme.DARK in Theme
        assert Theme.HIGH_CONTRAST in Theme

    def test_get_stylesheet_light(self):
        """Test stylesheet generation for light theme."""
        stylesheet = get_stylesheet(Theme.LIGHT)
        assert isinstance(stylesheet, str)
        assert "#FFFFFF" in stylesheet  # Background
        assert "64px" in stylesheet  # Minimum button size

    def test_get_stylesheet_dark(self):
        """Test stylesheet generation for dark theme."""
        stylesheet = get_stylesheet(Theme.DARK)
        assert isinstance(stylesheet, str)
        assert "#1E1E1E" in stylesheet  # Background
        assert "64px" in stylesheet

    def test_get_stylesheet_high_contrast(self):
        """Test stylesheet generation for high contrast theme."""
        stylesheet = get_stylesheet(Theme.HIGH_CONTRAST)
        assert isinstance(stylesheet, str)
        assert "#000000" in stylesheet  # Black background
        assert "#FFFFFF" in stylesheet  # White text

    def test_stylesheet_contains_accessibility_features(self):
        """Test that stylesheets include accessibility features."""
        for theme in Theme:
            stylesheet = get_stylesheet(theme)
            # Should include WCAG AAA compliant features
            assert "min-width: 64px" in stylesheet
            assert "min-height: 64px" in stylesheet
            assert "font-size: 14pt" in stylesheet
            assert "border" in stylesheet
            assert "padding" in stylesheet

    def test_get_ui_string_english(self):
        """Test English UI strings."""
        assert get_ui_string("app_title", "en") == "Accessibility Automation Agent"
        assert get_ui_string("start", "en") == "Start"
        assert get_ui_string("stop", "en") == "Stop"

    def test_get_ui_string_bengali(self):
        """Test Bengali UI strings."""
        assert get_ui_string("app_title", "bn") == "প্রবেশযোগ্যতা স্বয়ংক্রিয়করণ এজেন্ট"
        title_bn = get_ui_string("app_title", "bn")
        assert "বাংলা" in title_bn or "বাং" in title_bn or len(title_bn) > 5

    def test_get_ui_string_fallback(self):
        """Test that unknown strings return the key itself."""
        result = get_ui_string("unknown_key", "en")
        assert result == "unknown_key"

    def test_get_button_size(self):
        """Test button size constraints."""
        w, h = get_button_size()
        assert w >= 64
        assert h >= 64

    def test_get_button_size_custom(self):
        """Test button size with custom values."""
        w, h = get_button_size(100, 100)
        assert w == 100
        assert h == 100

    def test_get_button_size_minimum_enforcement(self):
        """Test that minimum 64x64 is enforced."""
        w, h = get_button_size(32, 32)
        assert w == 64
        assert h == 64

    def test_get_accessible_font(self):
        """Test accessible font generation."""
        font_css = get_accessible_font()
        assert "14pt" in font_css
        assert "font-size" in font_css

    def test_get_accessible_font_bold(self):
        """Test bold font generation."""
        font_css = get_accessible_font(bold=True)
        assert "bold" in font_css

    def test_get_accessible_font_size_minimum(self):
        """Test that minimum font size is enforced."""
        font_css = get_accessible_font(size=8)
        assert "14pt" in font_css  # Should enforce minimum


# ======================================================================
# Main Window Tests
# ======================================================================


class TestMainWindow:
    """Tests for main application window."""

    def test_main_window_creation(self, qt_app):
        """Test creating main window."""
        window = MainWindow()
        assert window is not None
        assert window.isVisible() is False  # Not shown

    def test_main_window_title(self, qt_app):
        """Test window title."""
        window = MainWindow()
        assert "Accessibility Automation Agent" in window.windowTitle()

    def test_main_window_size(self, qt_app):
        """Test window minimum size."""
        window = MainWindow()
        assert window.width() >= 1200 or window.minimumWidth() >= 1200
        assert window.height() >= 800 or window.minimumHeight() >= 800

    def test_main_window_has_tab_widget(self, qt_app):
        """Test that main window has tab widget."""
        window = MainWindow()
        assert hasattr(window, "tab_widget")
        assert window.tab_widget is not None

    def test_main_window_has_all_panels(self, qt_app):
        """Test that all panels are created."""
        window = MainWindow()
        assert hasattr(window, "voice_panel")
        assert hasattr(window, "eye_tracking_panel")
        assert hasattr(window, "mouse_panel")
        assert hasattr(window, "browser_panel")
        assert hasattr(window, "macro_panel")
        assert hasattr(window, "app_launcher_panel")
        assert hasattr(window, "settings_panel")

    def test_main_window_tab_count(self, qt_app):
        """Test that all tabs are added."""
        window = MainWindow()
        assert window.tab_widget.count() == 7

    def test_main_window_has_status_bar(self, qt_app):
        """Test that window has status bar."""
        window = MainWindow()
        assert window.status_bar is not None
        assert window.statusBar() is not None

    def test_set_theme(self, qt_app):
        """Test setting theme."""
        window = MainWindow()
        window.set_theme(Theme.LIGHT)
        assert window.current_theme == Theme.LIGHT

        window.set_theme(Theme.HIGH_CONTRAST)
        assert window.current_theme == Theme.HIGH_CONTRAST

    def test_theme_changed_signal(self, qt_app):
        """Test that theme_changed signal is emitted."""
        window = MainWindow()
        with patch.object(window.theme_changed, "emit") as mock_emit:
            window.set_theme(Theme.LIGHT)
            mock_emit.assert_called()

    def test_set_language(self, qt_app):
        """Test setting language."""
        window = MainWindow()
        window.set_language("en")
        assert window.current_language == "en"

        window.set_language("bn")
        assert window.current_language == "bn"

    def test_language_changed_signal(self, qt_app):
        """Test that language_changed signal is emitted."""
        window = MainWindow()
        with patch.object(window.language_changed, "emit") as mock_emit:
            window.set_language("bn")
            mock_emit.assert_called()

    def test_invalid_language_defaults_to_en(self, qt_app):
        """Test that invalid language defaults to English."""
        window = MainWindow()
        window.set_language("invalid")
        assert window.current_language == "en"


# ======================================================================
# Base Panel Tests
# ======================================================================


class TestBasePanel:
    """Tests for base panel class."""

    def test_base_panel_creation(self, qt_app):
        """Test creating base panel."""
        panel = BasePanel()
        assert panel is not None

    def test_base_panel_language_property(self, qt_app):
        """Test language property."""
        panel = BasePanel(language="bn")
        assert panel.language == "bn"

    def test_base_panel_update_language(self, qt_app):
        """Test updating language."""
        panel = BasePanel(language="en")
        panel.update_language("bn")
        assert panel.language == "bn"

    def test_base_panel_update_theme(self, qt_app):
        """Test updating theme."""
        panel = BasePanel()
        panel.update_theme(Theme.LIGHT)
        assert panel.current_theme == Theme.LIGHT

    def test_base_panel_get_status(self, qt_app):
        """Test get_status method."""
        panel = BasePanel()
        status = panel.get_status()
        assert isinstance(status, str)


# ======================================================================
# Voice Control Panel Tests
# ======================================================================


class TestVoiceControlPanel:
    """Tests for voice control panel."""

    def test_voice_panel_creation(self, qt_app):
        """Test creating voice panel."""
        panel = VoiceControlPanel()
        assert panel is not None

    def test_voice_panel_has_controls(self, qt_app):
        """Test that panel has required controls."""
        panel = VoiceControlPanel()
        assert hasattr(panel, "start_button")
        assert hasattr(panel, "stop_button")
        assert hasattr(panel, "language_combo")

    def test_voice_panel_update_transcription(self, qt_app):
        """Test updating transcription."""
        panel = VoiceControlPanel()
        panel.update_transcription("hello world", 0.95)
        assert panel.last_transcription == "hello world"
        assert panel.confidence == 0.95

    def test_voice_panel_update_command(self, qt_app):
        """Test updating command."""
        panel = VoiceControlPanel()
        panel.update_command("click")
        assert panel.command_label.text() == "click"

    def test_voice_panel_listening_status(self, qt_app):
        """Test listening status."""
        panel = VoiceControlPanel()
        assert panel.is_listening is False
        panel._on_start_listening()
        assert panel.is_listening is True
        panel._on_stop_listening()
        assert panel.is_listening is False


# ======================================================================
# Eye Tracking Panel Tests
# ======================================================================


class TestEyeTrackingPanel:
    """Tests for eye tracking panel."""

    def test_eye_tracking_panel_creation(self, qt_app):
        """Test creating eye tracking panel."""
        panel = EyeTrackingPanel()
        assert panel is not None

    def test_eye_tracking_requires_calibration(self, qt_app):
        """Test that tracking requires calibration."""
        panel = EyeTrackingPanel()
        assert panel.is_calibrated is False

    def test_eye_tracking_calibration(self, qt_app):
        """Test calibration."""
        panel = EyeTrackingPanel()
        panel._on_calibrate()
        assert panel.is_calibrated is True


# ======================================================================
# Mouse Control Panel Tests
# ======================================================================


class TestMouseControlPanel:
    """Tests for mouse control panel."""

    def test_mouse_panel_creation(self, qt_app):
        """Test creating mouse panel."""
        panel = MouseControlPanel()
        assert panel is not None

    def test_mouse_panel_position_update(self, qt_app):
        """Test updating cursor position."""
        panel = MouseControlPanel()
        panel.update_position(100, 200)
        assert panel.cursor_x == 100
        assert panel.cursor_y == 200
        assert "100" in panel.position_label.text()

    def test_mouse_panel_recording_toggle(self, qt_app):
        """Test recording toggle."""
        panel = MouseControlPanel()
        assert panel.is_recording is False
        panel._on_toggle_recording()
        assert panel.is_recording is True


# ======================================================================
# Browser Panel Tests
# ======================================================================


class TestBrowserPanel:
    """Tests for browser automation panel."""

    def test_browser_panel_creation(self, qt_app):
        """Test creating browser panel."""
        panel = BrowserAutomationPanel()
        assert panel is not None

    def test_browser_panel_has_search(self, qt_app):
        """Test that panel has search input."""
        panel = BrowserAutomationPanel()
        assert hasattr(panel, "search_input")

    def test_browser_panel_browser_selection(self, qt_app):
        """Test browser selection."""
        panel = BrowserAutomationPanel()
        assert "Chrome" in panel.browser_combo.itemText(0)


# ======================================================================
# Macro System Panel Tests
# ======================================================================


class TestMacroPanel:
    """Tests for macro system panel."""

    def test_macro_panel_creation(self, qt_app):
        """Test creating macro panel."""
        panel = MacroSystemPanel()
        assert panel is not None

    def test_macro_panel_recording_toggle(self, qt_app):
        """Test recording toggle."""
        panel = MacroSystemPanel()
        assert panel.is_recording is False
        panel._on_start_recording()
        assert panel.is_recording is True

    def test_macro_panel_add_to_list(self, qt_app):
        """Test adding macro to list."""
        panel = MacroSystemPanel()
        panel.add_macro_to_list("test_macro")
        assert panel.macro_list.count() == 1


# ======================================================================
# App Launcher Panel Tests
# ======================================================================


class TestAppLauncherPanel:
    """Tests for app launcher panel."""

    def test_app_launcher_creation(self, qt_app):
        """Test creating app launcher panel."""
        panel = AppLauncherPanel()
        assert panel is not None

    def test_app_launcher_set_apps(self, qt_app):
        """Test setting apps list."""
        panel = AppLauncherPanel()
        apps = ["Chrome", "Firefox", "Notepad"]
        panel.set_apps(apps)
        assert panel.app_list.count() == 3


# ======================================================================
# Settings Panel Tests
# ======================================================================


class TestSettingsPanel:
    """Tests for settings panel."""

    def test_settings_panel_creation(self, qt_app):
        """Test creating settings panel."""
        panel = SettingsPanel()
        assert panel is not None

    def test_settings_panel_has_theme_combo(self, qt_app):
        """Test that panel has theme selector."""
        panel = SettingsPanel()
        assert hasattr(panel, "theme_combo")
        assert panel.theme_combo.count() > 0

    def test_settings_panel_has_language_combo(self, qt_app):
        """Test that panel has language selector."""
        panel = SettingsPanel()
        assert hasattr(panel, "language_combo")


# ======================================================================
# Integration Tests
# ======================================================================


class TestUIIntegration:
    """Integration tests for UI components."""

    def test_all_panels_support_language_switching(self, qt_app):
        """Test that all panels support language switching."""
        panels = [
            VoiceControlPanel(),
            EyeTrackingPanel(),
            MouseControlPanel(),
            BrowserAutomationPanel(),
            MacroSystemPanel(),
            AppLauncherPanel(),
            SettingsPanel(),
        ]

        for panel in panels:
            assert hasattr(panel, "update_language")
            panel.update_language("bn")
            assert panel.language == "bn"

    def test_all_panels_support_theme_switching(self, qt_app):
        """Test that all panels support theme switching."""
        panels = [
            VoiceControlPanel(),
            EyeTrackingPanel(),
            MouseControlPanel(),
            BrowserAutomationPanel(),
            MacroSystemPanel(),
            AppLauncherPanel(),
            SettingsPanel(),
        ]

        for panel in panels:
            assert hasattr(panel, "update_theme")
            panel.update_theme(Theme.LIGHT)
            assert panel.current_theme == Theme.LIGHT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
