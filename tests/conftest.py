"""
Shared test fixtures for the Accessibility Automation Agent test suite.

Provides:
    - Temporary config directory with sample YAML files
    - ConfigManager instances isolated from the real config
    - Common test data and helpers
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest
import yaml


@pytest.fixture()
def tmp_config_dir(tmp_path: Path) -> Path:
    """
    Create a temporary config directory populated with default YAML files.

    Returns the path to the temporary config directory.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # default_settings.yaml
    default_settings = {
        "application": {
            "name": "Test Accessibility Agent",
            "version": "0.0.1",
            "environment": "test",
        },
        "voice": {
            "enabled": True,
            "language": "en",
            "whisper_model": "tiny",
            "device": "cpu",
            "confidence_threshold": 0.5,
            "timeout": 10,
        },
        "eye_tracking": {
            "enabled": True,
            "camera_index": 0,
            "fps": 30,
            "smoothing_factor": 0.7,
            "jitter_threshold": 5,
        },
        "blink_detection": {
            "single_blink_threshold": 0.3,
            "double_blink_timeout": 300,
            "eye_aspect_ratio_threshold": 0.2,
        },
        "gui_detection": {
            "primary_engine": "ufo2",
            "fallback_engine": "guirilla",
            "ufo2_confidence_threshold": 0.7,
            "guirilla_confidence_threshold": 0.5,
        },
        "ui": {
            "theme": "dark",
            "font_size": 12,
            "button_size": 64,
            "language": "en",
        },
    }
    (config_dir / "default_settings.yaml").write_text(
        yaml.dump(default_settings, default_flow_style=False),
        encoding="utf-8",
    )

    # ufo2_config.yaml (minimal)
    ufo2_config = {
        "ufo2": {
            "enabled": True,
            "use_visual_detection": True,
        },
    }
    (config_dir / "ufo2_config.yaml").write_text(
        yaml.dump(ufo2_config, default_flow_style=False),
        encoding="utf-8",
    )

    # guirilla_config.yaml (minimal)
    guirilla_config = {
        "guirilla": {
            "enabled": True,
            "model": "macpaw-research/GUIrilla-See-0.7B",
            "quantization": "int8",
        },
    }
    (config_dir / "guirilla_config.yaml").write_text(
        yaml.dump(guirilla_config, default_flow_style=False),
        encoding="utf-8",
    )

    # bengali_strings.json
    bengali_strings = {
        "start": "শুরু করুন",
        "stop": "থামুন",
        "settings": "সেটিংস",
    }
    (config_dir / "bengali_strings.json").write_text(
        json.dumps(bengali_strings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return config_dir


@pytest.fixture()
def isolated_config(tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Provide a fresh ConfigManager instance that reads from the temp
    config directory instead of the real project config/.

    Resets the singleton so each test gets its own instance.
    """
    from src.utils.config_manager import ConfigManager

    # Reset singleton
    ConfigManager._instance = None

    # Patch the config dir
    monkeypatch.setattr(
        ConfigManager,
        "__init__",
        _make_patched_init(tmp_config_dir),
    )

    mgr = ConfigManager()
    yield mgr

    # Cleanup singleton for other tests
    ConfigManager._instance = None


def _make_patched_init(config_dir: Path):
    """Create a patched __init__ that uses the given config directory."""

    def patched_init(self) -> None:
        if not hasattr(self, "_initialized"):
            self._config = {}
            self._config_dir = config_dir
            self._initialized = True
            self._load_all()

    return patched_init


@pytest.fixture()
def sample_yaml_file(tmp_path: Path) -> Path:
    """Create a standalone sample YAML file for unit tests."""
    data = {"section": {"key1": "value1", "key2": 42, "nested": {"deep": True}}}
    filepath = tmp_path / "sample.yaml"
    filepath.write_text(
        yaml.dump(data, default_flow_style=False), encoding="utf-8"
    )
    return filepath
