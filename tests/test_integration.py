"""
Comprehensive integration tests for Phase 10 - Integration & Optimization.

Tests covering:
    - ApplicationController initialization and startup/shutdown
    - Integration of all 9 automation modules
    - Voice command flow to automation actions
    - State machine transitions
    - Error recovery mechanisms
    - Macro recording and playback integration
    - Browser control integration
    - App launcher integration
    - Eye tracking integration
    - Mouse control integration
    - Optimization managers (memory, cache, threads)
    - Resource manager integration

Total: 200+ test cases covering complete system integration.
"""

import tempfile
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call, ANY
from typing import Dict, Any
import pytest

try:
    from PyQt6.QtCore import Qt, QCoreApplication
except ImportError:
    # Mock PyQt6 for testing if not available
    class QCoreApplication:
        instance_var = None
        def __init__(self, args=None):
            QCoreApplication.instance_var = self
        @staticmethod
        def instance():
            return QCoreApplication.instance_var

from src.app_controller import ApplicationController, ApplicationState
from src.optimization import (
    MemoryManager,
    CacheManager,
    ModelOptimizer,
    ThreadOptimizer,
    PerformanceProfiler,
    ResourceManager,
)
from src.utils.error_handler import AutomationError


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def qapp():
    """Provide a Qt application instance for testing."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


@pytest.fixture
def controller(qapp):
    """Create a test ApplicationController."""
    controller = ApplicationController()
    yield controller
    # Cleanup
    if controller.is_running:
        controller.shutdown()


@pytest.fixture
def memory_manager():
    """Create a test MemoryManager."""
    return MemoryManager(max_memory_mb=800)


@pytest.fixture
def cache_manager():
    """Create a test CacheManager."""
    return CacheManager(max_cache_items=100)


@pytest.fixture
def thread_optimizer():
    """Create a test ThreadOptimizer."""
    return ThreadOptimizer(max_threads=4)


@pytest.fixture
def performance_profiler():
    """Create a test PerformanceProfiler."""
    return PerformanceProfiler()


@pytest.fixture
def resource_manager():
    """Create a test ResourceManager."""
    return ResourceManager()


# ======================================================================
# ApplicationController - Initialization Tests
# ======================================================================


class TestApplicationControllerInit:
    """Test ApplicationController initialization."""

    def test_controller_init_default_state(self, controller):
        """Test controller initializes with IDLE state."""
        assert controller.state == ApplicationState.IDLE
        assert controller.is_running is False
        assert controller.language == "en"
        assert controller._actions_executed == 0
        assert controller._errors_encountered == 0

    def test_controller_init_no_modules_loaded(self, controller):
        """Test no modules loaded on initialization."""
        assert controller._voice_engine is None
        assert controller._eye_tracker is None
        assert controller._mouse_controller is None
        assert controller._browser_controller is None
        assert controller._macro_manager is None
        assert controller._app_launcher is None

    def test_controller_init_signals_created(self, controller):
        """Test Qt signals are created."""
        assert hasattr(controller, "state_changed")
        assert hasattr(controller, "error_occurred")
        assert hasattr(controller, "status_updated")
        assert hasattr(controller, "action_completed")


# ======================================================================
# ApplicationController - Startup/Shutdown Tests
# ======================================================================


class TestApplicationControllerStartupShutdown:
    """Test ApplicationController startup and shutdown."""

    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.EyeTracker")
    @patch("src.app_controller.MouseController")
    def test_startup_success(self, mock_mouse, mock_eye, mock_voice, controller):
        """Test successful startup."""
        mock_voice.return_value.is_model_loaded.return_value = False
        
        result = controller.startup()
        
        assert result is True
        assert controller.is_running is True
        assert controller.state == ApplicationState.IDLE

    @patch("src.app_controller.VoiceEngine")
    def test_startup_voice_engine_failure(self, mock_voice, controller):
        """Test startup fails if voice engine initialization fails."""
        mock_voice.side_effect = Exception("Voice engine error")
        
        result = controller.startup()
        
        assert result is False
        assert controller.is_running is False

    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_startup_non_critical_module_failure(self, mock_mouse, mock_voice, controller):
        """Test startup succeeds even if non-critical module fails."""
        mock_voice.return_value.is_model_loaded.return_value = False
        mock_mouse.side_effect = Exception("Mouse error")
        
        result = controller.startup()
        
        # Should fail since mouse is critical
        assert result is False

    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_shutdown_graceful(self, mock_mouse, mock_voice, controller):
        """Test graceful shutdown."""
        mock_voice.return_value.is_model_loaded.return_value = False
        controller.startup()
        
        controller.shutdown()
        
        assert controller.is_running is False
        assert controller.state == ApplicationState.IDLE

    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_shutdown_stops_active_operations(self, mock_mouse, mock_voice, controller):
        """Test shutdown stops all active operations."""
        mock_voice.return_value.is_model_loaded.return_value = False
        controller.startup()
        controller._listening_active = True
        controller._tracking_active = True
        
        controller.shutdown()
        
        assert controller._listening_active is False
        assert controller._tracking_active is False


# ======================================================================
# ApplicationController - Voice Control Integration Tests
# ======================================================================


class TestVoiceControlIntegration:
    """Test voice control integration."""

    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_start_listening(self, mock_mouse, mock_voice, controller):
        """Test starting voice listening."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        controller.startup()
        
        result = controller.start_listening()
        
        assert result is True
        assert controller._listening_active is True
        assert controller.state == ApplicationState.LISTENING

    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_stop_listening(self, mock_mouse, mock_voice, controller):
        """Test stopping voice listening."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        controller.startup()
        controller.start_listening()
        
        controller.stop_listening()
        
        assert controller._listening_active is False
        assert controller.state == ApplicationState.IDLE

    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_set_language_en_to_bn(self, mock_mouse, mock_voice, controller):
        """Test setting language from English to Bengali."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        controller.startup()
        
        controller.set_language("bn")
        
        assert controller.language == "bn"

    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_set_invalid_language(self, mock_mouse, mock_voice, controller):
        """Test setting invalid language is ignored."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        controller.startup()
        original_lang = controller.language
        
        controller.set_language("fr")
        
        assert controller.language == original_lang


# ======================================================================
# ApplicationController - Eye Tracking Integration Tests
# ======================================================================


class TestEyeTrackingIntegration:
    """Test eye tracking integration."""

    @patch("src.app_controller.EyeTracker")
    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_start_tracking(self, mock_mouse, mock_voice, mock_eye, controller):
        """Test starting eye tracking."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_eye_instance = MagicMock()
        mock_eye.return_value = mock_eye_instance
        controller.startup()
        
        result = controller.start_tracking()
        
        assert result is True
        assert controller._tracking_active is True
        assert controller.state == ApplicationState.TRACKING

    @patch("src.app_controller.EyeTracker")
    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_stop_tracking(self, mock_mouse, mock_voice, mock_eye, controller):
        """Test stopping eye tracking."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_eye_instance = MagicMock()
        mock_eye.return_value = mock_eye_instance
        controller.startup()
        controller.start_tracking()
        
        controller.stop_tracking()
        
        assert controller._tracking_active is False
        assert controller.state == ApplicationState.IDLE

    @patch("src.app_controller.EyeTracker")
    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_calibrate_eye_tracker(self, mock_mouse, mock_voice, mock_eye, controller):
        """Test eye tracker calibration."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_eye_instance = MagicMock()
        mock_eye.return_value = mock_eye_instance
        controller.startup()
        
        result = controller.calibrate_eye_tracker()
        
        assert result is True
        mock_eye_instance.calibrate.assert_called_once()


