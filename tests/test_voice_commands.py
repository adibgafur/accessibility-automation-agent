"""
Tests for src.core.voice_commands — VoiceCommandParser, CommandRegistry,
and VoiceCommandPipeline.
"""

from unittest.mock import MagicMock

import pytest

from src.core.voice_commands import (
    CommandCategory,
    VoiceCommand,
    VoiceCommandParser,
    CommandRegistry,
    VoiceCommandPipeline,
)


# ======================================================================
# VoiceCommandParser — English
# ======================================================================


class TestParserEnglish:
    """Test command parsing with English patterns."""

    @pytest.fixture()
    def parser(self) -> VoiceCommandParser:
        return VoiceCommandParser(language="en")

    # --- Mouse commands ---

    def test_click(self, parser: VoiceCommandParser):
        cmd = parser.parse("click")
        assert cmd is not None
        assert cmd.name == "click"
        assert cmd.category == CommandCategory.MOUSE

    def test_left_click(self, parser: VoiceCommandParser):
        cmd = parser.parse("left click")
        assert cmd is not None
        assert cmd.name == "click"

    def test_double_click(self, parser: VoiceCommandParser):
        cmd = parser.parse("double click")
        assert cmd is not None
        assert cmd.name == "double_click"

    def test_right_click(self, parser: VoiceCommandParser):
        cmd = parser.parse("right click")
        assert cmd is not None
        assert cmd.name == "right_click"

    def test_scroll_up(self, parser: VoiceCommandParser):
        cmd = parser.parse("scroll up")
        assert cmd is not None
        assert cmd.name == "scroll"
        assert "up" in cmd.args

    def test_scroll_down_with_amount(self, parser: VoiceCommandParser):
        cmd = parser.parse("scroll down 5")
        assert cmd is not None
        assert cmd.name == "scroll"
        assert "down" in cmd.args
        assert "5" in cmd.args

    # --- Keyboard commands ---

    def test_type_text(self, parser: VoiceCommandParser):
        cmd = parser.parse("type hello world")
        assert cmd is not None
        assert cmd.name == "type_text"
        assert cmd.args == ["hello world"]

    def test_press_key(self, parser: VoiceCommandParser):
        cmd = parser.parse("press enter")
        assert cmd is not None
        assert cmd.name == "press_key"
        assert "enter" in cmd.args

    def test_copy(self, parser: VoiceCommandParser):
        cmd = parser.parse("copy")
        assert cmd is not None
        assert cmd.name == "copy"

    def test_paste(self, parser: VoiceCommandParser):
        cmd = parser.parse("paste")
        assert cmd is not None
        assert cmd.name == "paste"

    def test_cut(self, parser: VoiceCommandParser):
        cmd = parser.parse("cut")
        assert cmd is not None
        assert cmd.name == "cut"

    def test_select_all(self, parser: VoiceCommandParser):
        cmd = parser.parse("select all")
        assert cmd is not None
        assert cmd.name == "select_all"

    def test_undo(self, parser: VoiceCommandParser):
        cmd = parser.parse("undo")
        assert cmd is not None
        assert cmd.name == "undo"

    def test_redo(self, parser: VoiceCommandParser):
        cmd = parser.parse("redo")
        assert cmd is not None
        assert cmd.name == "redo"

    # --- Navigation ---

    def test_open_app(self, parser: VoiceCommandParser):
        cmd = parser.parse("open chrome")
        assert cmd is not None
        assert cmd.name == "open_app"
        assert cmd.args == ["chrome"]

    def test_close_app(self, parser: VoiceCommandParser):
        cmd = parser.parse("close notepad")
        assert cmd is not None
        assert cmd.name == "close_app"
        assert "notepad" in cmd.args

    def test_switch_app(self, parser: VoiceCommandParser):
        cmd = parser.parse("switch to firefox")
        assert cmd is not None
        assert cmd.name == "switch_app"
        assert "firefox" in cmd.args

    def test_alt_tab(self, parser: VoiceCommandParser):
        cmd = parser.parse("alt tab")
        assert cmd is not None
        assert cmd.name == "alt_tab"

    # --- Browser ---

    def test_search(self, parser: VoiceCommandParser):
        cmd = parser.parse("search for python tutorials")
        assert cmd is not None
        assert cmd.name == "browser_search"
        assert "python tutorials" in cmd.args

    def test_new_tab(self, parser: VoiceCommandParser):
        cmd = parser.parse("new tab")
        assert cmd is not None
        assert cmd.name == "new_tab"

    def test_close_tab(self, parser: VoiceCommandParser):
        cmd = parser.parse("close tab")
        assert cmd is not None
        assert cmd.name == "close_tab"

    def test_refresh(self, parser: VoiceCommandParser):
        cmd = parser.parse("refresh")
        assert cmd is not None
        assert cmd.name == "browser_refresh"

    # --- Macro ---

    def test_start_recording(self, parser: VoiceCommandParser):
        cmd = parser.parse("start recording")
        assert cmd is not None
        assert cmd.name == "macro_start"

    def test_stop_recording(self, parser: VoiceCommandParser):
        cmd = parser.parse("stop recording")
        assert cmd is not None
        assert cmd.name == "macro_stop"

    def test_play_macro(self, parser: VoiceCommandParser):
        cmd = parser.parse("play macro login")
        assert cmd is not None
        assert cmd.name == "macro_play"
        assert "login" in cmd.args

    # --- System ---

    def test_screenshot(self, parser: VoiceCommandParser):
        cmd = parser.parse("screenshot")
        assert cmd is not None
        assert cmd.name == "screenshot"

    def test_take_screenshot(self, parser: VoiceCommandParser):
        cmd = parser.parse("take screenshot")
        assert cmd is not None
        assert cmd.name == "screenshot"

    # --- App control ---

    def test_help(self, parser: VoiceCommandParser):
        cmd = parser.parse("help")
        assert cmd is not None
        assert cmd.name == "show_help"

    def test_quit(self, parser: VoiceCommandParser):
        cmd = parser.parse("quit")
        assert cmd is not None
        assert cmd.name == "quit_app"

    def test_change_language(self, parser: VoiceCommandParser):
        cmd = parser.parse("change to bengali")
        assert cmd is not None
        assert cmd.name == "change_language"
        assert "bengali" in cmd.args

    def test_emergency_stop(self, parser: VoiceCommandParser):
        cmd = parser.parse("emergency stop")
        assert cmd is not None
        assert cmd.name == "emergency_stop"

    def test_calibrate(self, parser: VoiceCommandParser):
        cmd = parser.parse("calibrate")
        assert cmd is not None
        assert cmd.name == "calibrate"


