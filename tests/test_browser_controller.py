"""
Tests for src.automation.browser_controller.

These tests verify the BrowserController's public API without requiring
a real browser or Selenium. The WebDriver is fully mocked.
"""

from unittest.mock import MagicMock, PropertyMock, patch, call
from typing import Any, List

import pytest

from src.utils.error_handler import AutomationError


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch):
    """Supply sensible config defaults."""
    from src.utils.config_manager import ConfigManager

    defaults = {
        "browser.driver": "chrome",
        "browser.headless": False,
        "browser.implicit_wait": 10,
        "browser.page_load_timeout": 30,
    }

    original_get = ConfigManager.get

    def patched_get(self_or_key, key=None, default=None):
        if key is None:
            lookup_key = self_or_key
            fallback = default
        else:
            lookup_key = key
            fallback = default

        if lookup_key in defaults:
            return defaults[lookup_key]
        return fallback

    monkeypatch.setattr(ConfigManager, "get", patched_get)


@pytest.fixture()
def mock_webdriver():
    """Create a mock Selenium WebDriver."""
    mock = MagicMock()
    mock.window_handles = ["handle1", "handle2"]
    mock.current_url = "https://example.com"
    mock.title = "Example Domain"
    mock.page_source = "<html>...</html>"
    return mock


@pytest.fixture()
def controller(mock_webdriver, monkeypatch):
    """Return a BrowserController with WebDriver pre-injected."""
    from src.automation.browser_controller import BrowserController

    ctrl = BrowserController(driver="chrome", headless=False)
    ctrl._driver = mock_webdriver
    return ctrl


@pytest.fixture()
def controller_no_driver():
    """Return a BrowserController that has NOT loaded WebDriver yet."""
    from src.automation.browser_controller import BrowserController

    return BrowserController()


# ======================================================================
# Lazy Loading
# ======================================================================


class TestLazyLoading:
    """Test WebDriver lazy loading."""

    def test_driver_none_initially(self, controller_no_driver):
        assert controller_no_driver._driver is None

    def test_ensure_driver_initializes(self, controller_no_driver, monkeypatch):
        """Test that _ensure_driver initializes the driver."""
        mock_driver = MagicMock()
        mock_driver.implicitly_wait = MagicMock()
        mock_driver.set_page_load_timeout = MagicMock()

        def mock_chrome(*args, **kwargs):
            return mock_driver

        # Patch the webdriver.Chrome import
        with patch("selenium.webdriver.Chrome", mock_chrome):
            with patch("webdriver_manager.chrome.ChromeDriverManager"):
                controller_no_driver._ensure_driver()

        assert controller_no_driver._driver is not None

    def test_ensure_driver_idempotent(self, controller, mock_webdriver):
        """Calling _ensure_driver twice should not re-create."""
        original = controller._driver
        controller._ensure_driver()
        assert controller._driver is original

    def test_unsupported_driver_raises(self, controller_no_driver):
        """Unsupported driver type should raise AutomationError."""
        controller_no_driver._driver_type = "safari"
        with pytest.raises(AutomationError, match="Unsupported driver"):
            controller_no_driver._ensure_driver()

    def test_import_error_raises_automation_error(
        self, controller_no_driver, monkeypatch
    ):
        """Missing Selenium should raise AutomationError."""
        def fail_import(name, *a, **kw):
            if name == "selenium":
                raise ImportError("no selenium")
            import importlib
            return importlib.__import__(name, *a, **kw)

        monkeypatch.setattr("builtins.__import__", fail_import)

        with pytest.raises(AutomationError, match="not installed"):
            controller_no_driver._ensure_driver()


# ======================================================================
# Navigation
# ======================================================================


