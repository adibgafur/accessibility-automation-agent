"""
Voice Command Parser and Command Registry.

Provides:
    - VoiceCommandParser: normalises transcribed text and maps it to
      structured ``VoiceCommand`` objects using pattern matching.
    - CommandRegistry: registers handlers (callables) for named
      commands and dispatches incoming VoiceCommands to them.
    - Built-in command definitions for English and Bengali.

The parser uses simple keyword / pattern matching rather than an ML
model, keeping the system lightweight for low-spec hardware.

Architecture:
    Whisper text --> VoiceCommandParser.parse()
                        --> VoiceCommand dataclass
                            --> CommandRegistry.dispatch()
                                --> handler callable
"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger

from ..utils.config_manager import config


# ======================================================================
# Data structures
# ======================================================================


class CommandCategory(Enum):
    """Broad categories of voice commands."""

    MOUSE = auto()        # click, double click, right click, scroll
    KEYBOARD = auto()     # type, press key, hotkey, copy, paste
    NAVIGATION = auto()   # open, close, switch, go to, back, forward
    BROWSER = auto()      # search, new tab, close tab, bookmark
    MACRO = auto()        # start recording, stop recording, play macro
    SYSTEM = auto()       # volume, brightness, screenshot, lock
    APP_CONTROL = auto()  # start listening, stop listening, change language
    CUSTOM = auto()       # user-defined commands


@dataclass
class VoiceCommand:
    """
    Structured representation of a parsed voice command.

    Attributes:
        name:       Canonical command name (e.g. ``"click"``, ``"type"``).
        category:   Broad category of the command.
        args:       Positional arguments extracted from the utterance.
        raw_text:   The original transcribed text.
        confidence: Parser confidence (0.0 - 1.0).
        language:   Language of the utterance (``"en"`` or ``"bn"``).
    """

    name: str
    category: CommandCategory
    args: List[str] = field(default_factory=list)
    raw_text: str = ""
    confidence: float = 1.0
    language: str = "en"


# ======================================================================
# Command definitions (English + Bengali)
# ======================================================================

# Each entry: (regex pattern, command_name, category, arg extractor index or None)
# The regex is applied to the normalised (lowercased, stripped) text.
# Group 1, if present, is used as the first argument.

_EN_COMMANDS: List[Tuple[str, str, CommandCategory]] = [
    # --- Mouse ---
    (r"^(?:left\s+)?click$", "click", CommandCategory.MOUSE),
    (r"^double\s+click$", "double_click", CommandCategory.MOUSE),
    (r"^right\s+click$", "right_click", CommandCategory.MOUSE),
    (r"^scroll\s+(up|down)(?:\s+(\d+))?$", "scroll", CommandCategory.MOUSE),
    (r"^drag\s+(left|right|up|down)$", "drag", CommandCategory.MOUSE),

    # --- Keyboard ---
    (r"^type\s+(.+)$", "type_text", CommandCategory.KEYBOARD),
    (r"^press\s+(.+)$", "press_key", CommandCategory.KEYBOARD),
    (r"^(?:copy|copy that)$", "copy", CommandCategory.KEYBOARD),
    (r"^(?:paste|paste that)$", "paste", CommandCategory.KEYBOARD),
    (r"^(?:cut|cut that)$", "cut", CommandCategory.KEYBOARD),
    (r"^select\s+all$", "select_all", CommandCategory.KEYBOARD),
    (r"^undo$", "undo", CommandCategory.KEYBOARD),
    (r"^redo$", "redo", CommandCategory.KEYBOARD),
    (r"^(?:enter|press enter)$", "press_enter", CommandCategory.KEYBOARD),
    (r"^(?:escape|press escape)$", "press_escape", CommandCategory.KEYBOARD),
    (r"^tab$", "press_tab", CommandCategory.KEYBOARD),
    (r"^(?:backspace|delete)$", "press_backspace", CommandCategory.KEYBOARD),

    # --- Navigation ---
    (r"^open\s+(.+)$", "open_app", CommandCategory.NAVIGATION),
    (r"^close(?:\s+(.+))?$", "close_app", CommandCategory.NAVIGATION),
    (r"^switch\s+(?:to\s+)?(.+)$", "switch_app", CommandCategory.NAVIGATION),
    (r"^go\s+(?:to\s+)?(.+)$", "go_to", CommandCategory.NAVIGATION),
    (r"^(?:alt\s+tab|switch window)$", "alt_tab", CommandCategory.NAVIGATION),
    (r"^minimize$", "minimize", CommandCategory.NAVIGATION),
    (r"^maximize$", "maximize", CommandCategory.NAVIGATION),

    # --- Browser ---
    (r"^search\s+(?:for\s+)?(.+)$", "browser_search", CommandCategory.BROWSER),
    (r"^new\s+tab$", "new_tab", CommandCategory.BROWSER),
    (r"^close\s+tab$", "close_tab", CommandCategory.BROWSER),
    (r"^(?:next|forward)\s+tab$", "next_tab", CommandCategory.BROWSER),
    (r"^(?:previous|back)\s+tab$", "prev_tab", CommandCategory.BROWSER),
    (r"^(?:go\s+)?back$", "browser_back", CommandCategory.BROWSER),
    (r"^(?:go\s+)?forward$", "browser_forward", CommandCategory.BROWSER),
    (r"^refresh$", "browser_refresh", CommandCategory.BROWSER),
    (r"^bookmark$", "bookmark", CommandCategory.BROWSER),
    (r"^(?:address|url)\s+bar$", "address_bar", CommandCategory.BROWSER),

    # --- Macro ---
    (r"^start\s+recording$", "macro_start", CommandCategory.MACRO),
    (r"^stop\s+recording$", "macro_stop", CommandCategory.MACRO),
    (r"^play\s+macro(?:\s+(.+))?$", "macro_play", CommandCategory.MACRO),
    (r"^save\s+macro(?:\s+(?:as\s+)?(.+))?$", "macro_save", CommandCategory.MACRO),
    (r"^list\s+macros?$", "macro_list", CommandCategory.MACRO),

    # --- System ---
    (r"^(?:take\s+)?screenshot$", "screenshot", CommandCategory.SYSTEM),
    (r"^volume\s+(up|down)(?:\s+(\d+))?$", "volume", CommandCategory.SYSTEM),
    (r"^mute$", "mute", CommandCategory.SYSTEM),
    (r"^lock\s+(?:screen|computer)$", "lock_screen", CommandCategory.SYSTEM),

    # --- App control ---
    (r"^(?:start|begin)\s+listening$", "start_listening", CommandCategory.APP_CONTROL),
    (r"^stop\s+listening$", "stop_listening", CommandCategory.APP_CONTROL),
    (r"^(?:switch|change)\s+(?:to\s+)?(?:language\s+)?(english|bengali|bangla)$",
     "change_language", CommandCategory.APP_CONTROL),
    (r"^(?:help|show help)$", "show_help", CommandCategory.APP_CONTROL),
    (r"^(?:settings|show settings)$", "show_settings", CommandCategory.APP_CONTROL),
    (r"^(?:quit|exit)(?:\s+app)?$", "quit_app", CommandCategory.APP_CONTROL),
    (r"^(?:emergency\s+)?stop$", "emergency_stop", CommandCategory.APP_CONTROL),
    (r"^calibrate$", "calibrate", CommandCategory.APP_CONTROL),
]

_BN_COMMANDS: List[Tuple[str, str, CommandCategory]] = [
    # --- Mouse ---
    (r"^ক্লিক(?:\s+করুন)?$", "click", CommandCategory.MOUSE),
    (r"^ডাবল\s+ক্লিক(?:\s+করুন)?$", "double_click", CommandCategory.MOUSE),
    (r"^রাইট\s+ক্লিক(?:\s+করুন)?$", "right_click", CommandCategory.MOUSE),
    (r"^স্ক্রল\s+(উপরে|নিচে)$", "scroll", CommandCategory.MOUSE),

    # --- Keyboard ---
    (r"^টাইপ(?:\s+করুন)?\s+(.+)$", "type_text", CommandCategory.KEYBOARD),
    (r"^কপি(?:\s+করুন)?$", "copy", CommandCategory.KEYBOARD),
    (r"^পেস্ট(?:\s+করুন)?$", "paste", CommandCategory.KEYBOARD),
    (r"^কাট(?:\s+করুন)?$", "cut", CommandCategory.KEYBOARD),
    (r"^সব\s+নির্বাচন(?:\s+করুন)?$", "select_all", CommandCategory.KEYBOARD),
    (r"^আনডু$", "undo", CommandCategory.KEYBOARD),
    (r"^রিডু$", "redo", CommandCategory.KEYBOARD),
    (r"^এন্টার$", "press_enter", CommandCategory.KEYBOARD),
    (r"^মুছে\s+ফেলুন$", "press_backspace", CommandCategory.KEYBOARD),

    # --- Navigation ---
    (r"^খুলুন\s+(.+)$", "open_app", CommandCategory.NAVIGATION),
    (r"^বন্ধ(?:\s+করুন)?(?:\s+(.+))?$", "close_app", CommandCategory.NAVIGATION),

    # --- Browser ---
    (r"^খুঁজুন\s+(.+)$", "browser_search", CommandCategory.BROWSER),
    (r"^নতুন\s+ট্যাব$", "new_tab", CommandCategory.BROWSER),
    (r"^ট্যাব\s+বন্ধ(?:\s+করুন)?$", "close_tab", CommandCategory.BROWSER),
    (r"^রিফ্রেশ$", "browser_refresh", CommandCategory.BROWSER),

    # --- Macro ---
    (r"^রেকর্ড(?:িং)?\s+শুরু(?:\s+করুন)?$", "macro_start", CommandCategory.MACRO),
    (r"^রেকর্ড(?:িং)?\s+বন্ধ(?:\s+করুন)?$", "macro_stop", CommandCategory.MACRO),
    (r"^ম্যাক্রো\s+চালান(?:\s+(.+))?$", "macro_play", CommandCategory.MACRO),

    # --- System ---
    (r"^স্ক্রিনশট$", "screenshot", CommandCategory.SYSTEM),
    (r"^ভলিউম\s+(বাড়ান|কমান)$", "volume", CommandCategory.SYSTEM),

    # --- App control ---
    (r"^শুনুন$", "start_listening", CommandCategory.APP_CONTROL),
    (r"^থামান$", "stop_listening", CommandCategory.APP_CONTROL),
    (r"^ভাষা\s+(?:পরিবর্তন\s+)?(?:করুন\s+)?(ইংরেজি|বাংলা)$",
     "change_language", CommandCategory.APP_CONTROL),
    (r"^সাহায্য$", "show_help", CommandCategory.APP_CONTROL),
    (r"^সেটিংস$", "show_settings", CommandCategory.APP_CONTROL),
    (r"^বন্ধ(?:\s+করুন)?$", "quit_app", CommandCategory.APP_CONTROL),
    (r"^জরুরি\s+থামান$", "emergency_stop", CommandCategory.APP_CONTROL),
    (r"^ক্যালিব্রেট$", "calibrate", CommandCategory.APP_CONTROL),
]


# ======================================================================
# Voice Command Parser
# ======================================================================


class VoiceCommandParser:
    """
    Parses transcribed text into structured VoiceCommand objects.

    The parser maintains separate pattern tables for English and
    Bengali and selects the appropriate table based on the current
    language setting.

    Usage:
        parser = VoiceCommandParser(language="en")
        cmd = parser.parse("open chrome")
        # cmd.name == "open_app", cmd.args == ["chrome"]
    """

    def __init__(self, language: str = "en") -> None:
        self.language = language

        # Compile regex patterns for performance
        self._en_patterns = [
            (re.compile(pat, re.IGNORECASE), name, cat)
            for pat, name, cat in _EN_COMMANDS
        ]
        self._bn_patterns = [
            (re.compile(pat, re.UNICODE), name, cat)
            for pat, name, cat in _BN_COMMANDS
        ]

        # Custom user-defined patterns (added at runtime)
        self._custom_patterns: List[
            Tuple[re.Pattern, str, CommandCategory]
        ] = []

        logger.info(
            f"VoiceCommandParser created | lang={language} | "
            f"en_patterns={len(self._en_patterns)} | "
            f"bn_patterns={len(self._bn_patterns)}"
        )

    def parse(self, text: str) -> Optional[VoiceCommand]:
        """
        Parse transcribed text into a VoiceCommand.

        Args:
            text: Raw transcription from Whisper.

        Returns:
            A VoiceCommand if a match is found, otherwise ``None``.
        """
        if not text or not text.strip():
            return None

        cleaned = self._normalise(text)

        # Try custom patterns first (user-defined take priority)
        cmd = self._match_patterns(self._custom_patterns, cleaned, text)
        if cmd:
            return cmd

        # Then try language-specific patterns
        patterns = (
            self._bn_patterns
            if self.language == "bn"
            else self._en_patterns
        )
        cmd = self._match_patterns(patterns, cleaned, text)
        if cmd:
            return cmd

        # If current language didn't match, try the other language
        # (user might switch languages mid-sentence)
        fallback = (
            self._en_patterns
            if self.language == "bn"
            else self._bn_patterns
        )
        cmd = self._match_patterns(fallback, cleaned, text)
        if cmd:
            cmd.confidence = 0.7  # Lower confidence for cross-language
            return cmd

        logger.debug(f"No command matched for: '{text[:60]}'")
        return None

    def _match_patterns(
        self,
        patterns: List[Tuple[re.Pattern, str, CommandCategory]],
        cleaned: str,
        raw: str,
    ) -> Optional[VoiceCommand]:
        """Try to match cleaned text against a pattern list."""
        for pattern, name, category in patterns:
            match = pattern.match(cleaned)
            if match:
                args = [
                    g for g in match.groups() if g is not None
                ]
                cmd = VoiceCommand(
                    name=name,
                    category=category,
                    args=args,
                    raw_text=raw,
                    confidence=1.0,
                    language=self.language,
                )
                logger.info(
                    f"Command parsed: {name} | args={args} | "
                    f"raw='{raw[:60]}'"
                )
                return cmd
        return None

    @staticmethod
    def _normalise(text: str) -> str:
        """
        Normalise transcription for matching.

        - Strip whitespace
        - Collapse multiple spaces
        - Remove trailing punctuation
        - Lowercase (for English)
        """
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[.!?,;:]+$", "", text)
        return text.lower()

    # ------------------------------------------------------------------
    # Custom commands
    # ------------------------------------------------------------------

    def add_custom_command(
        self,
        pattern: str,
        command_name: str,
        category: CommandCategory = CommandCategory.CUSTOM,
    ) -> None:
        """
        Register a custom voice command pattern at runtime.

        Args:
            pattern:       Regex pattern to match.
            command_name:  Canonical command name.
            category:      Command category.
        """
        compiled = re.compile(pattern, re.IGNORECASE | re.UNICODE)
        self._custom_patterns.append((compiled, command_name, category))
        logger.info(
            f"Custom command registered: '{command_name}' "
            f"pattern='{pattern}'"
        )

    def remove_custom_command(self, command_name: str) -> bool:
        """Remove a custom command by name. Returns True if found."""
        before = len(self._custom_patterns)
        self._custom_patterns = [
            (p, n, c) for p, n, c in self._custom_patterns if n != command_name
        ]
        removed = len(self._custom_patterns) < before
        if removed:
            logger.info(f"Custom command removed: '{command_name}'")
        return removed

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------

    def set_language(self, language: str) -> None:
        """Switch the parser's primary language."""
        if language not in ("en", "bn"):
            logger.warning(f"Unknown language '{language}', defaulting to en")
            language = "en"
        self.language = language
        logger.info(f"Parser language set to: {language}")

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def get_available_commands(
        self, language: Optional[str] = None
    ) -> List[str]:
        """
        Return a sorted list of all available command names for a
        language.
        """
        lang = language or self.language
        patterns = (
            self._bn_patterns if lang == "bn" else self._en_patterns
        )
        names = sorted(set(name for _, name, _ in patterns))
        # Include custom commands
        names.extend(
            sorted(set(n for _, n, _ in self._custom_patterns))
        )
        return names


