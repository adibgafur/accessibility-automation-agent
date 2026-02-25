"""
Tests for src.automation.app_launcher.

These tests verify the AppLauncher's public API without requiring
a real Windows system or actual app installations. Subprocess and
registry access are mocked.
"""

from unittest.mock import MagicMock, patch, call
from pathlib import Path
from typing import List

import pytest

from src.utils.error_handler import AutomationError


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture()
def launcher():
    """Return an AppLauncher instance."""
    from src.automation.app_launcher import AppLauncher

    return AppLauncher()


@pytest.fixture()
def launcher_with_apps(launcher):
    """Return an AppLauncher with some pre-discovered apps."""
    launcher._discovered = True
    launcher._apps = {
        "chrome": "C:\\Program Files\\Google\\Chrome\\chrome.exe",
        "notepad": "notepad.exe",
        "firefox": "C:\\Program Files\\Mozilla Firefox\\firefox.exe",
        "calc": "calc.exe",
    }
    return launcher


# ======================================================================
# Initialization
# ======================================================================


class TestInitialization:
    """Test AppLauncher initialization."""

    def test_init(self, launcher):
        assert launcher._discovered is False
        assert launcher._apps == {}
        assert launcher._running_pids == {}
        assert launcher._launch_count == 0

    def test_discovered_false_initially(self, launcher):
        assert launcher._discovered is False


# ======================================================================
# Discovery
# ======================================================================


class TestDiscovery:
    """Test app discovery."""

    def test_discover_apps_common_apps(self, launcher):
        with patch.object(launcher, "_scan_registry"):
            with patch.object(launcher, "_scan_common_paths"):
                count = launcher.discover_apps()

        # Should have at least the common apps
        assert launcher._discovered is True
        assert count > 0
        assert "chrome" in launcher._apps
        assert "notepad" in launcher._apps

    def test_discover_apps_caches_result(self, launcher):
        with patch.object(launcher, "_scan_registry"):
            with patch.object(launcher, "_scan_common_paths"):
                count1 = launcher.discover_apps()
                count2 = launcher.discover_apps()

        # Both should return same count
        assert count1 == count2

    def test_discover_apps_force_rescans(self, launcher):
        with patch.object(launcher, "_scan_registry"):
            with patch.object(launcher, "_scan_common_paths"):
                launcher.discover_apps()
                launcher._apps["new_app"] = "path"

                # Force rescan should clear new_app
                launcher.discover_apps(force=True)

        assert "new_app" not in launcher._apps

    def test_discover_apps_returns_count(self, launcher):
        with patch.object(launcher, "_scan_registry"):
            with patch.object(launcher, "_scan_common_paths"):
                count = launcher.discover_apps()

        assert isinstance(count, int)
        assert count > 0

    def test_scan_registry_not_found(self, launcher):
        """On non-Windows systems, registry scan should be skipped."""
        with patch("builtins.__import__", side_effect=ImportError("no winreg")):
            # Should not raise
            launcher._scan_registry()

    @patch("subprocess.run")
    def test_scan_common_paths_missing_path(self, mock_run, launcher):
        """If common paths don't exist, scan should handle gracefully."""
        with patch("pathlib.Path.exists", return_value=False):
            launcher._scan_common_paths()
            # Should not raise


# ======================================================================
# Launching
# ======================================================================


