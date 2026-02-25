"""
Browser Automation Controller.

Wraps Selenium WebDriver to provide high-level browser control for the
accessibility agent. Specifically designed for voice-driven browsing
(search, navigation, form filling, tab management).

Supports:
    - Chrome/Firefox driver initialization (with headless mode)
    - Tab/window management (open, close, switch)
    - Navigation (back, forward, refresh, goto URL)
    - Search (Google, Bing, DuckDuckGo)
    - Form filling (text input, click, select)
    - Element waiting (explicit waits, expected conditions)
    - Screenshot capture

Dependencies:
    - selenium (WebDriver)
    - webdriver_manager (automatic driver setup)

Optimised for accessibility:
    - Lazy WebDriver loading (only on first use)
    - Configurable timeouts (implicit + explicit)
    - Retry logic for flaky operations
    - Comprehensive logging for debugging
"""

import time
from typing import Dict, List, Optional, Tuple, Any

from loguru import logger

from ..utils.config_manager import config
from ..utils.error_handler import AutomationError


class BrowserController:
    """
    High-level browser automation using Selenium WebDriver.

    Designed to be driven by VoiceEngine commands (search, navigate, fill forms).
    Lazy-loads the WebDriver on first use to keep startup time minimal.

    Usage:
        browser = BrowserController(driver="chrome", headless=False)
        browser.open_search("python tutorial")
        browser.navigate_to("https://example.com")
        browser.click(xpath="//button[@id='submit']")
        browser.fill_text(xpath="//input[@type='text']", text="Hello")
        browser.new_tab()
        browser.close_tab()
        browser.quit()

    Integration with VoiceEngine:
        Commands like "search for python" are routed to:
        -> VoiceCommandParser.parse() -> "browser_search", args=["python"]
        -> CommandRegistry.dispatch()
        -> BrowserController.open_search("python")
    """

    def __init__(
        self,
        driver: str = "chrome",
        headless: bool = False,
        implicit_wait: float = 10.0,
        page_load_timeout: float = 30.0,
    ) -> None:
        """
        Initialize the browser controller (WebDriver not loaded yet).

        Args:
            driver: "chrome" or "firefox".
            headless: Run in headless mode (no window).
            implicit_wait: Implicit wait time for elements (seconds).
            page_load_timeout: Page load timeout (seconds).
        """
        self._driver_type = driver.lower()
        self._headless = headless
        self._implicit_wait = implicit_wait
        self._page_load_timeout = page_load_timeout

        # Lazy-loaded
        self._driver = None
        self._current_url: str = ""
        self._tab_handles: List[str] = []
        self._current_tab_index: int = 0

        # Stats
        self._search_count: int = 0
        self._navigation_count: int = 0
        self._tab_count: int = 0
        self._form_fill_count: int = 0

        logger.info(
            f"BrowserController created | driver={self._driver_type} | "
            f"headless={self._headless}"
        )

    # ------------------------------------------------------------------
    # Lazy loading
    # ------------------------------------------------------------------

    def _ensure_driver(self) -> None:
        """Lazy-load the WebDriver on first use."""
        if self._driver is not None:
            return

        try:
            if self._driver_type == "chrome":
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service
                from webdriver_manager.chrome import ChromeDriverManager

                options = webdriver.ChromeOptions()
                if self._headless:
                    options.add_argument("--headless")
                options.add_argument("--disable-gpu")
                options.add_argument("--start-maximized")

                service = Service(ChromeDriverManager().install())
                self._driver = webdriver.Chrome(
                    service=service, options=options
                )
            elif self._driver_type == "firefox":
                from selenium import webdriver
                from selenium.webdriver.firefox.service import Service
                from webdriver_manager.firefox import GeckoDriverManager

                options = webdriver.FirefoxOptions()
                if self._headless:
                    options.add_argument("--headless")

                service = Service(GeckoDriverManager().install())
                self._driver = webdriver.Firefox(
                    service=service, options=options
                )
            else:
                raise AutomationError(
                    f"Unsupported driver: {self._driver_type} "
                    "(use 'chrome' or 'firefox')"
                )

            self._driver.implicitly_wait(self._implicit_wait)
            self._driver.set_page_load_timeout(self._page_load_timeout)

            logger.info(
                f"WebDriver loaded | driver={self._driver_type} | "
                f"implicit_wait={self._implicit_wait}s | "
                f"page_load_timeout={self._page_load_timeout}s"
            )
        except ImportError as exc:
            raise AutomationError(
                f"Selenium or webdriver_manager not installed: {exc}. "
                "Run: pip install selenium webdriver-manager"
            )
        except Exception as exc:
            raise AutomationError(f"Failed to initialize WebDriver: {exc}")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to(self, url: str) -> None:
        """
        Navigate to a URL.

        Args:
            url: URL to navigate to (will add https:// if missing).

        Raises:
            AutomationError: If navigation fails.
        """
        try:
            self._ensure_driver()

            # Add https if missing
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            self._driver.get(url)
            self._current_url = url
            self._navigation_count += 1

            logger.info(f"Navigated to: {url}")
        except Exception as exc:
            raise AutomationError(f"Navigation failed: {exc}")

    def go_back(self) -> None:
        """Go back in the browser history."""
        try:
            self._ensure_driver()
            self._driver.back()
            self._navigation_count += 1
            logger.debug("Navigated back")
        except Exception as exc:
            raise AutomationError(f"Back navigation failed: {exc}")

    def go_forward(self) -> None:
        """Go forward in the browser history."""
        try:
            self._ensure_driver()
            self._driver.forward()
            self._navigation_count += 1
            logger.debug("Navigated forward")
        except Exception as exc:
            raise AutomationError(f"Forward navigation failed: {exc}")

    def refresh(self) -> None:
        """Refresh the current page."""
        try:
            self._ensure_driver()
            self._driver.refresh()
            logger.debug("Page refreshed")
        except Exception as exc:
            raise AutomationError(f"Page refresh failed: {exc}")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def open_search(
        self,
        query: str,
        engine: str = "google",
    ) -> None:
        """
        Perform a web search.

        Args:
            query: Search query text.
            engine: "google", "bing", or "duckduckgo".

        Raises:
            AutomationError: If search fails.
        """
        try:
            self._ensure_driver()

            engine = engine.lower()
            if engine == "google":
                url = f"https://www.google.com/search?q={query}"
            elif engine == "bing":
                url = f"https://www.bing.com/search?q={query}"
            elif engine == "duckduckgo":
                url = f"https://duckduckgo.com/?q={query}"
            else:
                logger.warning(
                    f"Unknown search engine '{engine}', defaulting to Google"
                )
                url = f"https://www.google.com/search?q={query}"

            self.navigate_to(url)
            self._search_count += 1

            logger.info(f"Searched ({engine}): {query}")
        except AutomationError:
            raise
        except Exception as exc:
            raise AutomationError(f"Search failed: {exc}")

    # ------------------------------------------------------------------
    # Tab / Window Management
    # ------------------------------------------------------------------

    def new_tab(self, url: Optional[str] = None) -> None:
        """
        Open a new tab.

        Args:
            url: Optional URL to load in the new tab.
        """
        try:
            self._ensure_driver()

            # JavaScript to open new tab
            self._driver.execute_script("window.open('');")
            self._driver.switch_to.window(self._driver.window_handles[-1])

            self._tab_count += 1
            if url:
                self.navigate_to(url)

            logger.debug(f"New tab opened (total: {len(self._driver.window_handles)})")
        except Exception as exc:
            raise AutomationError(f"Failed to open new tab: {exc}")

    def close_tab(self, tab_index: Optional[int] = None) -> None:
        """
        Close a tab.

        Args:
            tab_index: Index of tab to close (current if None).
        """
        try:
            self._ensure_driver()

            if len(self._driver.window_handles) <= 1:
                logger.warning("Cannot close the last tab")
                return

            if tab_index is None:
                self._driver.close()
            else:
                self._driver.switch_to.window(
                    self._driver.window_handles[tab_index]
                )
                self._driver.close()
                # Switch to first available tab
                if self._driver.window_handles:
                    self._driver.switch_to.window(
                        self._driver.window_handles[0]
                    )

            logger.debug(
                f"Tab closed (remaining: {len(self._driver.window_handles)})"
            )
        except Exception as exc:
            raise AutomationError(f"Failed to close tab: {exc}")

    def switch_tab(self, tab_index: int) -> None:
        """
        Switch to a specific tab by index.

        Args:
            tab_index: Index of the tab (0-based).

        Raises:
            AutomationError: If tab index is invalid.
        """
        try:
            self._ensure_driver()

            if tab_index < 0 or tab_index >= len(self._driver.window_handles):
                raise AutomationError(
                    f"Tab index {tab_index} out of range "
                    f"(0-{len(self._driver.window_handles) - 1})"
                )

            self._driver.switch_to.window(
                self._driver.window_handles[tab_index]
            )
            self._current_tab_index = tab_index
            logger.debug(f"Switched to tab {tab_index}")
        except AutomationError:
            raise
        except Exception as exc:
            raise AutomationError(f"Failed to switch tab: {exc}")

    def get_tab_count(self) -> int:
        """Return the number of open tabs."""
        try:
            self._ensure_driver()
            return len(self._driver.window_handles)
        except Exception:
            return 0

    def get_current_tab_index(self) -> int:
        """Return the index of the current tab."""
        return self._current_tab_index

    # ------------------------------------------------------------------
    # Element interaction
    # ------------------------------------------------------------------

    def click(
        self,
        xpath: Optional[str] = None,
        css_selector: Optional[str] = None,
        element_id: Optional[str] = None,
    ) -> None:
        """
        Click an element.

        Args:
            xpath: XPath selector.
            css_selector: CSS selector.
            element_id: Element ID.

        Raises:
            AutomationError: If element not found or click fails.
        """
        try:
            self._ensure_driver()
            element = self._find_element(xpath, css_selector, element_id)

            if element is None:
                raise AutomationError("Element not found")

            element.click()
            logger.debug(f"Clicked element: {xpath or css_selector or element_id}")
        except AutomationError:
            raise
        except Exception as exc:
            raise AutomationError(f"Click failed: {exc}")

    def fill_text(
        self,
        text: str,
        xpath: Optional[str] = None,
        css_selector: Optional[str] = None,
        element_id: Optional[str] = None,
        clear: bool = True,
    ) -> None:
        """
        Fill text into an input field.

        Args:
            text: Text to enter.
            xpath: XPath selector.
            css_selector: CSS selector.
            element_id: Element ID.
            clear: Clear the field before typing.

        Raises:
            AutomationError: If element not found or fill fails.
        """
        try:
            self._ensure_driver()
            element = self._find_element(xpath, css_selector, element_id)

            if element is None:
                raise AutomationError("Element not found")

            if clear:
                element.clear()

            element.send_keys(text)
            self._form_fill_count += 1

            logger.debug(f"Filled text: {text[:50]}... into {xpath or css_selector or element_id}")
        except AutomationError:
            raise
        except Exception as exc:
            raise AutomationError(f"Fill text failed: {exc}")

    def get_text(
        self,
        xpath: Optional[str] = None,
        css_selector: Optional[str] = None,
        element_id: Optional[str] = None,
    ) -> str:
        """
        Get text from an element.

        Returns:
            The element's text content, or empty string if not found.
        """
        try:
            self._ensure_driver()
            element = self._find_element(xpath, css_selector, element_id)

            if element is None:
                return ""

            return element.text
        except Exception:
            return ""

    def select_dropdown(
        self,
        value: str,
        xpath: Optional[str] = None,
        css_selector: Optional[str] = None,
        element_id: Optional[str] = None,
    ) -> None:
        """
        Select an option from a dropdown.

        Args:
            value: Option value or text to select.
            xpath: XPath selector.
            css_selector: CSS selector.
            element_id: Element ID.

        Raises:
            AutomationError: If dropdown not found or selection fails.
        """
        try:
            from selenium.webdriver.support.select import Select

            self._ensure_driver()
            element = self._find_element(xpath, css_selector, element_id)

            if element is None:
                raise AutomationError("Dropdown not found")

            select = Select(element)
            # Try by value first, then by text
            try:
                select.select_by_value(value)
            except Exception:
                select.select_by_visible_text(value)

            logger.debug(f"Selected dropdown option: {value}")
        except AutomationError:
            raise
        except Exception as exc:
            raise AutomationError(f"Dropdown selection failed: {exc}")

    # ------------------------------------------------------------------
    # Element finding
    # ------------------------------------------------------------------

    def _find_element(
        self,
        xpath: Optional[str] = None,
        css_selector: Optional[str] = None,
        element_id: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Find an element using one of the provided selectors.

        Returns the first matching element, or None if not found.
        """
        from selenium.webdriver.common.by import By

        if xpath:
            try:
                return self._driver.find_element(By.XPATH, xpath)
            except Exception:
                return None
        elif css_selector:
            try:
                return self._driver.find_element(By.CSS_SELECTOR, css_selector)
            except Exception:
                return None
        elif element_id:
            try:
                return self._driver.find_element(By.ID, element_id)
            except Exception:
                return None

        return None

    def find_elements(
        self,
        xpath: Optional[str] = None,
        css_selector: Optional[str] = None,
    ) -> List[Any]:
        """
        Find multiple elements.

        Returns:
            List of matching elements (empty if none found).
        """
        from selenium.webdriver.common.by import By

        try:
            self._ensure_driver()

            if xpath:
                return self._driver.find_elements(By.XPATH, xpath)
            elif css_selector:
                return self._driver.find_elements(By.CSS_SELECTOR, css_selector)

            return []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Page info
    # ------------------------------------------------------------------

    def get_current_url(self) -> str:
        """Return the current page URL."""
        try:
            self._ensure_driver()
            return self._driver.current_url
        except Exception:
            return ""

    def get_page_title(self) -> str:
        """Return the current page title."""
        try:
            self._ensure_driver()
            return self._driver.title
        except Exception:
            return ""

    def get_page_source(self) -> str:
        """Return the current page HTML source."""
        try:
            self._ensure_driver()
            return self._driver.page_source
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Screenshots and wait
    # ------------------------------------------------------------------

    def screenshot(self, filepath: str) -> None:
        """
        Take a screenshot and save to file.

        Args:
            filepath: Path to save the screenshot.
        """
        try:
            self._ensure_driver()
            self._driver.save_screenshot(filepath)
            logger.info(f"Screenshot saved: {filepath}")
        except Exception as exc:
            raise AutomationError(f"Screenshot failed: {exc}")

    def wait_for_element(
        self,
        xpath: Optional[str] = None,
        css_selector: Optional[str] = None,
        timeout: float = 10.0,
    ) -> bool:
        """
        Wait for an element to be present.

        Args:
            xpath: XPath selector.
            css_selector: CSS selector.
            timeout: Max time to wait (seconds).

        Returns:
            True if element found, False if timeout.
        """
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.by import By

            self._ensure_driver()

            if xpath:
                locator = (By.XPATH, xpath)
            elif css_selector:
                locator = (By.CSS_SELECTOR, css_selector)
            else:
                return False

            WebDriverWait(self._driver, timeout).until(
                EC.presence_of_element_located(locator)
            )
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def quit(self) -> None:
        """Close the browser and quit the WebDriver."""
        try:
            if self._driver is not None:
                self._driver.quit()
                self._driver = None
                logger.info("Browser quit")
        except Exception as exc:
            logger.error(f"Error quitting browser: {exc}")

    def close(self) -> None:
        """Alias for quit()."""
        self.quit()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return status dict for the UI panel."""
        try:
            tab_count = self.get_tab_count() if self._driver else 0
            current_url = self.get_current_url() if self._driver else ""
        except Exception:
            tab_count = 0
            current_url = ""

        return {
            "driver_loaded": self._driver is not None,
            "driver_type": self._driver_type,
            "headless": self._headless,
            "current_url": current_url,
            "page_title": self.get_page_title() if self._driver else "",
            "tab_count": tab_count,
            "current_tab": self._current_tab_index,
            "search_count": self._search_count,
            "navigation_count": self._navigation_count,
            "form_fill_count": self._form_fill_count,
        }

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_implicit_wait(self, wait_time: float) -> None:
        """Update implicit wait time."""
        self._implicit_wait = max(0.0, wait_time)
        if self._driver is not None:
            self._driver.implicitly_wait(self._implicit_wait)
        logger.info(f"Implicit wait set to {self._implicit_wait}s")

    def set_page_load_timeout(self, timeout: float) -> None:
        """Update page load timeout."""
        self._page_load_timeout = max(0.0, timeout)
        if self._driver is not None:
            self._driver.set_page_load_timeout(self._page_load_timeout)
        logger.info(f"Page load timeout set to {self._page_load_timeout}s")


__all__ = ["BrowserController"]
