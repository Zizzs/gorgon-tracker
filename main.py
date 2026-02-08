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


def load_config() -> dict:
    """Load configuration from .env file."""
    load_dotenv()

    chatlog_dir = os.getenv("USER_CHATLOG_FILE_LOCATION")

    if not chatlog_dir:
        print("Error: USER_CHATLOG_FILE_LOCATION not set in .env file")
        sys.exit(1)

    return {
        "chatlog_dir": chatlog_dir,
        "output_dir": "CreaturePages",
        "state_file": "processed_logs.json"
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

    # Create parser
    parser = LootParser(
        chatlog_dir=config["chatlog_dir"],
        output_dir=config["output_dir"],
        state_file=config["state_file"]
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