class TestNavigation:
    """Test navigate_to, go_back, go_forward, refresh."""

    def test_navigate_to_with_url(self, controller, mock_webdriver):
        controller.navigate_to("https://example.com")
        mock_webdriver.get.assert_called_once_with("https://example.com")
        assert controller._navigation_count == 1

    def test_navigate_to_adds_https(self, controller, mock_webdriver):
        controller.navigate_to("example.com")
        mock_webdriver.get.assert_called_once_with("https://example.com")

    def test_navigate_to_preserves_http(self, controller, mock_webdriver):
        controller.navigate_to("http://example.com")
        mock_webdriver.get.assert_called_once_with("http://example.com")

    def test_navigate_to_error(self, controller, mock_webdriver):
        mock_webdriver.get.side_effect = RuntimeError("network error")
        with pytest.raises(AutomationError, match="Navigation failed"):
            controller.navigate_to("https://example.com")

    def test_go_back(self, controller, mock_webdriver):
        controller.go_back()
        mock_webdriver.back.assert_called_once()
        assert controller._navigation_count == 1

    def test_go_forward(self, controller, mock_webdriver):
        controller.go_forward()
        mock_webdriver.forward.assert_called_once()
        assert controller._navigation_count == 1

    def test_refresh(self, controller, mock_webdriver):
        controller.refresh()
        mock_webdriver.refresh.assert_called_once()

    def test_navigate_error_back(self, controller, mock_webdriver):
        mock_webdriver.back.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Back navigation failed"):
            controller.go_back()

    def test_navigate_error_forward(self, controller, mock_webdriver):
        mock_webdriver.forward.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Forward navigation failed"):
            controller.go_forward()

    def test_navigate_error_refresh(self, controller, mock_webdriver):
        mock_webdriver.refresh.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="refresh failed"):
            controller.refresh()


# ======================================================================
# Search
# ======================================================================


class TestSearch:
    """Test open_search with different search engines."""

    def test_search_google(self, controller, mock_webdriver):
        controller.open_search("python tutorial")
        called_url = mock_webdriver.get.call_args[0][0]
        assert "google.com" in called_url
        assert "python" in called_url
        assert controller._search_count == 1

    def test_search_bing(self, controller, mock_webdriver):
        controller.open_search("machine learning", engine="bing")
        called_url = mock_webdriver.get.call_args[0][0]
        assert "bing.com" in called_url
        assert "machine" in called_url

    def test_search_duckduckgo(self, controller, mock_webdriver):
        controller.open_search("privacy browser", engine="duckduckgo")
        called_url = mock_webdriver.get.call_args[0][0]
        assert "duckduckgo.com" in called_url
        assert "privacy" in called_url

    def test_search_unknown_engine_defaults_google(
        self, controller, mock_webdriver
    ):
        controller.open_search("test", engine="unknown_engine")
        called_url = mock_webdriver.get.call_args[0][0]
        assert "google.com" in called_url

    def test_search_increments_counter(self, controller, mock_webdriver):
        controller.open_search("a")
        controller.open_search("b")
        assert controller._search_count == 2


# ======================================================================
# Tab Management
# ======================================================================


class TestTabManagement:
    """Test new_tab, close_tab, switch_tab, get_tab_count."""

    def test_new_tab(self, controller, mock_webdriver):
        mock_webdriver.execute_script = MagicMock()
        controller.new_tab()
        mock_webdriver.execute_script.assert_called_once()
        mock_webdriver.switch_to.window.assert_called_once()
        assert controller._tab_count == 1

    def test_new_tab_with_url(self, controller, mock_webdriver):
        mock_webdriver.execute_script = MagicMock()
        controller.new_tab(url="https://example.com")
        mock_webdriver.get.assert_called_once()

    def test_new_tab_error(self, controller, mock_webdriver):
        mock_webdriver.execute_script.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Failed to open new tab"):
            controller.new_tab()

    def test_close_tab_current(self, controller, mock_webdriver):
        controller.close_tab()
        mock_webdriver.close.assert_called_once()

    def test_close_tab_by_index(self, controller, mock_webdriver):
        controller.close_tab(tab_index=0)
        assert mock_webdriver.switch_to.window.called

    def test_close_tab_warns_if_only_one(self, controller, mock_webdriver):
        mock_webdriver.window_handles = ["handle1"]
        controller.close_tab()
        # Should not call close() on last tab
        mock_webdriver.close.assert_not_called()

    def test_close_tab_error(self, controller, mock_webdriver):
        mock_webdriver.close.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Failed to close tab"):
            controller.close_tab()

    def test_switch_tab_valid(self, controller, mock_webdriver):
        controller.switch_tab(0)
        mock_webdriver.switch_to.window.assert_called_once()
        assert controller._current_tab_index == 0

    def test_switch_tab_invalid_index(self, controller, mock_webdriver):
        with pytest.raises(AutomationError, match="out of range"):
            controller.switch_tab(10)

    def test_switch_tab_negative_index(self, controller, mock_webdriver):
        with pytest.raises(AutomationError, match="out of range"):
            controller.switch_tab(-1)

    def test_get_tab_count(self, controller, mock_webdriver):
        count = controller.get_tab_count()
        assert count == 2  # mock has 2 window_handles

    def test_get_tab_count_error_returns_zero(
        self, controller, mock_webdriver
    ):
        mock_webdriver.window_handles = None  # Will raise on access
        count = controller.get_tab_count()
        assert count == 0

    def test_get_current_tab_index(self, controller):
        controller._current_tab_index = 1
        assert controller.get_current_tab_index() == 1


