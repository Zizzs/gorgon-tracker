#!/usr/bin/env python3
"""
Gorgon Tracker - CLI Interface

Parses Project Gorgon chat logs, extracts creature loot information,
and generates wiki-formatted files for each creature.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from loot_parser import LootParser
from paths import get_pg_chatlog_dir, get_gorgon_tracker_data_dir


def load_config() -> dict:
    """Load configuration from .env file or auto-detect paths."""
    load_dotenv()

    # Try .env first, then auto-detect
    chatlog_dir = os.getenv("USER_CHATLOG_FILE_LOCATION")

    if not chatlog_dir:
        detected_dir = get_pg_chatlog_dir()
        if detected_dir:
            chatlog_dir = str(detected_dir)
            print(f"Auto-detected ChatLogs folder: {chatlog_dir}")

    if not chatlog_dir:
        print("Error: Could not find Project Gorgon ChatLogs folder.")
        print("Please set USER_CHATLOG_FILE_LOCATION in .env file")
        print("Example: USER_CHATLOG_FILE_LOCATION=C:\\Users\\YourName\\AppData\\LocalLow\\Elder Game\\Project Gorgon\\ChatLogs")
        sys.exit(1)

    return {
        "chatlog_dir": chatlog_dir,
        "output_dir": "CreaturePages"
    }


def print_callback(message: str):
    """Simple callback to print progress messages."""
    print(message)


def main():
    """Main entry point for the CLI."""
    print("Gorgon Tracker")
    print("=" * 40)
    print()

    # Load configuration
    config = load_config()

    # Show storage location
    print(f"Data storage: {get_gorgon_tracker_data_dir()}")
    print()

    # Create parser (storage_dir is automatically set to LocalLow/GorgonTracker)
    parser = LootParser(
        chatlog_dir=config["chatlog_dir"],
        output_dir=config["output_dir"]
    )

    # Process all logs
    results = parser.process_all_logs(callback=print_callback)

    # Summary output
    print()
    updates = parser.get_creatures_needing_updates(results)

    if updates:
        print("Creatures needing wiki updates:")
        for creature, file_path in updates:
            print(f"  - {creature} ({file_path})")
    else:
        print("No new loot entries found.")

    print()
    print("Done!")


if __name__ == "__main__":
    main()
