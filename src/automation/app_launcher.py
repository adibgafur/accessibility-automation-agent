"""
Application Launcher for Windows.

Discovers and launches applications installed on the system.
Supports voice commands like "open chrome" or "launch notepad".

Features:
    - Windows registry scanning for installed applications
    - Application name fuzzy matching
    - Direct executable launching
    - Common app shortcuts (e.g., "chrome" -> full path)
    - Error handling for missing/broken application shortcuts
    - Caching of discovered apps for performance

Dependencies:
    - winreg (Windows registry access - stdlib on Windows)
    - subprocess (app launching - stdlib)

Optimised for accessibility:
    - Lazy app discovery (on first use)
    - Caching to avoid repeated registry scans
    - Support for Bengali app names (transliterated)
    - Voice-friendly command names
"""

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger

from ..utils.error_handler import AutomationError


# Common application mappings (voice-friendly names to executable names)
_COMMON_APPS = {
    "chrome": "chrome.exe",
    "chromium": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "explorer": "explorer.exe",
    "notepad": "notepad.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "outlook": "OUTLOOK.EXE",
    "teams": "Teams.exe",
    "vs code": "Code.exe",
    "vscode": "Code.exe",
    "cmd": "cmd.exe",
    "powershell": "pwsh.exe",
    "calculator": "calc.exe",
    "settings": "ms-settings:",
    "store": "ms-windows-store:",
}

# Bengali app name translations
_BENGALI_APPS = {
    "ক্রোম": "chrome",
    "ফায়ারফক্স": "firefox",
    "এজ": "edge",
    "নোটপ্যাড": "notepad",
    "ওয়ার্ড": "word",
    "এক্সেল": "excel",
    "টিমস": "teams",
    "কোড": "vs code",
    "ক্যালকুলেটর": "calculator",
}