# ======================================================================
# VoiceCommandParser — Bengali
# ======================================================================


class TestParserBengali:
    """Test command parsing with Bengali patterns."""

    @pytest.fixture()
    def parser(self) -> VoiceCommandParser:
        return VoiceCommandParser(language="bn")

    def test_click_bn(self, parser: VoiceCommandParser):
        cmd = parser.parse("ক্লিক করুন")
        assert cmd is not None
        assert cmd.name == "click"

    def test_click_bn_short(self, parser: VoiceCommandParser):
        cmd = parser.parse("ক্লিক")
        assert cmd is not None
        assert cmd.name == "click"

    def test_double_click_bn(self, parser: VoiceCommandParser):
        cmd = parser.parse("ডাবল ক্লিক করুন")
        assert cmd is not None
        assert cmd.name == "double_click"

    def test_copy_bn(self, parser: VoiceCommandParser):
        cmd = parser.parse("কপি করুন")
        assert cmd is not None
        assert cmd.name == "copy"

    def test_paste_bn(self, parser: VoiceCommandParser):
        cmd = parser.parse("পেস্ট করুন")
        assert cmd is not None
        assert cmd.name == "paste"

    def test_open_app_bn(self, parser: VoiceCommandParser):
        cmd = parser.parse("খুলুন ক্রোম")
        assert cmd is not None
        assert cmd.name == "open_app"
        assert "ক্রোম" in cmd.args

    def test_search_bn(self, parser: VoiceCommandParser):
        cmd = parser.parse("খুঁজুন পাইথন")
        assert cmd is not None
        assert cmd.name == "browser_search"

    def test_new_tab_bn(self, parser: VoiceCommandParser):
        cmd = parser.parse("নতুন ট্যাব")
        assert cmd is not None
        assert cmd.name == "new_tab"

    def test_screenshot_bn(self, parser: VoiceCommandParser):
        cmd = parser.parse("স্ক্রিনশট")
        assert cmd is not None
        assert cmd.name == "screenshot"

    def test_help_bn(self, parser: VoiceCommandParser):
        cmd = parser.parse("সাহায্য")
        assert cmd is not None
        assert cmd.name == "show_help"

    def test_settings_bn(self, parser: VoiceCommandParser):
        cmd = parser.parse("সেটিংস")
        assert cmd is not None
        assert cmd.name == "show_settings"


