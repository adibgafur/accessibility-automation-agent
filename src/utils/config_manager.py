"""
Configuration Management for Accessibility Automation Agent.

Provides a singleton ConfigManager that:
    - Loads YAML configuration files
    - Supports dot-notation access (e.g., config.get("voice.language"))
    - Merges defaults with environment overrides
    - Applies environment variable overrides (APP_ prefix)
    - Validates required configuration keys
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger


class ConfigManager:
    """
    Singleton configuration manager.

    Loads configuration from YAML files in the config/ directory,
    merges with environment-specific overrides, and provides
    dot-notation access to nested values.

    Usage:
        from src.utils.config_manager import config

        language = config.get("voice.language", default="en")
        config.set("ui.theme", "dark")
    """

    _instance: Optional["ConfigManager"] = None

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            self._config: Dict[str, Any] = {}
            self._config_dir = Path("config")
            self._initialized = True
            self._load_all()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        """Load default config, then apply environment overrides."""
        self._load_yaml("default_settings.yaml")
        self._load_yaml("ufo2_config.yaml")
        self._load_yaml("guirilla_config.yaml")

        # Environment-specific file (e.g., production_settings.yaml)
        env = os.getenv("APP_ENV", "development")
        env_file = f"{env}_settings.yaml"
        if (self._config_dir / env_file).exists():
            self._load_yaml(env_file)

        self._apply_env_overrides()
        logger.info("Configuration loaded successfully")

    def _load_yaml(self, filename: str) -> None:
        """
        Load a single YAML file and merge into the config dict.

        Args:
            filename: Name of the YAML file inside the config/ directory.
        """
        filepath = self._config_dir / filename
        if not filepath.exists():
            logger.warning(f"Config file not found: {filepath}")
            return

        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            self._config = self._deep_merge(self._config, data)
            logger.debug(f"Loaded config: {filepath}")
        except yaml.YAMLError as exc:
            logger.error(f"Failed to parse {filepath}: {exc}")
        except OSError as exc:
            logger.error(f"Failed to read {filepath}: {exc}")

    # ------------------------------------------------------------------
    # Merging helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> Dict:
        """Recursively merge *override* into *base* (mutates base)."""
        for key, value in override.items():
            if (
                key in base
                and isinstance(base[key], dict)
                and isinstance(value, dict)
            ):
                ConfigManager._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def _apply_env_overrides(self) -> None:
        """
        Apply environment variables that start with ``APP_`` as config
        overrides.  The variable name is lowercased and ``__`` is
        treated as a dot separator.

        Example:
            APP_VOICE__LANGUAGE=bn  ->  config["voice"]["language"] = "bn"
        """
        for key, value in os.environ.items():
            if not key.startswith("APP_"):
                continue
            config_path = key[4:].lower().replace("__", ".")
            self.set(config_path, value)
            logger.debug(f"Env override applied: {config_path}={value}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a configuration value using dot-notation.

        Args:
            key:     Dot-separated path (e.g., ``"voice.language"``).
            default: Fallback value when the key is missing.

        Returns:
            The configuration value, or *default*.
        """
        parts = key.split(".")
        node: Any = self._config
        for part in parts:
            if isinstance(node, dict):
                node = node.get(part)
            else:
                return default
            if node is None:
                return default
        return node

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value using dot-notation.

        Intermediate dictionaries are created automatically.

        Args:
            key:   Dot-separated path.
            value: Value to store.
        """
        parts = key.split(".")
        node = self._config
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value

    def get_section(self, section: str) -> Dict[str, Any]:
        """Return an entire top-level section as a dict (copy)."""
        data = self._config.get(section, {})
        if isinstance(data, dict):
            return data.copy()
        return {}

    def get_all(self) -> Dict[str, Any]:
        """Return a shallow copy of the full configuration dict."""
        return self._config.copy()

    def reload(self) -> None:
        """Discard current config and reload from disk."""
        self._config.clear()
        self._load_all()
        logger.info("Configuration reloaded from disk")

    def validate(self, required_keys: List[str]) -> List[str]:
        """
        Validate that all *required_keys* are present.

        Args:
            required_keys: List of dot-notation keys.

        Returns:
            List of missing keys (empty if all present).
        """
        missing = [k for k in required_keys if self.get(k) is None]
        if missing:
            logger.warning(f"Missing configuration keys: {missing}")
        return missing

    # ------------------------------------------------------------------
    # Bengali helpers
    # ------------------------------------------------------------------

    def load_bengali_strings(self) -> Dict[str, Any]:
        """
        Load Bengali translation strings from config/bengali_strings.json.

        Returns:
            Dictionary of Bengali UI strings.
        """
        import json

        filepath = self._config_dir / "bengali_strings.json"
        if not filepath.exists():
            logger.warning("Bengali strings file not found")
            return {}
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(f"Failed to load Bengali strings: {exc}")
            return {}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
config = ConfigManager()

__all__ = ["ConfigManager", "config"]