# ======================================================================
# Element Interaction
# ======================================================================


class TestElementInteraction:
    """Test click, fill_text, get_text, select_dropdown."""

    def test_click_xpath(self, controller, mock_webdriver):
        mock_element = MagicMock()
        with patch.object(
            controller, "_find_element", return_value=mock_element
        ):
            controller.click(xpath="//button")
            mock_element.click.assert_called_once()

    def test_click_css_selector(self, controller, mock_webdriver):
        mock_element = MagicMock()
        with patch.object(
            controller, "_find_element", return_value=mock_element
        ):
            controller.click(css_selector=".submit-btn")
            mock_element.click.assert_called_once()

    def test_click_element_id(self, controller, mock_webdriver):
        mock_element = MagicMock()
        with patch.object(
            controller, "_find_element", return_value=mock_element
        ):
            controller.click(element_id="submit_button")
            mock_element.click.assert_called_once()

    def test_click_not_found(self, controller, mock_webdriver):
        with patch.object(controller, "_find_element", return_value=None):
            with pytest.raises(AutomationError, match="Element not found"):
                controller.click(xpath="//nonexistent")

    def test_click_error(self, controller, mock_webdriver):
        mock_element = MagicMock()
        mock_element.click.side_effect = RuntimeError("click failed")
        with patch.object(
            controller, "_find_element", return_value=mock_element
        ):
            with pytest.raises(AutomationError, match="Click failed"):
                controller.click(xpath="//button")

    def test_fill_text_basic(self, controller, mock_webdriver):
        mock_element = MagicMock()
        with patch.object(
            controller, "_find_element", return_value=mock_element
        ):
            controller.fill_text("hello", xpath="//input")
            mock_element.clear.assert_called_once()
            mock_element.send_keys.assert_called_once_with("hello")
            assert controller._form_fill_count == 1

    def test_fill_text_no_clear(self, controller, mock_webdriver):
        mock_element = MagicMock()
        with patch.object(
            controller, "_find_element", return_value=mock_element
        ):
            controller.fill_text("world", xpath="//input", clear=False)
            mock_element.clear.assert_not_called()
            mock_element.send_keys.assert_called_once_with("world")

    def test_fill_text_not_found(self, controller, mock_webdriver):
        with patch.object(controller, "_find_element", return_value=None):
            with pytest.raises(AutomationError, match="Element not found"):
                controller.fill_text("text", xpath="//input")

    def test_fill_text_error(self, controller, mock_webdriver):
        mock_element = MagicMock()
        mock_element.send_keys.side_effect = RuntimeError("input error")
        with patch.object(
            controller, "_find_element", return_value=mock_element
        ):
            with pytest.raises(AutomationError, match="Fill text failed"):
                controller.fill_text("test", xpath="//input")

    def test_get_text(self, controller, mock_webdriver):
        mock_element = MagicMock()
        mock_element.text = "Some Text"
        with patch.object(
            controller, "_find_element", return_value=mock_element
        ):
            text = controller.get_text(xpath="//div")
            assert text == "Some Text"

    def test_get_text_not_found_returns_empty(
        self, controller, mock_webdriver
    ):
        with patch.object(controller, "_find_element", return_value=None):
            text = controller.get_text(xpath="//div")
            assert text == ""

    def test_get_text_error_returns_empty(self, controller, mock_webdriver):
        with patch.object(
            controller, "_find_element", side_effect=RuntimeError("error")
        ):
            text = controller.get_text(xpath="//div")
            assert text == ""

    def test_select_dropdown_by_value(self, controller, mock_webdriver):
        mock_element = MagicMock()
        with patch.object(
            controller, "_find_element", return_value=mock_element
        ):
            with patch("selenium.webdriver.support.select.Select") as MockSelect:
                mock_select = MagicMock()
                MockSelect.return_value = mock_select

                controller.select_dropdown("option1", xpath="//select")

                MockSelect.assert_called_once_with(mock_element)
                mock_select.select_by_value.assert_called_once_with("option1")

    def test_select_dropdown_not_found(self, controller, mock_webdriver):
        with patch.object(controller, "_find_element", return_value=None):
            with pytest.raises(AutomationError, match="Dropdown not found"):
                controller.select_dropdown("value", xpath="//select")


