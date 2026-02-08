"""
Path utilities for Gorgon Tracker.
Handles cross-platform path resolution for data storage and game files.
"""

import os
import sys
from pathlib import Path


def get_locallow_dir() -> Path:
    """
    Get the LocalLow directory path.

    On Windows: %APPDATA%/../LocalLow or %USERPROFILE%/AppData/LocalLow
    On other platforms: Falls back to ~/.local/share
    """
    if sys.platform == "win32":
        # Try LOCALAPPDATA first (points to Local, go up to get LocalLow)
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata).parent / "LocalLow"

        # Fallback to USERPROFILE
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            return Path(userprofile) / "AppData" / "LocalLow"

        # Last resort
        return Path.home() / "AppData" / "LocalLow"
    else:
        # Linux/Mac fallback
        return Path.home() / ".local" / "share"


def get_gorgon_tracker_data_dir() -> Path:
    """
    Get the Gorgon Tracker data directory.

    Returns:
        Path to AppData/LocalLow/GorgonTracker/ (created if doesn't exist)
    """
    data_dir = get_locallow_dir() / "GorgonTracker"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_pg_chatlog_dir() -> Path | None:
    """
    Auto-detect the Project Gorgon ChatLogs directory.

    Returns:
        Path to Elder Game/Project Gorgon/ChatLogs/ if found, None otherwise
    """
    locallow = get_locallow_dir()
    chatlog_dir = locallow / "Elder Game" / "Project Gorgon" / "ChatLogs"

    if chatlog_dir.exists():
        return chatlog_dir

    return None


def get_pg_base_dir() -> Path | None:
    """
    Get the Project Gorgon base directory (parent of ChatLogs).

    Returns:
        Path to Elder Game/Project Gorgon/ if found, None otherwise
    """
    chatlog_dir = get_pg_chatlog_dir()
    if chatlog_dir:
        return chatlog_dir.parent
    return None