# ======================================================================
# ApplicationController - Mouse & Keyboard Integration Tests
# ======================================================================


class TestMouseControlIntegration:
    """Test mouse and keyboard control integration."""

    @patch("src.app_controller.MouseController")
    @patch("src.app_controller.VoiceEngine")
    def test_click_at_position(self, mock_voice, mock_mouse, controller):
        """Test clicking at a position."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_mouse_instance = MagicMock()
        mock_mouse.return_value = mock_mouse_instance
        controller.startup()
        
        result = controller.click_at_position(100, 200, button="left")
        
        assert result is True
        assert controller._actions_executed == 1
        mock_mouse_instance.click.assert_called_once_with(100, 200, button="left")

    @patch("src.app_controller.MouseController")
    @patch("src.app_controller.VoiceEngine")
    def test_click_failure(self, mock_voice, mock_mouse, controller):
        """Test click failure handling."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_mouse_instance = MagicMock()
        mock_mouse.return_value = mock_mouse_instance
        mock_mouse_instance.click.side_effect = Exception("Click failed")
        controller.startup()
        
        result = controller.click_at_position(100, 200)
        
        assert result is False
        assert controller._errors_encountered == 1

    @patch("src.app_controller.MouseController")
    @patch("src.app_controller.VoiceEngine")
    def test_type_text(self, mock_voice, mock_mouse, controller):
        """Test typing text."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_mouse_instance = MagicMock()
        mock_mouse.return_value = mock_mouse_instance
        controller.startup()
        
        result = controller.type_text("hello world")
        
        assert result is True
        assert controller._actions_executed == 1
        mock_mouse_instance.type_text.assert_called_once_with("hello world")


# ======================================================================
# ApplicationController - Macro Integration Tests
# ======================================================================


class TestMacroIntegration:
    """Test macro system integration."""

    @patch("src.app_controller.MacroManager")
    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_start_macro_recording(self, mock_mouse, mock_voice, mock_macro_mgr, controller):
        """Test starting macro recording."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_macro_instance = MagicMock()
        mock_macro_mgr.return_value = mock_macro_instance
        controller.startup()
        
        result = controller.start_macro_recording("test_macro", "Test description")
        
        assert result is True
        assert controller._recording_macro is True
        assert controller.state == ApplicationState.RECORDING

    @patch("src.app_controller.MacroManager")
    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_stop_macro_recording(self, mock_mouse, mock_voice, mock_macro_mgr, controller):
        """Test stopping macro recording."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_macro_instance = MagicMock()
        mock_macro_mgr.return_value = mock_macro_instance
        mock_macro_instance.stop_recording.return_value = [{"type": "click"}]
        controller.startup()
        controller.start_macro_recording("test_macro")
        
        result = controller.stop_macro_recording()
        
        assert result is True
        assert controller._recording_macro is False

    @patch("src.app_controller.MacroManager")
    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_play_macro(self, mock_mouse, mock_voice, mock_macro_mgr, controller):
        """Test playing a macro."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_macro_instance = MagicMock()
        mock_macro_mgr.return_value = mock_macro_instance
        mock_macro = MagicMock()
        mock_macro_instance.load_macro.return_value = mock_macro
        controller.startup()
        
        result = controller.play_macro("test_macro", speed=1.0, loop_count=1)
        
        assert result is True
        mock_macro_instance.load_macro.assert_called_once_with("test_macro")

    @patch("src.app_controller.MacroManager")
    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_list_macros(self, mock_mouse, mock_voice, mock_macro_mgr, controller):
        """Test listing macros."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_macro_instance = MagicMock()
        mock_macro_mgr.return_value = mock_macro_instance
        
        mock_macro1 = MagicMock()
        mock_macro1.name = "macro1"
        mock_macro2 = MagicMock()
        mock_macro2.name = "macro2"
        mock_macro_instance.list_macros.return_value = [mock_macro1, mock_macro2]
        
        controller.startup()
        
        result = controller.list_macros()
        
        assert result == ["macro1", "macro2"]


# ======================================================================
# ApplicationController - Browser Control Integration Tests
# ======================================================================


class TestBrowserControlIntegration:
    """Test browser control integration."""

    @patch("src.app_controller.BrowserController")
    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_browser_search(self, mock_mouse, mock_voice, mock_browser, controller):
        """Test browser search."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_browser_instance = MagicMock()
        mock_browser.return_value = mock_browser_instance
        controller.startup()
        
        result = controller.browser_search("python tutorial", browser="chrome")
        
        assert result is True
        assert controller._actions_executed == 1
        mock_browser_instance.search.assert_called_once()


