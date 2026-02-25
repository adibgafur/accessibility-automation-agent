"""
Tests for src.utils.config_manager.ConfigManager.

Covers:
    - Dot-notation get/set
    - Deep merge behaviour
    - YAML loading from disk
    - Environment variable overrides (APP_ prefix)
    - Validation of required keys
    - Section retrieval
    - Reload from disk
    - Bengali strings loading
"""

import json
import os
from pathlib import Path

import pytest
import yaml

from src.utils.config_manager import ConfigManager


# ======================================================================
# Helpers
# ======================================================================


def _fresh_manager(config_dir: Path) -> ConfigManager:
    """Create a ConfigManager that reads from *config_dir* (not singleton)."""
    # Bypass the singleton so every test gets a clean instance
    mgr = object.__new__(ConfigManager)
    mgr._config = {}
    mgr._config_dir = config_dir
    mgr._initialized = True
    mgr._load_all()
    return mgr


# ======================================================================
# Tests
# ======================================================================


class TestDotNotationAccess:
    """Test get() and set() with dot-separated keys."""

    def test_get_top_level_key(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        assert mgr.get("application.name") == "Test Accessibility Agent"

    def test_get_nested_key(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        assert mgr.get("voice.language") == "en"

    def test_get_missing_key_returns_default(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        assert mgr.get("nonexistent.key") is None
        assert mgr.get("nonexistent.key", "fallback") == "fallback"

    def test_set_creates_intermediate_dicts(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        mgr.set("new.deep.nested.value", 42)
        assert mgr.get("new.deep.nested.value") == 42

    def test_set_overwrites_existing(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        mgr.set("voice.language", "bn")
        assert mgr.get("voice.language") == "bn"


class TestDeepMerge:
    """Test the _deep_merge static method."""

    def test_merge_non_overlapping(self):
        base = {"a": 1}
        override = {"b": 2}
        result = ConfigManager._deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_merge_overlapping_scalar(self):
        base = {"a": 1}
        override = {"a": 99}
        result = ConfigManager._deep_merge(base, override)
        assert result["a"] == 99

    def test_merge_nested_dicts(self):
        base = {"x": {"y": 1, "z": 2}}
        override = {"x": {"y": 10, "w": 3}}
        result = ConfigManager._deep_merge(base, override)
        assert result == {"x": {"y": 10, "z": 2, "w": 3}}


class TestYAMLLoading:
    """Test loading YAML files from the config directory."""

    def test_loads_default_settings(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        assert mgr.get("application.version") == "0.0.1"

    def test_loads_ufo2_config(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        assert mgr.get("ufo2.enabled") is True

    def test_loads_guirilla_config(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        assert mgr.get("guirilla.quantization") == "int8"

    def test_missing_yaml_file_is_silently_skipped(self, tmp_config_dir: Path):
        """The manager should not crash if an optional config is absent."""
        (tmp_config_dir / "ufo2_config.yaml").unlink()
        mgr = _fresh_manager(tmp_config_dir)
        # ufo2 section is gone since the file was deleted
        assert mgr.get("ufo2.enabled") is None

    def test_malformed_yaml_does_not_crash(self, tmp_config_dir: Path):
        """Invalid YAML should be logged and skipped, not crash."""
        (tmp_config_dir / "default_settings.yaml").write_text(
            "{ invalid yaml:: :", encoding="utf-8"
        )
        # Should not raise
        mgr = _fresh_manager(tmp_config_dir)
        assert isinstance(mgr.get_all(), dict)


class TestEnvOverrides:
    """Test APP_ environment variable overrides."""

    def test_env_override_simple(self, tmp_config_dir: Path, monkeypatch):
        monkeypatch.setenv("APP_VOICE__LANGUAGE", "bn")
        mgr = _fresh_manager(tmp_config_dir)
        assert mgr.get("voice.language") == "bn"

    def test_env_override_nested(self, tmp_config_dir: Path, monkeypatch):
        monkeypatch.setenv("APP_UI__THEME", "light")
        mgr = _fresh_manager(tmp_config_dir)
        assert mgr.get("ui.theme") == "light"


class TestValidation:
    """Test the validate() method."""

    def test_all_keys_present(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        missing = mgr.validate(["voice.language", "eye_tracking.fps"])
        assert missing == []

    def test_missing_keys_reported(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        missing = mgr.validate(["voice.language", "does.not.exist"])
        assert "does.not.exist" in missing

    def test_empty_required_list(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        assert mgr.validate([]) == []


class TestSectionRetrieval:
    """Test get_section() and get_all()."""

    def test_get_section_returns_copy(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        voice = mgr.get_section("voice")
        assert isinstance(voice, dict)
        assert voice["language"] == "en"
        # Mutating the copy must not affect the original
        voice["language"] = "fr"
        assert mgr.get("voice.language") == "en"

    def test_get_section_missing_returns_empty(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        assert mgr.get_section("nonexistent") == {}

    def test_get_all_returns_dict(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        all_cfg = mgr.get_all()
        assert isinstance(all_cfg, dict)
        assert "voice" in all_cfg


class TestReload:
    """Test config reload from disk."""

    def test_reload_picks_up_changes(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        assert mgr.get("voice.whisper_model") == "tiny"

        # Modify the YAML on disk
        settings_path = tmp_config_dir / "default_settings.yaml"
        data = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
        data["voice"]["whisper_model"] = "small"
        settings_path.write_text(
            yaml.dump(data, default_flow_style=False), encoding="utf-8"
        )

        mgr.reload()
        assert mgr.get("voice.whisper_model") == "small"


class TestBengaliStrings:
    """Test Bengali string file loading."""

    def test_loads_bengali_strings(self, tmp_config_dir: Path):
        mgr = _fresh_manager(tmp_config_dir)
        strings = mgr.load_bengali_strings()
        assert strings["start"] == "শুরু করুন"
        assert strings["stop"] == "থামুন"

    def test_missing_bengali_file_returns_empty(self, tmp_config_dir: Path):
        (tmp_config_dir / "bengali_strings.json").unlink()
        mgr = _fresh_manager(tmp_config_dir)
        assert mgr.load_bengali_strings() == {}

    def test_malformed_json_returns_empty(self, tmp_config_dir: Path):
        (tmp_config_dir / "bengali_strings.json").write_text(
            "{ invalid json", encoding="utf-8"
        )
        mgr = _fresh_manager(tmp_config_dir)
        assert mgr.load_bengali_strings() == {}
