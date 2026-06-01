"""
services/system_service.py
Windows-specific system integration:
  - Start with Windows (registry autostart)
  - System tray icon management helpers
"""

import sys
import os

# Registry access (Windows only)
try:
    import winreg
    _HAS_WINREG = True
except ImportError:
    _HAS_WINREG = False

APP_NAME = "Net Max"
AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def set_autostart(enabled: bool) -> bool:
    """Add or remove the app from Windows autostart. Returns True on success."""
    if not _HAS_WINREG:
        return False
    try:
        exe = sys.executable if getattr(sys, "frozen", False) else sys.executable
        script = os.path.abspath(sys.argv[0])
        value = f'"{exe}" "{script}"' if not getattr(sys, "frozen", False) else f'"{exe}"'

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, value)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


def is_autostart_enabled() -> bool:
    """Check if the app is registered for autostart."""
    if not _HAS_WINREG:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_READ
        ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except Exception:
        return False