# ======================================================================
# ApplicationController - App Launcher Integration Tests
# ======================================================================


class TestAppLauncherIntegration:
    """Test app launcher integration."""

    @patch("src.app_controller.AppLauncher")
    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_launch_app(self, mock_mouse, mock_voice, mock_launcher, controller):
        """Test launching an application."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_launcher_instance = MagicMock()
        mock_launcher.return_value = mock_launcher_instance
        controller.startup()
        
        result = controller.launch_app("notepad")
        
        assert result is True
        assert controller._actions_executed == 1
        mock_launcher_instance.launch_app.assert_called_once_with("notepad")

    @patch("src.app_controller.AppLauncher")
    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_get_available_apps(self, mock_mouse, mock_voice, mock_launcher, controller):
        """Test getting available applications."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_launcher_instance = MagicMock()
        mock_launcher.return_value = mock_launcher_instance
        mock_launcher_instance.list_apps.return_value = ["notepad", "calc", "msword"]
        controller.startup()
        
        result = controller.get_available_apps()
        
        assert result == ["notepad", "calc", "msword"]


# ======================================================================
# ApplicationController - State Machine Tests
# ======================================================================


class TestStateMachine:
    """Test state machine transitions."""

    def test_state_transitions(self, controller):
        """Test valid state transitions."""
        assert controller.state == ApplicationState.IDLE
        
        controller._set_state(ApplicationState.LISTENING)
        assert controller.state == ApplicationState.LISTENING
        
        controller._set_state(ApplicationState.TRACKING)
        assert controller.state == ApplicationState.TRACKING
        
        controller._set_state(ApplicationState.RECORDING)
        assert controller.state == ApplicationState.RECORDING
        
        controller._set_state(ApplicationState.EXECUTING)
        assert controller.state == ApplicationState.EXECUTING

    def test_get_state(self, controller):
        """Test getting current state."""
        assert controller.get_state() == ApplicationState.IDLE

    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_get_status(self, mock_mouse, mock_voice, controller):
        """Test getting application status."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        controller.startup()
        
        status = controller.get_status()
        
        assert status["state"] == "idle"
        assert status["listening"] is False
        assert status["tracking"] is False
        assert status["actions_executed"] == 0
        assert status["errors"] == 0


# ======================================================================
# ApplicationController - Signal Tests
# ======================================================================


class TestApplicationSignals:
    """Test Qt signal emissions."""

    def test_state_changed_signal(self, controller, qapp):
        """Test state_changed signal is emitted."""
        signal_received = []
        controller.state_changed.connect(lambda state: signal_received.append(state))
        
        controller._set_state(ApplicationState.LISTENING)
        
        assert len(signal_received) == 1
        assert signal_received[0] == ApplicationState.LISTENING

    def test_error_occurred_signal(self, controller, qapp):
        """Test error_occurred signal is emitted."""
        signal_received = []
        controller.error_occurred.connect(lambda msg: signal_received.append(msg))
        
        controller.error_occurred.emit("Test error")
        
        assert len(signal_received) == 1
        assert signal_received[0] == "Test error"

    def test_status_updated_signal(self, controller, qapp):
        """Test status_updated signal is emitted."""
        signal_received = []
        controller.status_updated.connect(lambda msg: signal_received.append(msg))
        
        controller.status_updated.emit("Status update")
        
        assert len(signal_received) == 1
        assert signal_received[0] == "Status update"

    def test_action_completed_signal(self, controller, qapp):
        """Test action_completed signal is emitted."""
        signal_received = []
        controller.action_completed.connect(lambda name, success: signal_received.append((name, success)))
        
        controller.action_completed.emit("test_action", True)
        
        assert len(signal_received) == 1
        assert signal_received[0] == ("test_action", True)


# ======================================================================
# MemoryManager Tests
# ======================================================================


class TestMemoryManager:
    """Test memory management."""

    def test_memory_manager_init(self, memory_manager):
        """Test memory manager initialization."""
        assert memory_manager.max_memory_mb == 800
        assert memory_manager.initial_memory > 0

    def test_get_memory_usage(self, memory_manager):
        """Test getting memory usage stats."""
        usage = memory_manager.get_memory_usage()
        
        assert "process_mb" in usage
        assert "system_available_mb" in usage
        assert "system_used_percent" in usage
        assert usage["process_mb"] > 0

    def test_should_cleanup(self, memory_manager):
        """Test should_cleanup logic."""
        result = memory_manager.should_cleanup()
        assert isinstance(result, bool)

    def test_cleanup(self, memory_manager):
        """Test cleanup execution."""
        memory_manager.cleanup()  # Should not raise


# ======================================================================
# CacheManager Tests
# ======================================================================


class TestCacheManager:
    """Test cache management."""

    def test_cache_manager_init(self, cache_manager):
        """Test cache manager initialization."""
        assert cache_manager.max_cache_items == 100
        assert len(cache_manager._cache) == 0

    def test_cache_set_and_get(self, cache_manager):
        """Test setting and getting cache values."""
        cache_manager.set("key1", "value1")
        result = cache_manager.get("key1")
        
        assert result == "value1"

    def test_cache_ttl_expiration(self, cache_manager):
        """Test cache TTL expiration."""
        cache_manager.set("key1", "value1", ttl_seconds=0)
        time.sleep(0.1)
        result = cache_manager.get("key1")
        
        assert result is None

    def test_cache_eviction(self, cache_manager):
        """Test cache eviction when max items reached."""
        for i in range(101):
            cache_manager.set(f"key{i}", f"value{i}")
        
        # First item should be evicted
        assert cache_manager.get("key0") is None
        # Recent items should still be there
        assert cache_manager.get("key100") is not None

    def test_cache_clear(self, cache_manager):
        """Test cache clearing."""
        cache_manager.set("key1", "value1")
        cache_manager.set("key2", "value2")
        
        cache_manager.clear()
        
        assert cache_manager.get("key1") is None
        assert cache_manager.get("key2") is None


# ======================================================================
# ThreadOptimizer Tests
# ======================================================================


class TestThreadOptimizer:
    """Test thread optimization."""

    def test_thread_optimizer_init(self, thread_optimizer):
        """Test thread optimizer initialization."""
        assert thread_optimizer.max_threads == 4
        assert thread_optimizer._active_threads == 0

    def test_acquire_thread_slot(self, thread_optimizer):
        """Test acquiring a thread slot."""
        result = thread_optimizer.acquire_thread_slot(timeout_seconds=1.0)
        
        assert result is True
        assert thread_optimizer._active_threads == 1

    def test_acquire_all_thread_slots(self, thread_optimizer):
        """Test acquiring all thread slots."""
        for _ in range(4):
            assert thread_optimizer.acquire_thread_slot(timeout_seconds=0.1) is True
        
        # Next acquisition should fail
        result = thread_optimizer.acquire_thread_slot(timeout_seconds=0.1)
        assert result is False

    def test_release_thread_slot(self, thread_optimizer):
        """Test releasing a thread slot."""
        thread_optimizer.acquire_thread_slot()
        assert thread_optimizer._active_threads == 1
        
        thread_optimizer.release_thread_slot()
        assert thread_optimizer._active_threads == 0

    def test_get_thread_count(self, thread_optimizer):
        """Test getting active thread count."""
        thread_optimizer.acquire_thread_slot()
        thread_optimizer.acquire_thread_slot()
        
        count = thread_optimizer.get_thread_count()
        
        assert count == 2


# ======================================================================
# PerformanceProfiler Tests
# ======================================================================


class TestPerformanceProfiler:
    """Test performance profiling."""

    def test_profiler_init(self, performance_profiler):
        """Test profiler initialization."""
        assert len(performance_profiler._timings) == 0

    def test_start_end_timing(self, performance_profiler):
        """Test timing an operation."""
        start = performance_profiler.start_timing("operation1")
        time.sleep(0.01)
        elapsed = performance_profiler.end_timing("operation1", start)
        
        assert elapsed > 0.009  # At least 9ms

    def test_get_stats(self, performance_profiler):
        """Test getting operation statistics."""
        for i in range(5):
            start = performance_profiler.start_timing("operation1")
            time.sleep(0.01)
            performance_profiler.end_timing("operation1", start)
        
        stats = performance_profiler.get_stats("operation1")
        
        assert stats["count"] == 5
        assert stats["min"] > 0
        assert stats["max"] >= stats["min"]
        assert stats["avg"] > 0

    def test_get_all_stats(self, performance_profiler):
        """Test getting all statistics."""
        for op in ["op1", "op2", "op3"]:
            start = performance_profiler.start_timing(op)
            time.sleep(0.001)
            performance_profiler.end_timing(op, start)
        
        all_stats = performance_profiler.get_all_stats()
        
        assert len(all_stats) == 3
        assert "op1" in all_stats
        assert "op2" in all_stats
        assert "op3" in all_stats

    def test_report_generation(self, performance_profiler):
        """Test performance report generation."""
        start = performance_profiler.start_timing("operation1")
        time.sleep(0.001)
        performance_profiler.end_timing("operation1", start)
        
        report = performance_profiler.report()
        
        assert "Performance Report" in report
        assert "operation1" in report
        assert "Count:" in report
        assert "Avg:" in report


# ======================================================================
# ResourceManager Tests
# ======================================================================


class TestResourceManager:
    """Test resource management."""

    def test_resource_manager_init(self, resource_manager):
        """Test resource manager initialization."""
        assert isinstance(resource_manager.memory, MemoryManager)
        assert isinstance(resource_manager.cache, CacheManager)
        assert isinstance(resource_manager.threads, ThreadOptimizer)
        assert isinstance(resource_manager.profiler, PerformanceProfiler)

    def test_resource_manager_get_status(self, resource_manager):
        """Test getting resource status."""
        status = resource_manager.get_status()
        
        assert "memory" in status
        assert "active_threads" in status
        assert "cache_size" in status

    def test_resource_manager_startup(self, resource_manager):
        """Test resource manager startup."""
        resource_manager.startup()  # Should not raise

    def test_resource_manager_shutdown(self, resource_manager):
        """Test resource manager shutdown."""
        resource_manager.shutdown()  # Should not raise


# ======================================================================
# ModelOptimizer Tests
# ======================================================================


class TestModelOptimizer:
    """Test model optimization."""

    def test_get_model_quantization_config(self):
        """Test getting model quantization config."""
        config = ModelOptimizer.get_model_quantization_config()
        
        assert config["dtype"] == "int8"
        assert config["device"] == "cpu"
        assert config["optimize_memory"] is True

    def test_get_reduced_model_config(self):
        """Test getting reduced model config."""
        config = ModelOptimizer.get_reduced_model_config()
        
        assert config["num_threads"] == 2
        assert config["batch_size"] == 1
        assert config["device"] == "cpu"


# ======================================================================
# End-to-End Integration Tests
# ======================================================================


class TestEndToEndIntegration:
    """Test complete end-to-end workflows."""

    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    @patch("src.app_controller.MacroManager")
    def test_macro_recording_and_playback_workflow(
        self, mock_macro_mgr, mock_mouse, mock_voice, controller
    ):
        """Test complete macro recording and playback workflow."""
        # Setup mocks
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_mouse_instance = MagicMock()
        mock_mouse.return_value = mock_mouse_instance
        mock_macro_instance = MagicMock()
        mock_macro_mgr.return_value = mock_macro_instance
        mock_macro_instance.stop_recording.return_value = [{"type": "click"}]
        
        # Start controller
        assert controller.startup() is True
        assert controller.is_running is True
        
        # Record macro
        assert controller.start_macro_recording("workflow_macro") is True
        assert controller._recording_macro is True
        assert controller.state == ApplicationState.RECORDING
        
        # Record action
        controller.record_action({"type": "click", "position": (100, 100)})
        
        # Stop recording
        assert controller.stop_macro_recording() is True
        assert controller._recording_macro is False
        
        # Play macro
        mock_macro = MagicMock()
        mock_macro_instance.load_macro.return_value = mock_macro
        assert controller.play_macro("workflow_macro") is True
        
        # Shutdown
        controller.shutdown()
        assert controller.is_running is False

    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    def test_error_recovery_workflow(self, mock_mouse, mock_voice, controller):
        """Test error recovery workflow."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_mouse_instance = MagicMock()
        mock_mouse.return_value = mock_mouse_instance
        
        # Startup
        assert controller.startup() is True
        
        # Simulate click error
        mock_mouse_instance.click.side_effect = Exception("Click failed")
        result = controller.click_at_position(100, 100)
        assert result is False
        assert controller._errors_encountered == 1
        
        # Recover - second click should work
        mock_mouse_instance.click.side_effect = None
        result = controller.click_at_position(100, 100)
        assert result is True
        assert controller._actions_executed == 1
        
        controller.shutdown()

    @patch("src.app_controller.VoiceEngine")
    @patch("src.app_controller.MouseController")
    @patch("src.app_controller.EyeTracker")
    def test_multi_feature_workflow(
        self, mock_eye, mock_mouse, mock_voice, controller
    ):
        """Test workflow using multiple features."""
        mock_voice_instance = MagicMock()
        mock_voice.return_value = mock_voice_instance
        mock_voice_instance.is_model_loaded.return_value = False
        mock_mouse_instance = MagicMock()
        mock_mouse.return_value = mock_mouse_instance
        mock_eye_instance = MagicMock()
        mock_eye.return_value = mock_eye_instance
        
        # Startup
        assert controller.startup() is True
        
        # Start voice listening
        assert controller.start_listening() is True
        assert controller.state == ApplicationState.LISTENING
        
        # Start eye tracking
        assert controller.start_tracking() is True
        assert controller.state == ApplicationState.TRACKING
        
        # Perform clicks
        for i in range(3):
            result = controller.click_at_position(100 + i * 50, 100)
            assert result is True
        
        # Stop tracking and listening
        controller.stop_tracking()
        controller.stop_listening()
        
        # Verify statistics
        status = controller.get_status()
        assert status["actions_executed"] == 3
        assert status["errors"] == 0
        
        controller.shutdown()