class TestLaunching:
    """Test app launching."""

    @patch("subprocess.Popen")
    def test_launch_app(self, mock_popen, launcher_with_apps):
        mock_process = MagicMock()
        mock_process.pid = 1234
        mock_popen.return_value = mock_process

        pid = launcher_with_apps.launch("chrome")

        mock_popen.assert_called_once()
        assert launcher_with_apps._launch_count == 1
        assert pid == 1234

    @patch("subprocess.Popen")
    def test_launch_app_increments_counter(self, mock_popen, launcher_with_apps):
        mock_process = MagicMock()
        mock_process.pid = 1234
        mock_popen.return_value = mock_process

        launcher_with_apps.launch("chrome")
        launcher_with_apps.launch("notepad")

        assert launcher_with_apps._launch_count == 2

    @patch("subprocess.Popen")
    def test_launch_app_tracks_pid(self, mock_popen, launcher_with_apps):
        mock_process = MagicMock()
        mock_process.pid = 5678
        mock_popen.return_value = mock_process

        launcher_with_apps.launch("firefox")

        assert "firefox" in launcher_with_apps._running_pids
        assert 5678 in launcher_with_apps._running_pids["firefox"]

    def test_launch_app_not_found(self, launcher_with_apps):
        with pytest.raises(AutomationError, match="Application not found"):
            launcher_with_apps.launch("nonexistent_app")

    @patch("subprocess.Popen")
    def test_launch_app_error(self, mock_popen, launcher_with_apps):
        mock_popen.side_effect = RuntimeError("failed to spawn")

        with pytest.raises(AutomationError, match="Failed to launch"):
            launcher_with_apps.launch("chrome")

    def test_launch_bengali_app_name(self, launcher_with_apps):
        """Bengali app names should be translated."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 9999
            mock_popen.return_value = mock_process

            # "ক্রোম" is Bengali for "chrome"
            launcher_with_apps.launch("ক্রোম")

            # Should have launched chrome
            mock_popen.assert_called_once()

    @patch("os.startfile")
    def test_launch_url_scheme(self, mock_startfile, launcher_with_apps):
        """URL schemes like 'ms-settings:' should be handled specially."""
        launcher_with_apps._apps["settings"] = "ms-settings:"
        launcher_with_apps.launch("settings")

        mock_startfile.assert_called_once_with("ms-settings:")

    @patch("subprocess.Popen")
    def test_launch_auto_discovers(self, mock_popen, launcher):
        """If apps not discovered, launch should discover them first."""
        mock_process = MagicMock()
        mock_process.pid = 1111
        mock_popen.return_value = mock_process

        with patch.object(launcher, "_scan_registry"):
            with patch.object(launcher, "_scan_common_paths"):
                launcher.launch("notepad")

        assert launcher._discovered is True


# ======================================================================
# Finding Apps
# ======================================================================


class TestFindingApps:
    """Test _find_app."""

    def test_find_app_exact_match(self, launcher_with_apps):
        path = launcher_with_apps._find_app("chrome")
        assert path == "C:\\Program Files\\Google\\Chrome\\chrome.exe"

    def test_find_app_case_insensitive(self, launcher_with_apps):
        path = launcher_with_apps._find_app("CHROME")
        assert path == "C:\\Program Files\\Google\\Chrome\\chrome.exe"

    def test_find_app_partial_match(self, launcher_with_apps):
        # Add an app with a longer name
        launcher_with_apps._apps["google chrome"] = "/path/to/chrome"

        path = launcher_with_apps._find_app("chrome")
        # Should find either chrome or google chrome
        assert path is not None

    def test_find_app_not_found(self, launcher_with_apps):
        path = launcher_with_apps._find_app("nonexistent")
        assert path is None

    def test_translate_app_name(self, launcher):
        assert launcher._translate_app_name("ক্রোম") == "chrome"
        assert launcher._translate_app_name("notepad") == "notepad"


# ======================================================================
# Process Management
# ======================================================================


class TestProcessManagement:
    """Test is_running, close, process tracking."""

    @patch("subprocess.run")
    def test_is_running_true(self, mock_run, launcher_with_apps):
        mock_run.return_value.stdout = "1234"
        launcher_with_apps._running_pids["chrome"] = [1234]

        result = launcher_with_apps.is_running("chrome")

        assert result is True

    @patch("subprocess.run")
    def test_is_running_false(self, mock_run, launcher_with_apps):
        mock_run.return_value.stdout = ""
        launcher_with_apps._running_pids["chrome"] = [9999]

        result = launcher_with_apps.is_running("chrome")

        assert result is False

    def test_is_running_not_tracked(self, launcher_with_apps):
        result = launcher_with_apps.is_running("unknown_app")
        assert result is False

    @patch("subprocess.run")
    def test_close_app(self, mock_run, launcher_with_apps):
        launcher_with_apps._running_pids["chrome"] = [1234]

        result = launcher_with_apps.close("chrome")

        assert result is True
        mock_run.assert_called_once()
        # PIDs should be cleared
        assert launcher_with_apps._running_pids["chrome"] == []

    def test_close_app_not_tracked(self, launcher_with_apps):
        result = launcher_with_apps.close("unknown_app")
        assert result is False

    @patch("subprocess.run")
    def test_close_app_error_continues(self, mock_run, launcher_with_apps):
        """If close fails for one PID, should continue to others."""
        mock_run.side_effect = RuntimeError("taskkill failed")

        launcher_with_apps._running_pids["chrome"] = [1234, 5678]

        result = launcher_with_apps.close("chrome")

        # Should still return True and try both PIDs
        assert result is True
        assert mock_run.call_count == 2

    def test_is_pid_running_success(self, launcher):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "1234 cmd.exe"
            result = launcher._is_pid_running(1234)
            assert result is True

    def test_is_pid_running_not_found(self, launcher):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = ""
            result = launcher._is_pid_running(9999)
            assert result is False

    def test_is_pid_running_error(self, launcher):
        with patch("subprocess.run", side_effect=RuntimeError("error")):
            result = launcher._is_pid_running(1234)
            assert result is False


# ======================================================================
# Query
# ======================================================================


class TestQuery:
    """Test get_available_apps, get_app_path."""

    def test_get_available_apps_with_discovery(self, launcher_with_apps):
        apps = launcher_with_apps.get_available_apps()

        assert isinstance(apps, list)
        assert len(apps) > 0
        assert "chrome" in apps
        assert "notepad" in apps

    def test_get_available_apps_triggers_discovery(self, launcher):
        with patch.object(launcher, "discover_apps") as mock_discover:
            launcher.get_available_apps()
            mock_discover.assert_called_once()

    def test_get_available_apps_sorted(self, launcher_with_apps):
        apps = launcher_with_apps.get_available_apps()

        # Should be sorted
        assert apps == sorted(apps)

    def test_get_app_path(self, launcher_with_apps):
        path = launcher_with_apps.get_app_path("chrome")
        assert path == "C:\\Program Files\\Google\\Chrome\\chrome.exe"

    def test_get_app_path_not_found(self, launcher_with_apps):
        path = launcher_with_apps.get_app_path("nonexistent")
        assert path is None

    def test_get_app_path_triggers_discovery(self, launcher):
        with patch.object(launcher, "discover_apps") as mock_discover:
            launcher.get_app_path("chrome")
            mock_discover.assert_called_once()


# ======================================================================
# Status
# ======================================================================


class TestStatus:
    """Test get_status."""

    def test_status_keys(self, launcher_with_apps):
        status = launcher_with_apps.get_status()

        expected_keys = {
            "discovered",
            "app_count",
            "running_apps",
            "launch_count",
        }
        assert set(status.keys()) == expected_keys

    def test_status_values(self, launcher_with_apps):
        launcher_with_apps._launch_count = 5
        launcher_with_apps._running_pids["chrome"] = [1234]

        status = launcher_with_apps.get_status()

        assert status["discovered"] is True
        assert status["app_count"] == 4  # chrome, notepad, firefox, calc
        assert "chrome" in status["running_apps"]
        assert status["launch_count"] == 5

    @patch("subprocess.run")
    def test_status_filters_dead_pids(self, mock_run, launcher_with_apps):
        """Dead PIDs should not be listed in running_apps."""
        mock_run.return_value.stdout = ""  # PID not found

        launcher_with_apps._running_pids["chrome"] = [9999]

        status = launcher_with_apps.get_status()

        assert "chrome" not in status["running_apps"]

    def test_status_empty_running_apps(self, launcher_with_apps):
        status = launcher_with_apps.get_status()

        assert status["running_apps"] == []


# ======================================================================
# Edge Cases
# ======================================================================


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_launch_empty_app_name(self, launcher_with_apps):
        with pytest.raises(AutomationError):
            launcher_with_apps.launch("")

    def test_launch_whitespace_app_name(self, launcher_with_apps):
        with pytest.raises(AutomationError):
            launcher_with_apps.launch("   ")

    def test_find_app_empty_string(self, launcher_with_apps):
        result = launcher_with_apps._find_app("")
        assert result is None

    def test_get_available_apps_empty(self, launcher):
        launcher._discovered = True
        launcher._apps = {}

        apps = launcher.get_available_apps()

        assert apps == []

    def test_close_multiple_pids(self, launcher_with_apps):
        with patch("subprocess.run") as mock_run:
            launcher_with_apps._running_pids["chrome"] = [1111, 2222, 3333]

            launcher_with_apps.close("chrome")

            # Should call taskkill for each PID
            assert mock_run.call_count == 3

    def test_is_running_cleans_dead_pids(self, launcher_with_apps):
        """Dead PIDs should be removed from tracking."""
        with patch("subprocess.run") as mock_run:
            # First PID alive, second dead
            mock_run.side_effect = [
                MagicMock(stdout="1234"),
                MagicMock(stdout=""),
            ]

            launcher_with_apps._running_pids["chrome"] = [1234, 5555]
            launcher_with_apps.is_running("chrome")

            # After cleanup, only alive PID should remain
            assert 5555 not in launcher_with_apps._running_pids["chrome"]


# ======================================================================
# Concurrent Access
# ======================================================================


class TestConcurrentAccess:
    """Test thread-safe discovery."""

    @patch("subprocess.run")
    def test_discover_apps_thread_safe(self, mock_run, launcher):
        """Concurrent discovery attempts should be serialized."""
        import threading

        results = []

        def discover():
            with patch.object(launcher, "_scan_registry"):
                with patch.object(launcher, "_scan_common_paths"):
                    count = launcher.discover_apps()
                    results.append(count)

        threads = [threading.Thread(target=discover) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results should be the same
        assert len(set(results)) == 1


__all__ = []