# ======================================================================
# Command Registry
# ======================================================================


class CommandRegistry:
    """
    Maps command names to handler callables and dispatches
    VoiceCommand objects to the appropriate handler.

    Usage:
        registry = CommandRegistry()
        registry.register("click", lambda cmd: mouse.click())
        registry.register("type_text", lambda cmd: mouse.type_text(cmd.args[0]))
        registry.dispatch(voice_command)
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, Callable[[VoiceCommand], Any]] = {}
        self._fallback: Optional[Callable[[VoiceCommand], Any]] = None
        logger.info("CommandRegistry created")

    def register(
        self,
        command_name: str,
        handler: Callable[[VoiceCommand], Any],
    ) -> None:
        """
        Register a handler for a named command.

        If a handler is already registered for the name, it is
        replaced.

        Args:
            command_name: Canonical command name (e.g. ``"click"``).
            handler:      Callable that accepts a VoiceCommand.
        """
        self._handlers[command_name] = handler
        logger.debug(f"Handler registered for '{command_name}'")

    def unregister(self, command_name: str) -> bool:
        """Unregister a handler. Returns True if it existed."""
        if command_name in self._handlers:
            del self._handlers[command_name]
            logger.debug(f"Handler unregistered for '{command_name}'")
            return True
        return False

    def set_fallback(
        self, handler: Callable[[VoiceCommand], Any]
    ) -> None:
        """
        Set a fallback handler for commands with no registered handler.

        Useful for logging unrecognised commands or playing an audio cue.
        """
        self._fallback = handler
        logger.debug("Fallback handler registered")

    def dispatch(self, command: VoiceCommand) -> Optional[Any]:
        """
        Dispatch a VoiceCommand to its registered handler.

        Args:
            command: The parsed voice command.

        Returns:
            The handler's return value, or ``None`` if no handler
            is registered (and no fallback is set).
        """
        handler = self._handlers.get(command.name)
        if handler is not None:
            try:
                logger.info(
                    f"Dispatching '{command.name}' "
                    f"(args={command.args})"
                )
                return handler(command)
            except Exception as exc:
                logger.error(
                    f"Handler error for '{command.name}': {exc}"
                )
                return None

        if self._fallback is not None:
            logger.debug(
                f"No handler for '{command.name}', using fallback"
            )
            return self._fallback(command)

        logger.warning(
            f"No handler registered for command: '{command.name}'"
        )
        return None

    def has_handler(self, command_name: str) -> bool:
        """Check whether a handler is registered for the command."""
        return command_name in self._handlers

    def get_registered_commands(self) -> List[str]:
        """Return sorted list of all registered command names."""
        return sorted(self._handlers.keys())

    @property
    def handler_count(self) -> int:
        """Number of registered handlers."""
        return len(self._handlers)


# ======================================================================
# Convenience: VoiceCommandPipeline
# ======================================================================


class VoiceCommandPipeline:
    """
    End-to-end pipeline connecting VoiceEngine -> Parser -> Registry.

    This is a convenience wrapper that wires up the transcription
    callback so commands flow automatically from speech to action.

    Usage:
        from src.core.voice_engine import VoiceEngine

        engine = VoiceEngine(language="en")
        pipeline = VoiceCommandPipeline(engine)
        pipeline.registry.register("click", my_click_handler)
        engine.load_model()
        engine.start_listening()
        # Commands are now dispatched automatically.
    """

    def __init__(self, voice_engine: Any, language: str = "en") -> None:
        self.parser = VoiceCommandParser(language=language)
        self.registry = CommandRegistry()
        self._engine = voice_engine
        self._engine.on_transcription(self._on_text)
        logger.info("VoiceCommandPipeline created and wired to VoiceEngine")

    def _on_text(self, text: str) -> None:
        """Callback: parse text and dispatch the command."""
        command = self.parser.parse(text)
        if command is not None:
            self.registry.dispatch(command)

    def set_language(self, language: str) -> None:
        """Switch language on both the engine and the parser."""
        self._engine.set_language(language)
        self.parser.set_language(language)


__all__ = [
    "CommandCategory",
    "VoiceCommand",
    "VoiceCommandParser",
    "CommandRegistry",
    "VoiceCommandPipeline",
]