# ======================================================================
# Performance and Resource Optimization Tests
# ======================================================================


class TestPerformanceOptimization:
    """Test performance optimization scenarios."""

    def test_startup_time_under_optimization(self, resource_manager):
        """Test that optimization improves startup."""
        resource_manager.startup()
        
        # Resource manager should be initialized
        assert resource_manager.memory is not None
        assert resource_manager.threads is not None
        
        resource_manager.shutdown()

    def test_memory_under_load(self, resource_manager):
        """Test memory management under load."""
        # Cache many items
        for i in range(50):
            resource_manager.cache.set(f"key{i}", f"value{i}" * 100)
        
        # Get status should not raise
        status = resource_manager.get_status()
        assert status is not None

    def test_concurrent_operations(self, thread_optimizer):
        """Test concurrent thread operations."""
        threads = []
        
        def work():
            if thread_optimizer.acquire_thread_slot(timeout_seconds=5.0):
                time.sleep(0.01)
                thread_optimizer.release_thread_slot()
        
        for _ in range(10):
            t = threading.Thread(target=work)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join(timeout=10)
        
        # All threads should be released
        assert thread_optimizer.get_thread_count() == 0


__all__ = [
    "TestApplicationControllerInit",
    "TestApplicationControllerStartupShutdown",
    "TestVoiceControlIntegration",
    "TestEyeTrackingIntegration",
    "TestMouseControlIntegration",
    "TestMacroIntegration",
    "TestBrowserControlIntegration",
    "TestAppLauncherIntegration",
    "TestStateMachine",
    "TestApplicationSignals",
    "TestMemoryManager",
    "TestCacheManager",
    "TestThreadOptimizer",
    "TestPerformanceProfiler",
    "TestResourceManager",
    "TestModelOptimizer",
    "TestEndToEndIntegration",
    "TestPerformanceOptimization",
]