# ======================================================================
# Parser — Edge cases
# ======================================================================


class TestParserEdgeCases:
    @pytest.fixture()
    def parser(self) -> VoiceCommandParser:
        return VoiceCommandParser(language="en")

    def test_empty_string(self, parser: VoiceCommandParser):
        assert parser.parse("") is None

    def test_whitespace_only(self, parser: VoiceCommandParser):
        assert parser.parse("   ") is None

    def test_none_input(self, parser: VoiceCommandParser):
        assert parser.parse(None) is None

    def test_unrecognised_text(self, parser: VoiceCommandParser):
        assert parser.parse("the weather is nice today") is None

    def test_trailing_punctuation_stripped(self, parser: VoiceCommandParser):
        cmd = parser.parse("click!")
        assert cmd is not None
        assert cmd.name == "click"

    def test_extra_whitespace_collapsed(self, parser: VoiceCommandParser):
        cmd = parser.parse("  double   click  ")
        assert cmd is not None
        assert cmd.name == "double_click"

    def test_case_insensitive(self, parser: VoiceCommandParser):
        cmd = parser.parse("OPEN Chrome")
        assert cmd is not None
        assert cmd.name == "open_app"

    def test_cross_language_fallback(self):
        """English parser should fall back to Bengali patterns."""
        parser = VoiceCommandParser(language="en")
        cmd = parser.parse("ক্লিক করুন")
        assert cmd is not None
        assert cmd.name == "click"
        assert cmd.confidence == 0.7  # lower confidence for cross-lang


# ======================================================================
# Custom commands
# ======================================================================


class TestCustomCommands:
    @pytest.fixture()
    def parser(self) -> VoiceCommandParser:
        return VoiceCommandParser(language="en")

    def test_add_custom_command(self, parser: VoiceCommandParser):
        parser.add_custom_command(
            r"^launch rocket$", "launch_rocket"
        )
        cmd = parser.parse("launch rocket")
        assert cmd is not None
        assert cmd.name == "launch_rocket"
        assert cmd.category == CommandCategory.CUSTOM

    def test_custom_takes_priority(self, parser: VoiceCommandParser):
        """Custom pattern should override built-in patterns."""
        parser.add_custom_command(r"^click$", "custom_click")
        cmd = parser.parse("click")
        assert cmd.name == "custom_click"

    def test_remove_custom_command(self, parser: VoiceCommandParser):
        parser.add_custom_command(r"^test$", "test_cmd")
        assert parser.remove_custom_command("test_cmd") is True
        assert parser.parse("test") is None

    def test_remove_nonexistent(self, parser: VoiceCommandParser):
        assert parser.remove_custom_command("nope") is False


# ======================================================================
# Available commands
# ======================================================================


class TestAvailableCommands:
    def test_en_commands_listed(self):
        parser = VoiceCommandParser(language="en")
        cmds = parser.get_available_commands()
        assert "click" in cmds
        assert "type_text" in cmds
        assert "browser_search" in cmds

    def test_bn_commands_listed(self):
        parser = VoiceCommandParser(language="bn")
        cmds = parser.get_available_commands()
        assert "click" in cmds


# ======================================================================
# CommandRegistry
# ======================================================================