# ======================================================================
# Element Finding
# ======================================================================


class TestElementFinding:
    """Test _find_element and find_elements."""

    def test_find_element_xpath(self, controller, mock_webdriver):
        mock_element = MagicMock()
        mock_webdriver.find_element.return_value = mock_element

        result = controller._find_element(xpath="//button")

        assert result == mock_element
        mock_webdriver.find_element.assert_called_once()

    def test_find_element_css_selector(self, controller, mock_webdriver):
        mock_element = MagicMock()
        mock_webdriver.find_element.return_value = mock_element

        result = controller._find_element(css_selector=".btn")

        assert result == mock_element

    def test_find_element_id(self, controller, mock_webdriver):
        mock_element = MagicMock()
        mock_webdriver.find_element.return_value = mock_element

        result = controller._find_element(element_id="submit")

        assert result == mock_element

    def test_find_element_not_found_returns_none(
        self, controller, mock_webdriver
    ):
        mock_webdriver.find_element.side_effect = RuntimeError("not found")
        result = controller._find_element(xpath="//nonexistent")
        assert result is None

    def test_find_elements_xpath(self, controller, mock_webdriver):
        mock_elements = [MagicMock(), MagicMock()]
        mock_webdriver.find_elements.return_value = mock_elements

        result = controller.find_elements(xpath="//div")

        assert result == mock_elements

    def test_find_elements_returns_empty_on_error(
        self, controller, mock_webdriver
    ):
        mock_webdriver.find_elements.side_effect = RuntimeError("error")
        result = controller.find_elements(xpath="//div")
        assert result == []


# ======================================================================
# Page Info
# ======================================================================


class TestPageInfo:
    """Test get_current_url, get_page_title, get_page_source."""

    def test_get_current_url(self, controller, mock_webdriver):
        mock_webdriver.current_url = "https://example.com"
        url = controller.get_current_url()
        assert url == "https://example.com"

    def test_get_current_url_error_returns_empty(
        self, controller, mock_webdriver
    ):
        mock_webdriver.current_url = None
        mock_webdriver.current_url.side_effect = RuntimeError("fail")
        url = controller.get_current_url()
        assert url == ""

    def test_get_page_title(self, controller, mock_webdriver):
        mock_webdriver.title = "My Page"
        title = controller.get_page_title()
        assert title == "My Page"

    def test_get_page_source(self, controller, mock_webdriver):
        mock_webdriver.page_source = "<html>content</html>"
        source = controller.get_page_source()
        assert source == "<html>content</html>"


# ======================================================================
# Screenshots
# ======================================================================


class TestScreenshots:
    """Test screenshot."""

    def test_screenshot(self, controller, mock_webdriver):
        controller.screenshot("/tmp/screenshot.png")
        mock_webdriver.save_screenshot.assert_called_once_with(
            "/tmp/screenshot.png"
        )

    def test_screenshot_error(self, controller, mock_webdriver):
        mock_webdriver.save_screenshot.side_effect = RuntimeError("fail")
        with pytest.raises(AutomationError, match="Screenshot failed"):
            controller.screenshot("/tmp/screenshot.png")


# ======================================================================
# Wait
# ======================================================================


class TestWait:
    """Test wait_for_element."""

    def test_wait_for_element_success(self, controller, mock_webdriver):
        with patch("selenium.webdriver.support.ui.WebDriverWait") as MockWait:
            mock_wait = MagicMock()
            MockWait.return_value = mock_wait

            result = controller.wait_for_element(xpath="//button", timeout=5)

            assert result is True
            MockWait.assert_called_once_with(mock_webdriver, 5)

    def test_wait_for_element_timeout(self, controller, mock_webdriver):
        with patch("selenium.webdriver.support.ui.WebDriverWait") as MockWait:
            mock_wait = MagicMock()
            mock_wait.until.side_effect = RuntimeError("timeout")
            MockWait.return_value = mock_wait

            result = controller.wait_for_element(xpath="//button")

            assert result is False

    def test_wait_for_element_no_selector(self, controller, mock_webdriver):
        result = controller.wait_for_element()
        assert result is False