class AppLauncher:
    """
    Discovers and launches Windows applications.

    Usage:
        launcher = AppLauncher()
        launcher.discover_apps()  # Scan system for apps
        launcher.launch("chrome")
        launcher.launch("notepad")
        launcher.is_running("chrome")
        launcher.close("chrome")

    Voice integration:
        Commands like "open chrome" or "launch firefox" are routed to:
        -> VoiceCommandParser.parse() -> "open_app", args=["chrome"]
        -> CommandRegistry.dispatch()
        -> AppLauncher.launch("chrome")
    """

    def __init__(self) -> None:
        """Initialize the application launcher."""
        self._apps: Dict[str, str] = {}  # {display_name: exe_path}
        self._discovered: bool = False
        self._discovery_lock = threading.Lock()
        self._running_pids: Dict[str, List[int]] = {}  # {app_name: [pids]}
        self._launch_count: int = 0

        logger.info("AppLauncher created")

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_apps(self, force: bool = False) -> int:
        """
        Discover installed applications on the system.

        Scans the Windows registry for applications installed in
        HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\Uninstall
        and common app paths.

        Args:
            force: Re-scan even if already discovered.

        Returns:
            Number of applications discovered.
        """
        with self._discovery_lock:
            if self._discovered and not force:
                logger.debug(f"Apps already discovered ({len(self._apps)} apps)")
                return len(self._apps)

            self._apps = {}

            # Add common apps first
            for name, exe in _COMMON_APPS.items():
                self._apps[name.lower()] = exe

            # Try to find apps in registry (Windows only)
            try:
                self._scan_registry()
            except Exception as exc:
                logger.warning(f"Registry scan failed: {exc}")

            # Scan common installation paths
            self._scan_common_paths()

            self._discovered = True
            logger.info(
                f"Application discovery complete: {len(self._apps)} apps found"
            )
            return len(self._apps)

    def _scan_registry(self) -> None:
        """
        Scan Windows registry for installed applications.

        Updates self._apps with discovered applications.
        """
        try:
            import winreg
        except ImportError:
            logger.warning("winreg not available (not on Windows)")
            return

        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            )

            index = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, index)
                    subkey = winreg.OpenKey(key, subkey_name)

                    # Get DisplayName and InstallLocation
                    try:
                        display_name, _ = winreg.QueryValueEx(
                            subkey, "DisplayName"
                        )
                        # Use display name as lowercase key
                        name_key = display_name.lower()
                        if name_key not in self._apps:
                            self._apps[name_key] = display_name

                        logger.debug(f"Registry app found: {display_name}")
                    except WindowsError:
                        pass

                    winreg.CloseKey(subkey)
                    index += 1
                except WindowsError:
                    break

            winreg.CloseKey(key)
        except Exception as exc:
            logger.warning(f"Registry scan error: {exc}")

    def _scan_common_paths(self) -> None:
        """
        Scan common installation paths for applications.

        Checks:
            - C:\\Program Files
            - C:\\Program Files (x86)
            - AppData\\Local\\Programs
        """
        common_paths = [
            Path("C:\\Program Files"),
            Path("C:\\Program Files (x86)"),
            Path.home() / "AppData" / "Local" / "Programs",
        ]

        for base_path in common_paths:
            if not base_path.exists():
                continue

            try:
                for app_dir in base_path.iterdir():
                    if app_dir.is_dir():
                        name = app_dir.name.lower()
                        if name not in self._apps:
                            self._apps[name] = str(app_dir)
                            logger.debug(
                                f"Path scan app found: {app_dir.name}"
                            )
            except Exception as exc:
                logger.warning(f"Path scan error for {base_path}: {exc}")

    # ------------------------------------------------------------------
    # Launching
    # ------------------------------------------------------------------

    def launch(self, app_name: str) -> int:
        """
        Launch an application.

        Args:
            app_name: Application name (e.g., "chrome", "notepad").
                     Can be Bengali (will be translated).

        Returns:
            Process ID of the launched application.

        Raises:
            AutomationError: If app not found or launch fails.
        """
        try:
            # Translate Bengali app names
            app_name = self._translate_app_name(app_name)
            app_name = app_name.lower().strip()

            # Ensure apps are discovered
            if not self._discovered:
                self.discover_apps()

            # Find the application
            exe_path = self._find_app(app_name)

            if not exe_path:
                raise AutomationError(
                    f"Application not found: {app_name}. "
                    f"Use discover_apps() to scan for installed apps."
                )

            # Launch the app
            logger.info(f"Launching application: {app_name} ({exe_path})")

            # Check if it's a special URL scheme (e.g., ms-settings:)
            if exe_path.startswith("ms-"):
                os.startfile(exe_path)
            else:
                # Normal executable
                process = subprocess.Popen(
                    exe_path,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                pid = process.pid

                # Track the PID
                if app_name not in self._running_pids:
                    self._running_pids[app_name] = []
                self._running_pids[app_name].append(pid)

                self._launch_count += 1
                logger.info(f"Application launched: {app_name} (PID {pid})")
                return pid

            self._launch_count += 1
            return 0  # URL scheme doesn't return PID

        except AutomationError:
            raise
        except Exception as exc:
            raise AutomationError(f"Failed to launch {app_name}: {exc}")

    def _find_app(self, app_name: str) -> Optional[str]:
        """
        Find the executable path for an app by name (fuzzy match).

        Returns the exe path or None if not found.
        """
        app_name = app_name.lower()

        # Exact match first
        if app_name in self._apps:
            return self._apps[app_name]

        # Partial match
        for name, path in self._apps.items():
            if app_name in name or name in app_name:
                return path

        return None

    def _translate_app_name(self, app_name: str) -> str:
        """Translate Bengali app names to English."""
        bengali_lower = app_name.lower()
        return _BENGALI_APPS.get(bengali_lower, app_name)

    # ------------------------------------------------------------------
    # Process management
    # ------------------------------------------------------------------

    def is_running(self, app_name: str) -> bool:
        """
        Check if an application is currently running.

        Args:
            app_name: Application name.

        Returns:
            True if running, False otherwise.
        """
        try:
            app_name = app_name.lower()

            if app_name not in self._running_pids:
                return False

            # Verify PIDs are still alive
            valid_pids = []
            for pid in self._running_pids[app_name]:
                if self._is_pid_running(pid):
                    valid_pids.append(pid)

            self._running_pids[app_name] = valid_pids
            return len(valid_pids) > 0
        except Exception:
            return False

    def _is_pid_running(self, pid: int) -> bool:
        """Check if a process ID is still running."""
        try:
            # Use tasklist command to check if PID is running
            output = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return str(pid) in output.stdout
        except Exception:
            return False

    def close(self, app_name: str) -> bool:
        """
        Close an application.

        Args:
            app_name: Application name.

        Returns:
            True if closed, False if not running.
        """
        try:
            app_name = app_name.lower()

            if app_name not in self._running_pids:
                logger.warning(f"Application not tracked: {app_name}")
                return False

            for pid in self._running_pids[app_name]:
                try:
                    # Use taskkill to close the process
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/F"],
                        capture_output=True,
                        timeout=5,
                    )
                    logger.info(f"Closed application: {app_name} (PID {pid})")
                except Exception as exc:
                    logger.warning(f"Failed to close PID {pid}: {exc}")

            self._running_pids[app_name] = []
            return True
        except Exception as exc:
            logger.error(f"Failed to close {app_name}: {exc}")
            return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_available_apps(self) -> List[str]:
        """
        Return a list of discovered application names.

        Ensures apps are discovered first.
        """
        if not self._discovered:
            self.discover_apps()

        return sorted(self._apps.keys())

    def get_app_path(self, app_name: str) -> Optional[str]:
        """Get the full path/exe for an app."""
        if not self._discovered:
            self.discover_apps()

        return self._find_app(app_name.lower())

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict:
        """Return status dict for the UI panel."""
        running_apps = [
            name
            for name, pids in self._running_pids.items()
            if len(pids) > 0 and any(self._is_pid_running(p) for p in pids)
        ]

        return {
            "discovered": self._discovered,
            "app_count": len(self._apps),
            "running_apps": running_apps,
            "launch_count": self._launch_count,
        }


__all__ = ["AppLauncher"]