class TestCommandRegistry:
    @pytest.fixture()
    def registry(self) -> CommandRegistry:
        return CommandRegistry()

    def _make_cmd(self, name: str, args=None) -> VoiceCommand:
        return VoiceCommand(
            name=name,
            category=CommandCategory.MOUSE,
            args=args or [],
            raw_text=name,
        )

    def test_register_and_dispatch(self, registry: CommandRegistry):
        handler = MagicMock(return_value="ok")
        registry.register("click", handler)

        cmd = self._make_cmd("click")
        result = registry.dispatch(cmd)

        handler.assert_called_once_with(cmd)
        assert result == "ok"

    def test_dispatch_unknown(self, registry: CommandRegistry):
        cmd = self._make_cmd("fly_away")
        result = registry.dispatch(cmd)
        assert result is None

    def test_fallback_handler(self, registry: CommandRegistry):
        fallback = MagicMock(return_value="fallback")
        registry.set_fallback(fallback)

        cmd = self._make_cmd("unknown")
        result = registry.dispatch(cmd)

        fallback.assert_called_once_with(cmd)
        assert result == "fallback"

    def test_handler_error_caught(self, registry: CommandRegistry):
        bad_handler = MagicMock(side_effect=RuntimeError("boom"))
        registry.register("explode", bad_handler)

        cmd = self._make_cmd("explode")
        result = registry.dispatch(cmd)
        assert result is None

    def test_unregister(self, registry: CommandRegistry):
        registry.register("click", MagicMock())
        assert registry.unregister("click") is True
        assert registry.has_handler("click") is False

    def test_unregister_nonexistent(self, registry: CommandRegistry):
        assert registry.unregister("nope") is False

    def test_has_handler(self, registry: CommandRegistry):
        assert registry.has_handler("click") is False
        registry.register("click", MagicMock())
        assert registry.has_handler("click") is True

    def test_get_registered_commands(self, registry: CommandRegistry):
        registry.register("click", MagicMock())
        registry.register("type_text", MagicMock())
        cmds = registry.get_registered_commands()
        assert cmds == ["click", "type_text"]

    def test_handler_count(self, registry: CommandRegistry):
        assert registry.handler_count == 0
        registry.register("a", MagicMock())
        registry.register("b", MagicMock())
        assert registry.handler_count == 2

    def test_replace_handler(self, registry: CommandRegistry):
        h1 = MagicMock()
        h2 = MagicMock()
        registry.register("click", h1)
        registry.register("click", h2)

        cmd = self._make_cmd("click")
        registry.dispatch(cmd)
        h1.assert_not_called()
        h2.assert_called_once()


# ======================================================================
# VoiceCommandPipeline
# ======================================================================


class TestVoiceCommandPipeline:
    def test_pipeline_wiring(self):
        """Pipeline should parse text and dispatch the command."""
        mock_engine = MagicMock()
        mock_engine.on_transcription = MagicMock()

        pipeline = VoiceCommandPipeline(mock_engine, language="en")

        # Register a handler
        handler = MagicMock()
        pipeline.registry.register("click", handler)

        # Simulate transcription callback
        # Get the callback that was registered with the engine
        cb = mock_engine.on_transcription.call_args[0][0]
        cb("click")

        handler.assert_called_once()
        dispatched_cmd = handler.call_args[0][0]
        assert dispatched_cmd.name == "click"

    def test_pipeline_unrecognised(self):
        """Unrecognised text should not dispatch anything."""
        mock_engine = MagicMock()
        pipeline = VoiceCommandPipeline(mock_engine, language="en")

        handler = MagicMock()
        pipeline.registry.register("click", handler)

        cb = mock_engine.on_transcription.call_args[0][0]
        cb("random gibberish that matches nothing")

        handler.assert_not_called()

    def test_pipeline_set_language(self):
        """set_language should propagate to both engine and parser."""
        mock_engine = MagicMock()
        pipeline = VoiceCommandPipeline(mock_engine, language="en")

        pipeline.set_language("bn")
        mock_engine.set_language.assert_called_once_with("bn")
        assert pipeline.parser.language == "bn"
