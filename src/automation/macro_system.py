"""
Macro Recording and Playback System.

Provides recording, saving, loading, and playback of action macros.
Macros are sequences of mouse/keyboard actions that can be replayed
at any time, with optional looping and speed control.

Features:
    - Record mouse/keyboard actions from MouseController
    - Save macros to JSON files (with metadata)
    - Load macros from storage
    - Playback with speed control (1x, 2x, 0.5x, etc.)
    - Macro templates (common patterns)
    - Loop playback (repeat N times or infinite)
    - Pause/resume during recording
    - Macro listing and metadata querying
    - Bengali macro names and descriptions
    - Variable substitution in macros (e.g., {{input}})

Dependencies:
    - json (stdlib - macro serialization)
    - pathlib (stdlib - file management)

Optimised for accessibility:
    - Voice-friendly command names
    - Macro names can be in Bengali
    - Automatic timestamp tracking
    - Error recovery on playback failure
    - Metadata tracking (created, last modified, duration, etc.)
"""

import json
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

from loguru import logger

from ..utils.config_manager import config
from ..utils.error_handler import AutomationError


# ======================================================================
# Data Structures
# ======================================================================


@dataclass
class MacroMetadata:
    """Metadata for a macro."""

    name: str
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_modified: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_seconds: float = 0.0
    action_count: int = 0
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)  # e.g., ["browser", "login"]
    variables: Dict[str, str] = field(default_factory=dict)  # e.g., {"username": ""}


@dataclass
class Macro:
    """A complete macro with metadata and actions."""

    metadata: MacroMetadata
    actions: List[Dict[str, Any]]  # Actions from MouseController

    def to_dict(self) -> Dict:
        """Convert macro to dictionary for JSON serialization."""
        return {
            "metadata": asdict(self.metadata),
            "actions": self.actions,
        }

    @staticmethod
    def from_dict(data: Dict) -> "Macro":
        """Create a Macro from a dictionary (JSON deserialization)."""
        meta_dict = data["metadata"]
        metadata = MacroMetadata(
            name=meta_dict["name"],
            description=meta_dict.get("description", ""),
            created_at=meta_dict.get("created_at", datetime.now().isoformat()),
            last_modified=meta_dict.get("last_modified", datetime.now().isoformat()),
            duration_seconds=meta_dict.get("duration_seconds", 0.0),
            action_count=meta_dict.get("action_count", 0),
            version=meta_dict.get("version", "1.0"),
            tags=meta_dict.get("tags", []),
            variables=meta_dict.get("variables", {}),
        )
        return Macro(metadata=metadata, actions=data.get("actions", []))


# ======================================================================
# Macro Storage
# ======================================================================


