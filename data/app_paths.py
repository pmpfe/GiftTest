"""Runtime-writable paths for GiftTest.

On desktop, writing into the project directory may work when running from source,
but it breaks once packaged (and is not writable on Android). Centralize all
writable paths here.
"""

from __future__ import annotations

from pathlib import Path
import os

from .constants import APP_NAME


def _is_android() -> bool:
    # Qt for Python on Android typically reports sys.platform == "android".
    # Keep an environment fallback for other runtimes.
    return os.environ.get("ANDROID_ARGUMENT") is not None or os.environ.get("QT_ANDROID_APP") is not None


def get_app_data_dir() -> Path:
    """Return a writable per-user/app data directory."""
    try:
        from PySide6.QtCore import QStandardPaths

        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        if base:
            path = Path(base)
        else:
            raise RuntimeError("empty QStandardPaths")
    except Exception:
        # Fallback for non-Qt contexts (tests, tooling). Keep it stable.
        if _is_android():
            # Best-effort fallback; Android should normally have QStandardPaths.
            path = Path.home() / "." + APP_NAME.lower()
        else:
            path = Path.home() / ".local" / "share" / APP_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_preferences_path() -> Path:
    return get_app_data_dir() / "preferences.json"


def get_test_history_path() -> Path:
    return get_app_data_dir() / "test_history.json"


def get_http_log_path() -> Path:
    return get_app_data_dir() / "http_log.txt"