# ======================================================================
# Cleanup
# ======================================================================


class TestCleanup:
    """Test quit and close."""

    def test_quit(self, controller, mock_webdriver):
        controller.quit()
        mock_webdriver.quit.assert_called_once()
        assert controller._driver is None

    def test_quit_error_logged(self, controller, mock_webdriver):
        mock_webdriver.quit.side_effect = RuntimeError("error")
        # Should not raise
        controller.quit()

    def test_close_calls_quit(self, controller, mock_webdriver):
        controller.close()
        mock_webdriver.quit.assert_called_once()

    def test_quit_when_no_driver(self, controller_no_driver):
        controller_no_driver.quit()
        # Should not raise


# ======================================================================
# Status
# ======================================================================


class TestStatus:
    """Test get_status."""

    def test_status_keys(self, controller):
        status = controller.get_status()
        expected_keys = {
            "driver_loaded",
            "driver_type",
            "headless",
            "current_url",
            "page_title",
            "tab_count",
            "current_tab",
            "search_count",
            "navigation_count",
            "form_fill_count",
        }
        assert set(status.keys()) == expected_keys

    def test_status_values(self, controller, mock_webdriver):
        controller._search_count = 5
        controller._navigation_count = 3
        controller._form_fill_count = 2

        status = controller.get_status()

        assert status["driver_loaded"] is True
        assert status["driver_type"] == "chrome"
        assert status["headless"] is False
        assert status["search_count"] == 5
        assert status["navigation_count"] == 3
        assert status["form_fill_count"] == 2

    def test_status_no_driver(self, controller_no_driver):
        status = controller_no_driver.get_status()
        assert status["driver_loaded"] is False


# ======================================================================
# Configuration
# ======================================================================


class TestConfiguration:
    """Test set_implicit_wait, set_page_load_timeout."""

    def test_set_implicit_wait(self, controller, mock_webdriver):
        controller.set_implicit_wait(20.0)
        assert controller._implicit_wait == 20.0
        mock_webdriver.implicitly_wait.assert_called_once_with(20.0)

    def test_set_implicit_wait_clamps_min(self, controller):
        controller.set_implicit_wait(-1.0)
        assert controller._implicit_wait == 0.0

    def test_set_implicit_wait_no_driver(self, controller_no_driver):
        controller_no_driver.set_implicit_wait(15.0)
        assert controller_no_driver._implicit_wait == 15.0

    def test_set_page_load_timeout(self, controller, mock_webdriver):
        controller.set_page_load_timeout(60.0)
        assert controller._page_load_timeout == 60.0
        mock_webdriver.set_page_load_timeout.assert_called_once_with(60.0)

    def test_set_page_load_timeout_clamps_min(self, controller):
        controller.set_page_load_timeout(-5.0)
        assert controller._page_load_timeout == 0.0


# ======================================================================
# Initialization
# ======================================================================


class TestInitialization:
    """Test controller initialization."""

    def test_init_chrome(self):
        from src.automation.browser_controller import BrowserController

        ctrl = BrowserController(driver="chrome", headless=True)
        assert ctrl._driver_type == "chrome"
        assert ctrl._headless is True

    def test_init_firefox(self):
        from src.automation.browser_controller import BrowserController

        ctrl = BrowserController(driver="firefox", headless=False)
        assert ctrl._driver_type == "firefox"
        assert ctrl._headless is False

    def test_init_timeouts(self):
        from src.automation.browser_controller import BrowserController

        ctrl = BrowserController(implicit_wait=5.0, page_load_timeout=15.0)
        assert ctrl._implicit_wait == 5.0
        assert ctrl._page_load_timeout == 15.0

    def test_init_counters_zero(self):
        from src.automation.browser_controller import BrowserController

        ctrl = BrowserController()
        assert ctrl._search_count == 0
        assert ctrl._navigation_count == 0
        assert ctrl._form_fill_count == 0


__all__ = []