class MacroStorage:
    """
    File-based macro storage.

    Saves and loads macros as JSON files in a directory.
    """

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        """
        Initialize macro storage.

        Args:
            storage_dir: Directory to store macro files. Defaults to
                        data/macros/ in the project.
        """
        if storage_dir is None:
            # Default to project data/macros/ directory
            storage_dir = Path(__file__).parent.parent.parent / "data" / "macros"

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"MacroStorage initialized: {self.storage_dir}")

    def save_macro(self, macro: Macro) -> Path:
        """
        Save a macro to a JSON file.

        Args:
            macro: The macro to save.

        Returns:
            Path to the saved file.

        Raises:
            AutomationError: If save fails.
        """
        try:
            # Sanitize macro name for filename
            filename = self._sanitize_name(macro.metadata.name) + ".json"
            filepath = self.storage_dir / filename

            # Update metadata
            macro.metadata.last_modified = datetime.now().isoformat()
            macro.metadata.action_count = len(macro.actions)

            # Calculate duration
            if macro.actions:
                first_time = macro.actions[0].get("timestamp", 0)
                last_time = macro.actions[-1].get("timestamp", first_time)
                macro.metadata.duration_seconds = last_time - first_time

            # Write to JSON
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(macro.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(f"Macro saved: {macro.metadata.name} ({filepath})")
            return filepath

        except Exception as exc:
            raise AutomationError(f"Failed to save macro: {exc}")

    def load_macro(self, name: str) -> Macro:
        """
        Load a macro from a JSON file.

        Args:
            name: Macro name (without .json extension).

        Returns:
            The loaded Macro.

        Raises:
            AutomationError: If macro not found or load fails.
        """
        try:
            filename = self._sanitize_name(name) + ".json"
            filepath = self.storage_dir / filename

            if not filepath.exists():
                raise AutomationError(f"Macro not found: {name}")

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            macro = Macro.from_dict(data)
            logger.info(f"Macro loaded: {name}")
            return macro

        except AutomationError:
            raise
        except Exception as exc:
            raise AutomationError(f"Failed to load macro '{name}': {exc}")

    def list_macros(self) -> List[MacroMetadata]:
        """
        List all saved macros.

        Returns:
            List of macro metadata in alphabetical order.
        """
        macros = []
        try:
            for json_file in sorted(self.storage_dir.glob("*.json")):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    meta_dict = data["metadata"]
                    metadata = MacroMetadata(
                        name=meta_dict["name"],
                        description=meta_dict.get("description", ""),
                        created_at=meta_dict.get("created_at", ""),
                        last_modified=meta_dict.get("last_modified", ""),
                        duration_seconds=meta_dict.get("duration_seconds", 0.0),
                        action_count=meta_dict.get("action_count", 0),
                        version=meta_dict.get("version", "1.0"),
                        tags=meta_dict.get("tags", []),
                        variables=meta_dict.get("variables", {}),
                    )
                    macros.append(metadata)
                except Exception as exc:
                    logger.warning(f"Failed to read macro file {json_file}: {exc}")
            return macros
        except Exception as exc:
            logger.error(f"Failed to list macros: {exc}")
            return []

    def delete_macro(self, name: str) -> bool:
        """
        Delete a saved macro.

        Args:
            name: Macro name.

        Returns:
            True if deleted, False if not found.
        """
        try:
            filename = self._sanitize_name(name) + ".json"
            filepath = self.storage_dir / filename

            if filepath.exists():
                filepath.unlink()
                logger.info(f"Macro deleted: {name}")
                return True

            logger.warning(f"Macro not found: {name}")
            return False

        except Exception as exc:
            logger.error(f"Failed to delete macro '{name}': {exc}")
            return False

    def _sanitize_name(self, name: str) -> str:
        """Sanitize macro name for use as filename."""
        # Replace special characters with underscores
        import re

        sanitized = re.sub(r"[^\w\u0980-\u09FF-]", "_", name)
        return sanitized or "macro"


# ======================================================================
# Macro Manager
# ======================================================================


class MacroManager:
    """
    High-level macro management: record, save, load, replay.

    Usage:
        manager = MacroManager()
        manager.start_recording("login_sequence")
        # ... user performs actions (mouse_controller records them) ...
        actions = manager.stop_recording()
        manager.save_macro("login_sequence", actions, description="Login flow")

        # Later:
        macro = manager.load_macro("login_sequence")
        manager.replay_macro(macro, speed=1.0)

    Voice integration:
        Commands:
        - "start recording" -> manager.start_recording()
        - "stop recording" -> manager.stop_recording()
        - "play macro login_sequence" -> manager.replay_macro(load_macro("login_sequence"))
        - "list macros" -> manager.list_macros()
    """

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        auto_save: bool = True,
    ) -> None:
        """
        Initialize the macro manager.

        Args:
            storage_dir: Directory for macro files.
            auto_save: Auto-save macros after recording.
        """
        self.storage = MacroStorage(storage_dir)
        self.auto_save = auto_save

        self._recording: bool = False
        self._current_name: Optional[str] = None
        self._current_actions: List[Dict] = []
        self._record_start_time: float = 0.0

        # Playback state
        self._playing: bool = False
        self._play_callback: Optional[Callable[[Dict], None]] = None

        # Stats
        self._record_count: int = 0
        self._playback_count: int = 0

        logger.info(
            f"MacroManager created | auto_save={auto_save} | "
            f"storage={self.storage.storage_dir}"
        )

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def start_recording(self, name: str, description: str = "") -> None:
        """
        Start recording a new macro.

        Args:
            name: Name for the macro.
            description: Optional description.

        Raises:
            AutomationError: If already recording.
        """
        if self._recording:
            raise AutomationError("Already recording a macro")

        self._recording = True
        self._current_name = name
        self._current_actions = []
        self._record_start_time = time.time()

        logger.info(f"Macro recording started: {name}")

    def stop_recording(self) -> List[Dict]:
        """
        Stop recording and return the recorded actions.

        Returns:
            List of recorded action dictionaries.

        Raises:
            AutomationError: If not currently recording.
        """
        if not self._recording:
            raise AutomationError("Not currently recording")

        self._recording = False
        actions = list(self._current_actions)

        logger.info(
            f"Macro recording stopped: {self._current_name} "
            f"({len(actions)} actions)"
        )

        # Auto-save if enabled
        if self.auto_save and self._current_name:
            try:
                macro = Macro(
                    metadata=MacroMetadata(name=self._current_name),
                    actions=actions,
                )
                self.storage.save_macro(macro)
            except Exception as exc:
                logger.warning(f"Auto-save failed: {exc}")

        self._record_count += 1
        return actions

    def record_action(self, action: Dict) -> None:
        """
        Record a single action (called by MouseController).

        Args:
            action: Action dictionary from MouseController.
        """
        if self._recording:
            self._current_actions.append(action)

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording

    # ------------------------------------------------------------------
    # Saving & Loading
    # ------------------------------------------------------------------

    def save_macro(
        self,
        name: str,
        actions: List[Dict],
        description: str = "",
        tags: List[str] = None,
    ) -> Path:
        """
        Save a macro manually.

        Args:
            name: Macro name.
            actions: List of action dictionaries.
            description: Optional description.
            tags: Optional tags (e.g., ["browser", "login"]).

        Returns:
            Path to saved file.
        """
        macro = Macro(
            metadata=MacroMetadata(
                name=name,
                description=description,
                tags=tags or [],
            ),
            actions=actions,
        )
        return self.storage.save_macro(macro)

    def load_macro(self, name: str) -> Macro:
        """
        Load a macro by name.

        Args:
            name: Macro name.

        Returns:
            The loaded Macro.

        Raises:
            AutomationError: If macro not found.
        """
        return self.storage.load_macro(name)

    def list_macros(self) -> List[MacroMetadata]:
        """
        List all saved macros.

        Returns:
            List of macro metadata.
        """
        return self.storage.list_macros()

    def delete_macro(self, name: str) -> bool:
        """
        Delete a macro.

        Args:
            name: Macro name.

        Returns:
            True if deleted, False if not found.
        """
        return self.storage.delete_macro(name)

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def replay_macro(
        self,
        macro: Macro,
        speed: float = 1.0,
        loop_count: int = 1,
        action_callback: Optional[Callable[[Dict], None]] = None,
    ) -> None:
        """
        Replay a macro.

        Args:
            macro: The macro to replay.
            speed: Playback speed (1.0 = normal, 2.0 = 2x speed, 0.5 = half speed).
            loop_count: Number of times to repeat (0 = infinite).
            action_callback: Callback to execute each action. If not provided,
                           actions are logged only.

        Raises:
            AutomationError: If speed is invalid.
        """
        if speed <= 0:
            raise AutomationError("Speed must be positive")

        if self._playing:
            logger.warning("Already playing a macro, stopping current playback")
            self._playing = False

        self._playing = True
        self._play_callback = action_callback

        try:
            loop_num = 0
            while self._playing and (loop_count == 0 or loop_num < loop_count):
                logger.info(
                    f"Playing macro: {macro.metadata.name} "
                    f"(loop {loop_num + 1}/{loop_count or '∞'})"
                )

                self._execute_actions(macro.actions, speed)
                loop_num += 1

            self._playback_count += 1
            logger.info(f"Macro playback complete: {macro.metadata.name}")

        except Exception as exc:
            logger.error(f"Macro playback error: {exc}")
            raise AutomationError(f"Macro playback failed: {exc}")
        finally:
            self._playing = False

    def stop_playback(self) -> None:
        """Stop ongoing macro playback."""
        self._playing = False
        logger.info("Macro playback stopped")

    def is_playing(self) -> bool:
        """Check if currently playing a macro."""
        return self._playing

    def _execute_actions(
        self, actions: List[Dict], speed: float
    ) -> None:
        """
        Execute a sequence of actions with proper timing.

        Args:
            actions: List of action dictionaries.
            speed: Playback speed multiplier.
        """
        if not actions:
            return

        prev_time = actions[0].get("timestamp", time.time())

        for action in actions:
            if not self._playing:
                break

            # Calculate delay based on action timestamps
            current_time = action.get("timestamp", time.time())
            delta = (current_time - prev_time) / speed

            if delta > 0:
                time.sleep(delta)

            # Execute the action
            if self._play_callback is not None:
                try:
                    self._play_callback(action)
                except Exception as exc:
                    logger.warning(f"Action execution failed: {exc}")

            prev_time = current_time

    # ------------------------------------------------------------------
    # Template Macros
    # ------------------------------------------------------------------

    def create_template(
        self, name: str, actions: List[Dict], description: str = ""
    ) -> None:
        """
        Create a template macro (useful patterns to save).

        Templates are macros that can be reused as starting points.

        Args:
            name: Template name.
            actions: Template actions.
            description: Optional description.
        """
        self.save_macro(name, actions, description, tags=["template"])

    def get_templates(self) -> List[MacroMetadata]:
        """
        Get all template macros.

        Returns:
            List of macros tagged as "template".
        """
        all_macros = self.list_macros()
        return [m for m in all_macros if "template" in m.tags]

    # ------------------------------------------------------------------
    # Variable Substitution
    # ------------------------------------------------------------------

    def substitute_variables(
        self, macro: Macro, variables: Dict[str, str]
    ) -> Macro:
        """
        Substitute variables in macro actions.

        Supports {{variable_name}} syntax in action strings (e.g., type_text).

        Args:
            macro: The macro to modify.
            variables: Dictionary of {variable_name: value}.

        Returns:
            A new Macro with substituted values.
        """
        import copy

        new_macro = copy.deepcopy(macro)

        for action in new_macro.actions:
            if action.get("type") == "type_text":
                text = action.get("text", "")
                for var_name, var_value in variables.items():
                    text = text.replace(f"{{{{{var_name}}}}}", var_value)
                action["text"] = text

            # Update macro metadata variables
            if "variables" in new_macro.metadata.__dict__:
                new_macro.metadata.variables.update(variables)

        logger.debug(f"Variables substituted in macro: {macro.metadata.name}")
        return new_macro

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return status dict for the UI panel."""
        return {
            "recording": self._recording,
            "current_macro": self._current_name if self._recording else None,
            "current_action_count": len(self._current_actions),
            "playing": self._playing,
            "saved_macro_count": len(self.list_macros()),
            "record_count": self._record_count,
            "playback_count": self._playback_count,
        }


__all__ = ["Macro", "MacroMetadata", "MacroStorage", "MacroManager"]
