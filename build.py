#!/usr/bin/env python3
"""
Build script for Gorgon Tracker.
Creates a standalone .exe using PyInstaller.
"""

import subprocess
import sys
import os
from pathlib import Path
import shutil

def get_package_path(package_name):
    """Get the installation path of a package."""
    import importlib
    spec = importlib.util.find_spec(package_name)
    if spec and spec.origin:
        return Path(spec.origin).parent
    return None

def build():
    # Get paths to required packages
    import customtkinter
    import tkinterdnd2

    ctk_path = Path(customtkinter.__file__).parent
    dnd_path = Path(tkinterdnd2.__file__).parent

    print(f"CustomTkinter path: {ctk_path}")
    print(f"TkinterDnD2 path: {dnd_path}")

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=GorgonTracker",
        "--onedir",
        "--windowed",
        "--noconfirm",
        # Add customtkinter
        f"--add-data={ctk_path};customtkinter",
        # Add tkinterdnd2
        f"--add-data={dnd_path};tkinterdnd2",
        # Hidden imports
        "--hidden-import=customtkinter",
        "--hidden-import=tkinterdnd2",
        "--hidden-import=PIL",
        "--hidden-import=PIL._tkinter_finder",
        # Collect all from these packages
        "--collect-all=customtkinter",
        "--collect-all=tkinterdnd2",
        # Entry point
        "gui.py"
    ]

    print("\nRunning PyInstaller...")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=Path(__file__).parent)

    if result.returncode == 0:
        print("\n" + "="*50)
        print("Build successful!")
        print("="*50)
        print(f"\nExecutable location:")
        print(f"  dist/GorgonTracker/GorgonTracker.exe")
        print("\nTo create an installer, you can use:")
        print("  - Inno Setup (free): https://jrsoftware.org/isinfo.php")
        print("  - NSIS: https://nsis.sourceforge.io/")
    else:
        print("\nBuild failed!")
        sys.exit(1)

if __name__ == "__main__":
    build()
