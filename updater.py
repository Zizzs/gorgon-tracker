"""
Self-update module for GorgonTracker.
Handles checking GitHub releases, downloading, and orchestrating the update.
"""
import os
import sys
import json
import tempfile
import zipfile
import shutil
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

GITHUB_API_URL = "https://api.github.com/repos/Zizzs/gorgon-tracker/releases/latest"
ASSET_NAME = "GorgonTracker-windows.zip"


def get_latest_release_info() -> dict | None:
    """Query GitHub API for latest release info."""
    try:
        req = Request(GITHUB_API_URL, headers={"Accept": "application/vnd.github.v3+json"})
        with urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except (URLError, json.JSONDecodeError, Exception):
        return None


def parse_version(version_str: str) -> tuple:
    """Parse version string like 'v1.2.3' or '1.2.3' into tuple (1, 2, 3)."""
    clean = version_str.lstrip('v')
    parts = clean.split('.')
    return tuple(int(p) for p in parts if p.isdigit())


def is_update_available(current_version: str, release_info: dict) -> bool:
    """Check if the release is newer than current version."""
    tag = release_info.get("tag_name", "")
    if tag == "latest":  # Rolling release - check published date or commit
        return False  # Skip "latest" tag, wait for versioned releases
    try:
        current = parse_version(current_version)
        remote = parse_version(tag)
        return remote > current
    except (ValueError, TypeError):
        return False


def get_download_url(release_info: dict) -> str | None:
    """Extract download URL for the Windows zip asset."""
    for asset in release_info.get("assets", []):
        if asset.get("name") == ASSET_NAME:
            return asset.get("browser_download_url")
    return None


def get_release_version(release_info: dict) -> str:
    """Get the version tag from release info."""
    return release_info.get("tag_name", "unknown")


def download_update(url: str, progress_callback=None) -> Path | None:
    """Download update zip to temp directory with progress reporting."""
    temp_dir = Path(tempfile.gettempdir())
    zip_path = temp_dir / ASSET_NAME

    try:
        req = Request(url)
        with urlopen(req, timeout=60) as response:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 8192

            with open(zip_path, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size:
                        progress_callback(downloaded, total_size)

        return zip_path
    except Exception:
        if zip_path.exists():
            zip_path.unlink()
        return None


def extract_update(zip_path: Path) -> Path | None:
    """Extract zip to temp directory, return path to extracted folder."""
    temp_dir = Path(tempfile.gettempdir())
    extract_dir = temp_dir / "GorgonTracker-update"

    # Clean up any previous extraction
    if extract_dir.exists():
        shutil.rmtree(extract_dir)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)

        # The zip contains a GorgonTracker folder
        inner_dir = extract_dir / "GorgonTracker"
        if inner_dir.exists():
            return inner_dir
        return extract_dir
    except Exception:
        return None


def get_install_dir() -> Path:
    """Get the directory where the app is installed."""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        return Path(sys.executable).parent
    else:
        # Running as script (development)
        return Path(__file__).parent


def is_running_frozen() -> bool:
    """Check if running as a compiled exe (vs running as script)."""
    return getattr(sys, 'frozen', False)


def generate_update_script(new_version_path: Path, install_dir: Path) -> Path:
    """Generate batch script to perform the update after app exits."""
    temp_dir = Path(tempfile.gettempdir())
    script_path = temp_dir / "gorgon_update.bat"

    # Convert paths to strings for batch script
    install_dir_str = str(install_dir)
    new_version_str = str(new_version_path)
    zip_path_str = str(temp_dir / ASSET_NAME)
    parent_dir_str = str(new_version_path.parent)

    # Batch script content - uses robocopy which handles locked files well
    # (e.g., when Windows Defender is scanning the new files)
    script = f'''@echo off
setlocal

echo GorgonTracker Update in Progress...
echo.

:: Define paths
set "INSTALL_DIR={install_dir_str}"
set "NEW_VERSION={new_version_str}"

:: Give the app a moment to start closing
timeout /t 1 /nobreak >nul

:: Force kill the application if still running
echo Ensuring application is closed...
taskkill /f /im GorgonTracker.exe >nul 2>&1

:: Wait a moment for Windows to release file handles
timeout /t 2 /nobreak >nul

:: Use robocopy to mirror the new version over the old one
:: /MIR mirrors the directory (copies new, deletes old)
:: /W:2 wait 2 seconds between retries, /R:5 retry 5 times per file
:: This handles antivirus scans and other temporary file locks gracefully
echo Installing update...
robocopy "%NEW_VERSION%" "%INSTALL_DIR%" /MIR /W:2 /R:5 /NFL /NDL /NJH /NJS

:: Robocopy returns various codes, less than 8 is success
if %ERRORLEVEL% lss 8 goto SUCCESS

echo.
echo Failed to update! Error code: %ERRORLEVEL%
echo Please close any programs using GorgonTracker files and try again.
pause
exit /b 1

:SUCCESS
:: Verify the update
if not exist "%INSTALL_DIR%\\GorgonTracker.exe" (
    echo Update verification failed - GorgonTracker.exe not found!
    pause
    exit /b 1
)

echo Update successful!

:: Clean up temp files
echo Cleaning up...
del "{zip_path_str}" 2>nul
rmdir /s /q "{parent_dir_str}" 2>nul

:: Start the updated application
echo Starting GorgonTracker...
start "" "%INSTALL_DIR%\\GorgonTracker.exe"

:: Self-delete this script
del "%~f0"
'''

    with open(script_path, 'w') as f:
        f.write(script)

    return script_path


def launch_update_script(script_path: Path):
    """Launch the update script and prepare to exit."""
    # Use os.startfile which is the proper Windows API for launching detached processes.
    # This avoids issues with subprocess.Popen where close_fds=True + DETACHED_PROCESS
    # can prevent the subprocess from launching properly on Windows.
    os.startfile(str(script_path))
