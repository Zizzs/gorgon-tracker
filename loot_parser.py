"""
Core loot parsing logic for Gorgon Tracker.
Designed to be imported by CLI or GUI interfaces.
"""

import re
import os
import sys
import json
import shutil
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

from paths import get_gorgon_tracker_data_dir, get_pg_chatlog_dir


# Known item prefixes to strip for base item names
QUALITY_PREFIXES = [
    "Shoddy", "Crude", "Rough", "Decent", "Nice",
    "Quality", "Great", "Exceptional", "Amazing", "Astounding"
]

MODIFIER_PREFIXES = [
    "Peppy", "Cruel", "Vicious", "Swift", "Mighty", "Stalwart",
    "Nimble", "Hardy", "Savage", "Fierce", "Brutal", "Deadly",
    "Keen", "Sharp", "Heavy", "Light", "Sturdy", "Elegant",
    "Accurate", "Mind-Numbing", "Slicing", "Grating", "Extra Thick"
]

ALL_PREFIXES = QUALITY_PREFIXES + MODIFIER_PREFIXES

# Suffix pattern - matches "of [Something]" at the end
SUFFIX_PATTERN = re.compile(r'\s+of\s+.+$', re.IGNORECASE)

# Zone name mappings (internal name -> display name)
ZONE_NAMES = {
    "AreaSunVale": "Sun Vale",
    "AreaSerbuleHills": "Serbule Hills",
    "AreaSerbule": "Serbule",
    "AreaEltibule": "Eltibule",
    "AreaKurMountains": "Kur Mountains",
    "AreaGazlukKeep": "Gazluk Keep",
    "AreaGazlukPlateau": "Gazluk Plateau",
    "AreaIlmari": "Ilmari",
    "AreaDesert2": "Phantom Ilmari Desert",
    "AreaRahuSewers": "Rahu Sewer",
    "AreaRahu": "Rahu",
    "AreaDesertTown": "Amulna",
    "AreaRedWing": "Red Wing Casino",
    "AreaFaeRealm": "Fae Realm",
    "AreaWinterNexus": "Winter Nexus",
    "AreaLabyrinth": "Labyrinth",
    "AreaGoblinDungeon": "Goblin Dungeon",
    "AreaCave1": "Goblin Dungeon",
    "AreaMyconian": "Myconian Cave",
    "AreaAnagoge": "Anagoge Island",
    "AreaNewbie2": "Anagoge Records Facility",
    "AreaDarkChapel": "Dark Chapel",
    "AreaCrypt": "Crypt of Thulgarod",
    "AreaWolf": "Wolf Cave",
    "AreaHogan": "Hogan's Keep",
    "AreaYeti": "Yeti Cave",
    "AreaKelp": "Under the Sea",
    "AreaBigMine": "Borghild",
    "ChooseCharacter": None,  # Not a zone
    "ReconnectToServer": None,  # Not a zone - connection state
}

# Official Project Gorgon item database URL
ITEMS_JSON_URL = "https://cdn.projectgorgon.com/v456/data/items.json"


def load_valid_items(cache_dir: Path) -> set:
    """Load valid item names from PG's official item database."""
    items_set = set()

    # Debug log file
    debug_log = cache_dir / "item_cache_debug.log"
    def log(msg):
        with open(debug_log, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now()}: {msg}\n")

    log(f"load_valid_items called, frozen={getattr(sys, 'frozen', False)}")

    # Check for bundled cache first (PyInstaller)
    if getattr(sys, 'frozen', False):
        bundled_cache = Path(sys._MEIPASS) / "items_cache.json"
        log(f"Checking bundled cache at: {bundled_cache}")
        log(f"Bundled cache exists: {bundled_cache.exists()}")
        if bundled_cache.exists():
            try:
                with open(bundled_cache, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    items = set(data.get("names", []))
                    log(f"Loaded {len(items)} items from bundled cache")
                    return items
            except Exception as e:
                log(f"Error loading bundled cache: {e}")
                pass

    # Try to load from local cache
    cache_file = cache_dir / "items_cache.json"
    if cache_file.exists():
        cache_age = datetime.now().timestamp() - cache_file.stat().st_mtime
        if cache_age < 7 * 24 * 3600:  # 7 days
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get("names", []))
            except (json.JSONDecodeError, IOError, OSError):
                pass

    # Download fresh data
    try:
        req = urllib.request.Request(
            ITEMS_JSON_URL,
            headers={'User-Agent': 'GorgonTracker/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            if not isinstance(data, dict):
                raise ValueError("Invalid items database format")
            for item_id, item_data in data.items():
                if isinstance(item_data, dict) and "Name" in item_data:
                    items_set.add(item_data["Name"])

            # Cache for later
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({"names": list(items_set)}, f)
    except Exception as e:
        print(f"Warning: Could not load items database: {e}")

    return items_set


class LootParser:
    """Parses chat logs and extracts creature loot data."""

    # Regex patterns for chat log
    LOG_LINE_PATTERN = re.compile(r'^(\d{2}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\t\[(\w+)\] (.+)$')
    COMBAT_TARGET_PATTERN = re.compile(r' on (.+?) #\d+[!:]')
    FATALITY_PATTERN = re.compile(r'\(FATALITY!\)$')
    LOOT_PATTERN = re.compile(r'^(.+?)(?: x(\d+))? added to inventory\.$')
    SKINNING_XP_PATTERN = re.compile(r'^You earned \d+ XP in Skinning\.$')
    BUTCHERING_XP_PATTERN = re.compile(r'^You earned \d+ XP in Butchering\.$')
    # Any XP message (to reset skinning_active when we see non-skinning XP)
    ANY_XP_PATTERN = re.compile(r'^You earned \d+ XP in .+\.$')

    # Regex patterns for Player.log
    PLAYER_LOG_ZONE_PATTERN = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\] LOADING LEVEL (.+)$')

    # Pattern to extract timezone offset from chat log login line
    TIMEZONE_PATTERN = re.compile(r'Timezone Offset ([+-])(\d{2}):(\d{2}):(\d{2})')

    # Pattern to match ProcessAddItem in Player.log for loot validation
    # Example: [15:59:08] LocalPlayer: ProcessAddItem(BasicSword(12345), InventorySlot, True)
    PLAYER_LOG_ADDITEM_PATTERN = re.compile(
        r'\[(\d{2}:\d{2}:\d{2})\] LocalPlayer: ProcessAddItem\(([^(]+)\((\d+)\),'
    )

    def __init__(self, chatlog_dir: str = None, output_dir: str = "CreaturePages",
                 storage_dir: Path = None):
        # Storage directory - defaults to AppData/LocalLow/GorgonTracker
        if storage_dir is None:
            storage_dir = get_gorgon_tracker_data_dir()
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Data files now stored in storage_dir
        self.data_file = self.storage_dir / "creature_data.json"
        self.state_file = self.storage_dir / "processed_logs.json"

        # Mirror directory for log files
        self.mirror_dir = self.storage_dir / "PlayerLogs"
        self.mirror_dir.mkdir(parents=True, exist_ok=True)

        # Chatlog directory - auto-detect if not provided
        if chatlog_dir:
            self.chatlog_dir = Path(chatlog_dir)
        else:
            detected_dir = get_pg_chatlog_dir()
            if detected_dir:
                self.chatlog_dir = detected_dir
            else:
                # Fallback to empty path - will fail gracefully when processing
                self.chatlog_dir = Path("")

        self.output_dir = Path(output_dir)

        # Player.log is in parent directory of ChatLogs
        self.player_log_path = self.chatlog_dir.parent / "Player.log" if self.chatlog_dir.exists() else Path("")

        # Current parsing state
        self.current_creature: Optional[str] = None
        self.creature_killed = False
        self.current_zone: Optional[str] = None
        self.kill_timestamp: Optional[datetime] = None  # When the kill happened
        self.loot_window_seconds = 30  # Max seconds after kill to attribute loot
        # Track last loot for retrospective skinning detection
        self.last_loot: Optional[dict] = None  # {creature, base_name, count, timestamp}

        # Zone transitions parsed from Player.log (time -> zone)
        self.zone_transitions: list[tuple[datetime, str]] = []

        # Track if we're parsing current session (Player.log is valid)
        self._is_current_session = False

        # Timezone offset from chat log (hours to subtract from local to get UTC)
        self._timezone_offset_hours = 0

        # Migrate legacy data from project root if needed
        self._migrate_legacy_data()

        # Clean zone history to remove invalid entries
        self._clean_zone_history()

        # Load creature data (source of truth)
        self.creature_data = self._load_creature_data()

        # Load processing state
        self.processed_state = self._load_state()

        # Load valid item names from PG database
        self.valid_items = load_valid_items(self.storage_dir)

    def _load_state(self) -> dict:
        """Load the processed logs state file."""
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"files": {}}

    def _save_state(self):
        """Save the processed logs state file."""
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.processed_state, f, indent=2)

    def _migrate_legacy_data(self):
        """
        Migrate data files from legacy locations (project root) to new storage directory.
        Only migrates if the new location doesn't have the files yet.
        """
        # Get the project root (where the script is located)
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            project_root = Path(sys.executable).parent
        else:
            # Running as script
            project_root = Path(__file__).parent

        legacy_files = [
            ("creature_data.json", self.data_file),
            ("processed_logs.json", self.state_file),
            ("items_cache.json", self.storage_dir / "items_cache.json"),
        ]

        for legacy_name, new_path in legacy_files:
            legacy_path = project_root / legacy_name

            # Only migrate if legacy exists and new doesn't
            if legacy_path.exists() and not new_path.exists():
                try:
                    shutil.copy2(legacy_path, new_path)
                    print(f"Migrated {legacy_name} to {new_path}")
                except Exception as e:
                    print(f"Warning: Could not migrate {legacy_name}: {e}")

    def _mirror_log_file(self, source_path: Path):
        """
        Mirror a single log file to the PlayerLogs directory.

        Args:
            source_path: Path to the source log file
        """
        if not source_path.exists():
            return

        dest_path = self.mirror_dir / source_path.name

        try:
            shutil.copy2(source_path, dest_path)
        except Exception as e:
            print(f"Warning: Could not mirror {source_path.name}: {e}")

    def _get_system_timezone_offset_hours(self) -> float:
        """Get the system's local timezone offset from UTC in hours."""
        from datetime import timezone
        local_offset = datetime.now(timezone.utc).astimezone().utcoffset()
        return local_offset.total_seconds() / 3600

    def _convert_utc_to_local_time(self, time_str: str, base_date: str) -> tuple[str, str]:
        """
        Convert a UTC time string to local time, handling date rollover.

        Args:
            time_str: Time in "HH:MM:SS" format (UTC from Player.log)
            base_date: Date in "YYYY-MM-DD" format

        Returns:
            Tuple of (local_time_str, adjusted_date_str)
        """
        offset_hours = self._get_system_timezone_offset_hours()
        utc_hour = int(time_str[:2])
        local_hour = utc_hour + offset_hours

        # Handle date adjustment if crossing midnight
        date_adjustment = 0
        if local_hour < 0:
            local_hour += 24
            date_adjustment = -1
        elif local_hour >= 24:
            local_hour -= 24
            date_adjustment = 1

        # Adjust the date if needed
        if date_adjustment != 0:
            adjusted_date = datetime.strptime(base_date, "%Y-%m-%d") + timedelta(days=date_adjustment)
            result_date = adjusted_date.strftime("%Y-%m-%d")
        else:
            result_date = base_date

        local_time_str = f"{int(local_hour):02d}{time_str[2:]}"  # Replace hour, keep :MM:SS
        return local_time_str, result_date

    def _update_zone_history(self):
        """Append new zone transitions from Player.log to persistent history."""
        if not self.player_log_path.exists():
            return

        history_file = self.storage_dir / "zone_history.txt"

        # Load existing history to avoid duplicates
        existing_entries = set()
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    existing_entries = set(line.strip() for line in f if line.strip())
            except Exception:
                pass

        # Use Player.log file modification date instead of current date
        # This ensures correct dates when processing logs from previous sessions
        try:
            log_mtime = os.path.getmtime(self.player_log_path)
            log_date = datetime.fromtimestamp(log_mtime).strftime("%Y-%m-%d")
        except (OSError, ValueError):
            log_date = datetime.now().strftime("%Y-%m-%d")

        # Read current Player.log and append new entries
        new_entries = []
        try:
            with open(self.player_log_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    match = self.PLAYER_LOG_ZONE_PATTERN.match(line.strip())
                    if match:
                        time_str, zone_internal = match.groups()
                        zone_name = ZONE_NAMES.get(zone_internal, zone_internal)
                        if zone_name is None:  # Skip non-zones like ChooseCharacter
                            continue
                        # Convert UTC time from Player.log to local time
                        local_time_str, local_date = self._convert_utc_to_local_time(time_str, log_date)
                        entry = f"{local_date} {local_time_str} {zone_name}"
                        if entry not in existing_entries:
                            new_entries.append(entry)
                            existing_entries.add(entry)
        except Exception as e:
            print(f"Warning: Could not read Player.log: {e}")
            return

        # Append new entries to history
        if new_entries:
            try:
                with open(history_file, 'a', encoding='utf-8') as f:
                    for entry in new_entries:
                        f.write(entry + '\n')
            except Exception as e:
                print(f"Warning: Could not write zone history: {e}")

    def _load_zone_history(self) -> list[tuple[datetime, str]]:
        """Load all zone transitions from persistent history."""
        transitions = []
        history_file = self.storage_dir / "zone_history.txt"

        if not history_file.exists():
            return transitions

        # Get invalid zone names (those that map to None)
        invalid_zones = {name for name, display in ZONE_NAMES.items() if display is None}

        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # Format: "2026-02-07 14:30:45 Kur Mountains"
                    parts = line.split(' ', 2)  # Split into date, time, zone
                    if len(parts) == 3:
                        date_str, time_str, zone_name = parts
                        # Validate date format (YYYY-MM-DD)
                        if len(date_str) != 10 or date_str[4] != '-' or date_str[7] != '-':
                            continue
                        # Validate time format (HH:MM:SS)
                        if len(time_str) != 8 or time_str[2] != ':' or time_str[5] != ':':
                            continue
                        # Skip invalid zone names
                        if zone_name in invalid_zones:
                            continue
                        try:
                            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                            transitions.append((dt, zone_name))
                        except ValueError:
                            continue
        except Exception:
            pass

        return sorted(transitions, key=lambda x: x[0])

    def _clean_zone_history(self):
        """
        Clean zone_history.txt by removing invalid entries.

        Removes entries that:
        - Don't have valid YYYY-MM-DD HH:MM:SS format
        - Have zone names that map to None in ZONE_NAMES (like ReconnectToServer)
        """
        history_file = self.storage_dir / "zone_history.txt"

        if not history_file.exists():
            return

        # Get invalid zone names (those that map to None)
        invalid_zones = {name for name, display in ZONE_NAMES.items() if display is None}

        valid_entries = []
        had_invalid = False

        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # Format: "2026-02-07 14:30:45 Kur Mountains"
                    parts = line.split(' ', 2)
                    if len(parts) != 3:
                        had_invalid = True
                        continue

                    date_str, time_str, zone_name = parts

                    # Validate date format (YYYY-MM-DD)
                    if len(date_str) != 10 or date_str[4] != '-' or date_str[7] != '-':
                        had_invalid = True
                        continue

                    # Validate time format (HH:MM:SS)
                    if len(time_str) != 8 or time_str[2] != ':' or time_str[5] != ':':
                        had_invalid = True
                        continue

                    # Skip invalid zone names
                    if zone_name in invalid_zones:
                        had_invalid = True
                        continue

                    # Validate the datetime can be parsed
                    try:
                        datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                        valid_entries.append(line)
                    except ValueError:
                        had_invalid = True
                        continue
        except Exception:
            return

        # Only rewrite if we found invalid entries
        if had_invalid:
            try:
                with open(history_file, 'w', encoding='utf-8') as f:
                    for entry in valid_entries:
                        f.write(entry + '\n')
            except Exception:
                pass

    def _update_skinning_history(self):
        """Parse Player.log for skinning events and append to persistent history."""
        self._update_corpse_action_history("skinned", "skinning_history.txt")

    def _update_butchering_history(self):
        """Parse Player.log for butchering events and append to persistent history."""
        self._update_corpse_action_history("butchered", "butchering_history.txt")

    def _update_loot_history(self):
        """
        Parse Player.log for ProcessAddItem entries and append to persistent history.
        This provides validation data that can be cross-referenced with chat log timestamps.
        """
        if not self.player_log_path.exists():
            return

        history_file = self.storage_dir / "loot_history.txt"

        # Load existing history to avoid duplicates
        existing_entries = set()
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    existing_entries = set(line.strip() for line in f if line.strip())
            except Exception:
                pass

        # Use Player.log file modification date
        try:
            log_mtime = os.path.getmtime(self.player_log_path)
            log_date = datetime.fromtimestamp(log_mtime).strftime("%Y-%m-%d")
        except (OSError, ValueError):
            log_date = datetime.now().strftime("%Y-%m-%d")

        # Read current Player.log and find ProcessAddItem entries
        new_entries = []
        try:
            with open(self.player_log_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    match = self.PLAYER_LOG_ADDITEM_PATTERN.match(line.strip())
                    if match:
                        time_str, item_internal_name, item_id = match.groups()
                        # Format: YYYY-MM-DD HH:MM:SS|item_internal_name|item_id
                        entry = f"{log_date} {time_str}|{item_internal_name}|{item_id}"
                        if entry not in existing_entries:
                            new_entries.append(entry)
                            existing_entries.add(entry)
        except Exception as e:
            print(f"Warning: Could not read Player.log for loot history: {e}")
            return

        # Append new entries to history
        if new_entries:
            try:
                with open(history_file, 'a', encoding='utf-8') as f:
                    for entry in new_entries:
                        f.write(entry + '\n')
            except Exception as e:
                print(f"Warning: Could not write loot history: {e}")

    # Pattern to match start of ProcessTalkScreen with "Search Corpse of X"
    # Example: [15:59:08] LocalPlayer: ProcessTalkScreen(2281134, "Search Corpse of Wild Pig",
    CORPSE_SEARCH_START_PATTERN = re.compile(
        r'\[(\d{2}:\d{2}:\d{2})\] LocalPlayer: ProcessTalkScreen\((\d+), "Search Corpse of ([^"]+)"'
    )

    # Pattern to match skinning/butchering result with items obtained
    # Example: Zizzs skinned the corpse (with a +8 skill bonus from equipment) and obtained Rough Animal Skin x2 plus Shoddy Animal Skin"
    CORPSE_ACTION_RESULT_PATTERN = re.compile(
        r'\w+ (skinned|butchered) the corpse.*?and obtained ([^"]+)"',
        re.IGNORECASE
    )

    def _update_corpse_action_history(self, action_type: str, history_filename: str):
        """
        Parse Player.log for skinning/butchering events and append to persistent history.

        Uses line-by-line processing with state tracking to avoid catastrophic regex
        backtracking on large files (Player.log can be 70MB+).

        Args:
            action_type: "skinned" or "butchered"
            history_filename: Name of the history file to write to
        """
        if not self.player_log_path.exists():
            return

        history_file = self.storage_dir / history_filename

        # Load existing history to avoid duplicates
        existing_entries = set()
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    existing_entries = set(line.strip() for line in f if line.strip())
            except Exception:
                pass

        # Use Player.log file modification date
        try:
            log_mtime = os.path.getmtime(self.player_log_path)
            log_date = datetime.fromtimestamp(log_mtime).strftime("%Y-%m-%d")
        except (OSError, ValueError):
            log_date = datetime.now().strftime("%Y-%m-%d")

        # Process line-by-line with state tracking
        # ProcessTalkScreen can span multiple lines, so we track state across lines
        new_entries = []
        pending_corpse = None  # (time_str, entity_id, creature)
        pending_text = ""  # Accumulated text for current ProcessTalkScreen

        try:
            with open(self.player_log_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    # Check for start of a new ProcessTalkScreen with "Search Corpse"
                    corpse_match = self.CORPSE_SEARCH_START_PATTERN.search(line)
                    if corpse_match:
                        # Start tracking a new potential corpse action
                        pending_corpse = corpse_match.groups()
                        pending_text = line[corpse_match.start():]
                        continue

                    # If we're tracking a corpse search, accumulate text
                    if pending_corpse:
                        # Check if a new log entry starts (new timestamp = new entry)
                        if line.startswith('[') and '] ' in line[:15]:
                            # New log entry started, reset tracking
                            pending_corpse = None
                            pending_text = ""
                        else:
                            # Continuation of ProcessTalkScreen, accumulate text
                            pending_text += line

                        # Look for the skinning/butchering result in accumulated text
                        action_match = self.CORPSE_ACTION_RESULT_PATTERN.search(pending_text)
                        if action_match:
                            action, items_str = action_match.groups()

                            # Only process entries matching our action type
                            if action.lower() == action_type:
                                time_str, entity_id, creature = pending_corpse

                                # Parse items: "Rough Animal Skin x2 plus Shoddy Animal Skin"
                                items = self._parse_corpse_items(items_str)

                                # Convert UTC time from Player.log to local time
                                local_time_str, local_date = self._convert_utc_to_local_time(time_str, log_date)

                                # Format: YYYY-MM-DD HH:MM:SS|entity_id|creature|item1,item2,...
                                items_formatted = ",".join(f"{name}:{count}" for name, count in items)
                                entry = f"{local_date} {local_time_str}|{entity_id}|{creature}|{items_formatted}"

                                if entry not in existing_entries:
                                    new_entries.append(entry)
                                    existing_entries.add(entry)

                            # Reset tracking after processing
                            pending_corpse = None
                            pending_text = ""

        except Exception as e:
            print(f"Warning: Could not read Player.log for {action_type}: {e}")
            return

        # Append new entries to history
        if new_entries:
            try:
                with open(history_file, 'a', encoding='utf-8') as f:
                    for entry in new_entries:
                        f.write(entry + '\n')
            except Exception as e:
                print(f"Warning: Could not write {action_type} history: {e}")

    def _parse_corpse_items(self, items_str: str) -> list[tuple[str, int]]:
        """
        Parse items string from ProcessTalkScreen.

        Args:
            items_str: String like "Rough Animal Skin x2 plus Shoddy Animal Skin"

        Returns:
            List of (item_name, count) tuples
        """
        items = []
        # Split by " plus "
        parts = items_str.split(" plus ")
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Check for "x2" count suffix
            count_match = re.search(r'^(.+?)\s+x(\d+)$', part)
            if count_match:
                name = count_match.group(1).strip()
                count = int(count_match.group(2))
            else:
                name = part
                count = 1

            if name:
                items.append((name, count))

        return items

    def _load_skinning_history(self) -> list[tuple[datetime, str, str, list[tuple[str, int]]]]:
        """
        Load skinning history from persistent file.

        Returns:
            List of (datetime, entity_id, creature, items) tuples
            where items is a list of (item_name, count) tuples
        """
        return self._load_corpse_action_history("skinning_history.txt")

    def _load_butchering_history(self) -> list[tuple[datetime, str, str, list[tuple[str, int]]]]:
        """
        Load butchering history from persistent file.

        Returns:
            List of (datetime, entity_id, creature, items) tuples
            where items is a list of (item_name, count) tuples
        """
        return self._load_corpse_action_history("butchering_history.txt")

    def _load_corpse_action_history(self, history_filename: str) -> list[tuple[datetime, str, str, list[tuple[str, int]]]]:
        """
        Load corpse action history from persistent file.

        Args:
            history_filename: Name of the history file to read

        Returns:
            List of (datetime, entity_id, creature, items) tuples
        """
        history = []
        history_file = self.storage_dir / history_filename

        if not history_file.exists():
            return history

        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # Format: "YYYY-MM-DD HH:MM:SS|entity_id|creature|item1:count1,item2:count2,..."
                    try:
                        datetime_part, entity_id, creature, items_part = line.split('|', 3)
                        dt = datetime.strptime(datetime_part, "%Y-%m-%d %H:%M:%S")

                        # Parse items
                        items = []
                        if items_part:
                            for item_entry in items_part.split(','):
                                if ':' in item_entry:
                                    name, count_str = item_entry.rsplit(':', 1)
                                    items.append((name, int(count_str)))

                        history.append((dt, entity_id, creature, items))
                    except (ValueError, IndexError):
                        continue
        except Exception:
            pass

        return sorted(history, key=lambda x: x[0])

    def _mirror_all_logs(self):
        """Mirror all Chat-*.log files and update zone history."""
        if not self.chatlog_dir.exists():
            return

        # Mirror all Chat-*.log files
        for log_file in self.chatlog_dir.glob("Chat-*.log"):
            self._mirror_log_file(log_file)

        # Update zone history (appends new transitions)
        self._update_zone_history()

    def _load_creature_data(self) -> dict:
        """
        Load creature data JSON.

        Structure:
        {
            "Creature Name": {
                "kills": 123,
                "zones": ["Sun Vale", "Eltibule"],
                "items": {
                    "Item Name": {
                        "count": 45,
                        "first_seen": "2026-02-07",
                        "last_seen": "2026-02-07"
                    }
                }
            }
        }
        """
        if self.data_file.exists():
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_creature_data(self):
        """Save creature data JSON."""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.creature_data, f, indent=2, sort_keys=True)

    def _parse_player_log(self, reference_date: datetime) -> list[tuple[datetime, str]]:
        """
        Parse Player.log for zone transitions.

        Args:
            reference_date: The date to use for timestamps (from chat log filename)

        Returns:
            List of (datetime, zone_name) tuples sorted by time
        """
        transitions = []

        if not self.player_log_path.exists():
            return transitions

        try:
            with open(self.player_log_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    match = self.PLAYER_LOG_ZONE_PATTERN.match(line.strip())
                    if match:
                        time_str, zone_internal = match.groups()

                        # Skip non-zone levels
                        zone_name = ZONE_NAMES.get(zone_internal, zone_internal)
                        if zone_name is None:
                            continue

                        # Convert UTC time from Player.log to local time
                        try:
                            base_date = reference_date.strftime("%Y-%m-%d")
                            local_time_str, local_date = self._convert_utc_to_local_time(time_str, base_date)
                            time_parts = local_time_str.split(':')
                            local_datetime = datetime.strptime(local_date, "%Y-%m-%d")
                            zone_time = local_datetime.replace(
                                hour=int(time_parts[0]),
                                minute=int(time_parts[1]),
                                second=int(time_parts[2])
                            )
                            transitions.append((zone_time, zone_name))
                        except (ValueError, IndexError):
                            continue
        except Exception:
            pass

        return sorted(transitions, key=lambda x: x[0])

    def _get_zone_at_time(self, timestamp: datetime) -> Optional[str]:
        """Get the zone the player was in at a given timestamp.

        Only returns a zone if there's a zone transition from the SAME DAY.
        This prevents incorrect zone assignment when zone data is missing
        (e.g., Player.log was reset before zone data was captured).

        Both timestamp and zone_transitions are in local time.
        We compare full datetime objects to correctly handle midnight crossings.
        """
        if not self.zone_transitions:
            return None

        target_date = timestamp.date()

        # Filter to same-day transitions only
        same_day_transitions = [
            (zone_time, zone_name)
            for zone_time, zone_name in self.zone_transitions
            if zone_time.date() == target_date
        ]

        if not same_day_transitions:
            return None

        # Find the last transition before or at the timestamp
        current_zone = None
        for zone_time, zone_name in same_day_transitions:
            if zone_time <= timestamp:
                current_zone = zone_name
            else:
                break

        return current_zone

    def get_current_zone(self) -> Optional[str]:
        """Get the most recent zone from Player.log (current session only)."""
        if not self.player_log_path.exists():
            return None

        last_zone = None
        try:
            with open(self.player_log_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    match = self.PLAYER_LOG_ZONE_PATTERN.match(line.strip())
                    if match:
                        _, zone_internal = match.groups()
                        zone_name = ZONE_NAMES.get(zone_internal, zone_internal)
                        if zone_name is not None:
                            last_zone = zone_name
        except Exception:
            pass

        return last_zone

    def _is_today(self, log_filename: str) -> bool:
        """Check if a chat log file is from today (current session)."""
        try:
            date_match = re.search(r'Chat-(\d{2})-(\d{2})-(\d{2})\.log', log_filename)
            if date_match:
                year = 2000 + int(date_match.group(1))
                month = int(date_match.group(2))
                day = int(date_match.group(3))
                log_date = datetime(year, month, day).date()
                return log_date == datetime.now().date()
        except (ValueError, AttributeError):
            pass
        return False

    def strip_prefixes(self, item_name: str) -> str:
        """Find the base item name by matching against valid item database."""
        # If we have valid items loaded, use smart matching
        if self.valid_items:
            # Try exact match on full name first (before stripping anything)
            if item_name in self.valid_items:
                return item_name

            # Try stripping prefixes from the full name first
            words = item_name.split()
            for i in range(len(words)):
                candidate = ' '.join(words[i:])
                if candidate in self.valid_items:
                    return candidate

            # Now try stripping suffix pattern and repeat
            name_no_suffix = SUFFIX_PATTERN.sub('', item_name)

            # Try exact match on suffix-stripped name
            if name_no_suffix in self.valid_items:
                return name_no_suffix

            # Try stripping prefixes from suffix-stripped name
            words = name_no_suffix.split()
            for i in range(len(words)):
                candidate = ' '.join(words[i:])
                if candidate in self.valid_items:
                    return candidate

            # No match found - return full item name (don't strip anything)
            return item_name

        # Fallback to old behavior if no valid items loaded
        name = SUFFIX_PATTERN.sub('', item_name)
        words = name.split()
        while words and words[0] in ALL_PREFIXES:
            words.pop(0)
        return ' '.join(words) if words else item_name

    def _record_kill(self, creature: str, zone: Optional[str] = None):
        """Record a creature kill."""
        if creature not in self.creature_data:
            self.creature_data[creature] = {"kills": 0, "zones": [], "items": {}, "skinning": {}, "butchering": {}}

        # Ensure zones list exists (for backwards compatibility)
        if "zones" not in self.creature_data[creature]:
            self.creature_data[creature]["zones"] = []

        self.creature_data[creature]["kills"] += 1

        # Update last_updated timestamp (UTC)
        utc_now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.creature_data[creature]["last_updated"] = utc_now

        # Smart zone handling - don't pollute existing data with "Unknown"
        if zone:
            # Known zone - add it
            if zone not in self.creature_data[creature]["zones"]:
                self.creature_data[creature]["zones"].append(zone)
                self.creature_data[creature]["zones"].sort()
        elif not self.creature_data[creature]["zones"]:
            # Unknown zone, but creature has NO zones yet - add "Unknown"
            self.creature_data[creature]["zones"].append("Unknown")

    def _record_loot(self, creature: str, base_name: str, count: int = 1,
                     zone: Optional[str] = None) -> bool:
        """
        Record a loot drop. Returns True if this is a new item for this creature.

        Args:
            creature: The creature name
            base_name: The base item name (prefixes stripped)
            count: Number of items dropped
            zone: Optional zone where the item dropped
        """
        if creature not in self.creature_data:
            self.creature_data[creature] = {"kills": 0, "zones": [], "items": {}, "skinning": {}, "butchering": {}}

        # Ensure skinning dict exists (backwards compatibility)
        if "skinning" not in self.creature_data[creature]:
            self.creature_data[creature]["skinning"] = {}

        items = self.creature_data[creature]["items"]
        today = datetime.now().strftime("%Y-%m-%d")
        is_new = base_name not in items

        if is_new:
            items[base_name] = {
                "count": count,
                "drops": 1,  # Number of drop events (for drop rate calculation)
                "first_seen": today,
                "last_seen": today,
                "zones": [zone] if zone else [],  # Don't add "Unknown" - leave empty if zone unknown
                "wiki_only": False
            }
        else:
            items[base_name]["count"] += count
            items[base_name]["drops"] = items[base_name].get("drops", 1) + 1  # Increment drop events
            items[base_name]["last_seen"] = today
            # Add zone if not already tracked
            if zone:
                item_zones = items[base_name].get("zones", [])
                if zone not in item_zones:
                    item_zones.append(zone)
                    item_zones.sort()
                    items[base_name]["zones"] = item_zones
            # Ensure wiki_only flag exists (backwards compatibility)
            if "wiki_only" not in items[base_name]:
                items[base_name]["wiki_only"] = False

        return is_new

    def _record_skinning(self, creature: str, base_name: str, count: int = 1) -> bool:
        """
        Record a skinning drop. Returns True if this is a new skinning item for this creature.
        """
        if creature not in self.creature_data:
            self.creature_data[creature] = {"kills": 0, "zones": [], "items": {}, "skinning": {}, "butchering": {}}

        # Ensure skinning dict exists (backwards compatibility)
        if "skinning" not in self.creature_data[creature]:
            self.creature_data[creature]["skinning"] = {}

        skinning = self.creature_data[creature]["skinning"]
        today = datetime.now().strftime("%Y-%m-%d")
        is_new = base_name not in skinning

        if is_new:
            skinning[base_name] = {
                "count": count,
                "drops": 1,  # Number of drop events (for drop rate calculation)
                "first_seen": today,
                "last_seen": today
            }
        else:
            skinning[base_name]["count"] += count
            skinning[base_name]["drops"] = skinning[base_name].get("drops", 1) + 1  # Increment drop events
            skinning[base_name]["last_seen"] = today

        return is_new

    def _record_butchering(self, creature: str, base_name: str, count: int = 1) -> bool:
        """
        Record a butchering drop. Returns True if this is a new butchering item for this creature.
        """
        if creature not in self.creature_data:
            self.creature_data[creature] = {"kills": 0, "zones": [], "items": {}, "skinning": {}, "butchering": {}}

        # Ensure butchering dict exists (backwards compatibility)
        if "butchering" not in self.creature_data[creature]:
            self.creature_data[creature]["butchering"] = {}

        butchering = self.creature_data[creature]["butchering"]
        today = datetime.now().strftime("%Y-%m-%d")
        is_new = base_name not in butchering

        if is_new:
            butchering[base_name] = {
                "count": count,
                "drops": 1,  # Number of drop events (for drop rate calculation)
                "first_seen": today,
                "last_seen": today
            }
        else:
            butchering[base_name]["count"] += count
            butchering[base_name]["drops"] = butchering[base_name].get("drops", 1) + 1  # Increment drop events
            butchering[base_name]["last_seen"] = today

        return is_new

    def parse_line(self, line: str) -> Optional[dict]:
        """Parse a single chat log line and return event info if relevant."""
        match = self.LOG_LINE_PATTERN.match(line.strip())
        if not match:
            return None

        timestamp_str, channel, message = match.groups()

        # Parse timestamp for zone lookup and loot window check
        timestamp = None
        try:
            timestamp = datetime.strptime(timestamp_str, "%y-%m-%d %H:%M:%S")
            self.current_zone = self._get_zone_at_time(timestamp)
        except ValueError:
            pass

        if channel == "Combat":
            # Check for combat target
            target_match = self.COMBAT_TARGET_PATTERN.search(message)
            if target_match:
                creature_name = target_match.group(1)
                # New combat target - reset kill state
                if creature_name != self.current_creature:
                    self.current_creature = creature_name
                    self.creature_killed = False
                    self.kill_timestamp = None

                # Check for fatality ON THE SAME LINE
                if self.FATALITY_PATTERN.search(message):
                    self.creature_killed = True
                    self.kill_timestamp = timestamp
                    if self.current_creature:
                        self._record_kill(self.current_creature, self.current_zone)
                    return {"type": "kill", "creature": self.current_creature, "zone": self.current_zone}

                return {"type": "combat", "creature": creature_name, "zone": self.current_zone}

            # Check for fatality without target (edge case)
            if self.FATALITY_PATTERN.search(message):
                self.creature_killed = True
                self.kill_timestamp = timestamp
                if self.current_creature:
                    self._record_kill(self.current_creature, self.current_zone)
                return {"type": "kill", "creature": self.current_creature, "zone": self.current_zone}

        elif channel == "Status":
            # Check for skinning XP - retrospectively classify last loot as skinning
            is_skinning = self.SKINNING_XP_PATTERN.match(message)
            is_butchering = self.BUTCHERING_XP_PATTERN.match(message)

            if is_skinning or is_butchering:
                # If there was loot on the SAME SECOND, reclassify it as skinning/butchering.
                # Actual skinning/butchering items appear on the same timestamp as the XP.
                # Regular loot (like Pixie Sugar) appears 1+ seconds before any XP.
                if self.last_loot and timestamp:
                    time_diff = (timestamp - self.last_loot["timestamp"]).total_seconds()
                    if 0 <= time_diff < 1:
                        creature = self.last_loot["creature"]
                        base_name = self.last_loot["base_name"]
                        count = self.last_loot["count"]

                        # Move from regular loot to skinning or butchering
                        if creature in self.creature_data:
                            items = self.creature_data[creature].get("items", {})
                            if base_name in items:
                                # Remove from regular loot
                                del items[base_name]
                            # Add to appropriate category
                            if is_skinning:
                                self._record_skinning(creature, base_name, count)
                            else:
                                self._record_butchering(creature, base_name, count)
                            self._save_creature_data()

                self.last_loot = None
                xp_type = "skinning_xp" if is_skinning else "butchering_xp"
                return {"type": xp_type, "creature": self.current_creature}

            # Check for loot
            loot_match = self.LOOT_PATTERN.match(message)
            if loot_match:
                item_name = loot_match.group(1)
                count = int(loot_match.group(2)) if loot_match.group(2) else 1
                base_name = self.strip_prefixes(item_name)

                # Check if we're within the loot window (30 seconds after kill)
                in_loot_window = False
                if self.creature_killed and self.kill_timestamp and timestamp:
                    time_since_kill = (timestamp - self.kill_timestamp).total_seconds()
                    in_loot_window = 0 <= time_since_kill <= self.loot_window_seconds

                # Associate with killed creature (regular loot) only if in loot window
                if in_loot_window and self.current_creature:
                    is_new = self._record_loot(self.current_creature, base_name, count,
                                               zone=self.current_zone)
                    # Track this loot for potential skinning reclassification
                    self.last_loot = {
                        "creature": self.current_creature,
                        "base_name": base_name,
                        "count": count,
                        "timestamp": timestamp
                    }
                    return {
                        "type": "loot",
                        "creature": self.current_creature,
                        "item": item_name,
                        "base_name": base_name,
                        "count": count,
                        "is_new": is_new,
                        "zone": self.current_zone
                    }

        return None

    def parse_log_file(self, file_path: Path, callback=None) -> dict[str, set[str]]:
        """
        Parse a single log file and return new loot found.

        Args:
            file_path: Path to the log file
            callback: Optional function to call with progress updates

        Returns:
            Dict of creature_name -> set of new base item names found
        """
        file_name = file_path.name

        # Check if this is today's log (current session - zone tracking is valid)
        self._is_current_session = self._is_today(file_name)

        # Load zone transitions from persistent history
        self.zone_transitions = self._load_zone_history()
        if callback and self.zone_transitions:
            callback(f"  Found {len(self.zone_transitions)} zone transitions in history")

        # Get last processed line for this file
        last_line = self.processed_state["files"].get(file_name, 0)

        new_loot: dict[str, set[str]] = defaultdict(set)
        current_line = 0

        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            # First, try to find timezone offset from the login line
            first_line = f.readline()
            tz_match = self.TIMEZONE_PATTERN.search(first_line)
            if tz_match:
                sign = 1 if tz_match.group(1) == '+' else -1
                hours = int(tz_match.group(2))
                self._timezone_offset_hours = sign * hours
            f.seek(0)  # Reset to beginning

            for line_num, line in enumerate(f, 1):
                current_line = line_num

                # Skip already processed lines
                if line_num <= last_line:
                    continue

                result = self.parse_line(line)
                if result and result["type"] == "loot" and result["is_new"]:
                    new_loot[result["creature"]].add(result["base_name"])

        # Update state
        self.processed_state["files"][file_name] = current_line

        return new_loot

    def process_all_logs(self, callback=None) -> dict[str, dict]:
        """
        Process all chat log files.

        Args:
            callback: Optional function(message: str) for progress updates

        Returns:
            Dict with processing results per creature
        """
        results = {}

        if not self.chatlog_dir.exists():
            if callback:
                callback(f"Error: Chat log directory not found: {self.chatlog_dir}")
            return results

        # Capture zone transitions and skinning/butchering/loot history FIRST
        # This prevents data loss if Player.log gets overwritten between sessions
        self._update_zone_history()
        self._update_skinning_history()
        self._update_butchering_history()
        self._update_loot_history()

        log_files = sorted(self.chatlog_dir.glob("Chat-*.log"))

        if not log_files:
            if callback:
                callback("No chat log files found.")
            return results

        all_new_loot: dict[str, set[str]] = defaultdict(set)

        for log_file in log_files:
            if callback:
                callback(f"Processing {log_file.name}...")

            # Reset parsing state for each file
            self.current_creature = None
            self.creature_killed = False
            self.current_zone = None
            self.kill_timestamp = None
            self.last_loot = None

            new_loot = self.parse_log_file(log_file, callback)

            # Mirror the processed log file
            self._mirror_log_file(log_file)

            for creature, items in new_loot.items():
                all_new_loot[creature].update(items)

                if callback and items:
                    zone_info = ""
                    if creature in self.creature_data and self.creature_data[creature].get("zones"):
                        zones = self.creature_data[creature]["zones"]
                        zone_info = f" [{', '.join(zones)}]"
                    callback(f"  [NEW] {creature}{zone_info}: +{len(items)} items ({', '.join(sorted(items))})")

        # Generate results
        for creature, new_items in all_new_loot.items():
            if new_items:
                results[creature] = {
                    "new_items": new_items,
                    "status": "new" if len(self.creature_data.get(creature, {}).get("items", {})) == len(new_items) else "update"
                }

        # Save everything
        self._save_state()
        self._save_creature_data()
        self._generate_wiki_files()

        # Update zone history (appends new transitions)
        self._update_zone_history()

        return results

    def _generate_wiki_files(self):
        """Generate wiki syntax files from creature data."""
        self.output_dir.mkdir(exist_ok=True)

        for creature, data in self.creature_data.items():
            items = sorted(data.get("items", {}).keys())
            if not items:
                continue

            file_path = self.output_dir / f"{creature}.txt"
            wiki_content = self.generate_wiki_syntax(items)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(wiki_content)

    def generate_wiki_syntax(self, items: list[str]) -> str:
        """Generate wiki-formatted loot table syntax (clean, copy-paste ready)."""
        if not items:
            return "==Reported Loot==\nNo loot reported yet.\n"

        lines = ["==Reported Loot==", "{|"]
        lines.extend(self._format_loot_table(sorted(items)))
        lines.append("|}")

        return '\n'.join(lines) + '\n'

    def get_creatures_needing_updates(self, results: dict[str, dict]) -> list[tuple[str, Path]]:
        """Get list of creatures that received new loot entries."""
        updates = []
        for creature, data in results.items():
            if data["new_items"]:
                file_path = self.output_dir / f"{creature}.txt"
                updates.append((creature, file_path))
        return sorted(updates)

    def _parse_log_timestamp_utc(self, timestamp_str: str) -> str:
        """
        Parse a log timestamp and convert to UTC ISO format.

        Args:
            timestamp_str: Timestamp from log like "25-02-07 14:30:00"

        Returns:
            UTC timestamp in ISO format like "2025-02-07T14:30:00Z"
        """
        try:
            local_time = datetime.strptime(timestamp_str, "%y-%m-%d %H:%M:%S")
            # Convert to UTC by subtracting the timezone offset
            utc_time = local_time - timedelta(hours=self._timezone_offset_hours)
            return utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return None

    def _is_timestamp_newer(self, new_timestamp: str, last_updated: str) -> bool:
        """
        Check if new_timestamp is newer than last_updated.

        Args:
            new_timestamp: UTC timestamp in ISO format
            last_updated: UTC timestamp in ISO format (or None)

        Returns:
            True if new_timestamp is newer or last_updated is None
        """
        if not last_updated:
            return True
        if not new_timestamp:
            return False
        return new_timestamp > last_updated

    def full_rescan(self, callback=None) -> dict:
        """
        Full rescan of all logs. Only processes entries newer than last_updated.
        Returns stats about what was found.
        """
        if not self.chatlog_dir.exists():
            return {}

        # Capture zone transitions and skinning/butchering/loot history FIRST
        # This prevents data loss if Player.log gets overwritten between sessions
        self._update_zone_history()
        self._update_skinning_history()
        self._update_butchering_history()
        self._update_loot_history()

        log_files = sorted(self.chatlog_dir.glob("Chat-*.log"))
        stats = {"new_creatures": 0, "new_items": 0, "new_skinning": 0, "new_butchering": 0, "skipped_old": 0}

        # DEBUG: Track kill counts to identify double-counting bug
        debug_kill_counts = {}

        for log_file in log_files:
            if callback:
                callback(f"Rescanning {log_file.name}...")

            # Check if this is today's log (current session - zone tracking is valid)
            is_current_session = self._is_today(log_file.name)

            # Load zone transitions from persistent history
            self.zone_transitions = self._load_zone_history()

            # Reset state for this file
            current_creature = None
            creature_killed = False
            current_zone = None
            current_utc_timestamp = None
            kill_timestamp = None  # Track when the kill happened for loot window
            last_loot = None  # Track last loot for retrospective skinning detection

            line_count = 0  # Track total lines for processed_state update

            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                # First, try to find timezone offset from the login line
                first_line = f.readline()
                tz_match = self.TIMEZONE_PATTERN.search(first_line)
                if tz_match:
                    sign = 1 if tz_match.group(1) == '+' else -1
                    hours = int(tz_match.group(2))
                    self._timezone_offset_hours = sign * hours
                f.seek(0)  # Reset to beginning

                for line_count, line in enumerate(f, 1):
                    match = self.LOG_LINE_PATTERN.match(line.strip())
                    if not match:
                        continue

                    timestamp_str, channel, message = match.groups()

                    # Parse timestamp to UTC for comparison
                    current_utc_timestamp = self._parse_log_timestamp_utc(timestamp_str)

                    # Parse timestamp for zone lookup (works for all logs now)
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%y-%m-%d %H:%M:%S")
                        current_zone = self._get_zone_at_time(timestamp)
                    except ValueError:
                        pass

                    # Parse timestamp for loot window checking
                    current_timestamp = None
                    try:
                        current_timestamp = datetime.strptime(timestamp_str, "%y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass

                    if channel == "Combat":
                        # Check for combat target
                        target_match = self.COMBAT_TARGET_PATTERN.search(message)
                        if target_match:
                            new_creature = target_match.group(1)
                            if new_creature != current_creature:
                                current_creature = new_creature
                                creature_killed = False
                                kill_timestamp = None

                        # Check for fatality
                        if self.FATALITY_PATTERN.search(message) and current_creature:
                            # Always track kill state for loot attribution
                            creature_killed = True
                            kill_timestamp = current_timestamp

                            # Check if this entry is newer than what we've already processed
                            last_updated = None
                            if current_creature in self.creature_data:
                                last_updated = self.creature_data[current_creature].get("last_updated")

                            if not self._is_timestamp_newer(current_utc_timestamp, last_updated):
                                # Skip incrementing kills - we've already counted this kill
                                # But keep creature_killed=True so loot can still be attributed
                                stats["skipped_old"] += 1
                                continue

                            # Create creature entry if new
                            if current_creature not in self.creature_data:
                                self.creature_data[current_creature] = {
                                    "kills": 0, "zones": [], "items": {}, "skinning": {}, "butchering": {}
                                }
                                stats["new_creatures"] += 1
                                if callback:
                                    callback(f"  [NEW] {current_creature}")

                            # Increment kills
                            self.creature_data[current_creature]["kills"] += 1

                            # DEBUG: Track this kill increment
                            if current_creature not in debug_kill_counts:
                                debug_kill_counts[current_creature] = 0
                            debug_kill_counts[current_creature] += 1

                            # Update last_updated timestamp
                            self.creature_data[current_creature]["last_updated"] = current_utc_timestamp

                            # Add zone if not present (use "Unknown" if no zone data)
                            zone_to_add = current_zone if current_zone else "Unknown"
                            zones = self.creature_data[current_creature].get("zones", [])
                            if zone_to_add not in zones:
                                zones.append(zone_to_add)
                                zones.sort()
                                self.creature_data[current_creature]["zones"] = zones

                            # Zone self-healing: fix incorrect zone assignments
                            if current_zone and current_creature in self.creature_data:
                                creature_zones = self.creature_data[current_creature].get("zones", [])
                                # If creature has zones but current_zone is not in them, it's a mismatch
                                # We replace with the correct zone from Player.log
                                if creature_zones and current_zone not in creature_zones:
                                    if callback:
                                        callback(f"  [ZONE FIX] {current_creature}: {creature_zones} -> [{current_zone}]")
                                    self.creature_data[current_creature]["zones"] = [current_zone]
                                    # Also fix item zones
                                    for item_name, item_data in self.creature_data[current_creature].get("items", {}).items():
                                        if item_data.get("zones"):
                                            item_data["zones"] = [current_zone]

                    elif channel == "Status":
                        # Skinning/butchering XP - retrospectively classify last loot
                        is_skinning = self.SKINNING_XP_PATTERN.match(message)
                        is_butchering = self.BUTCHERING_XP_PATTERN.match(message)

                        if is_skinning or is_butchering:
                            # Only reclassify if loot was on the SAME SECOND as XP.
                            # Regular loot appears 1+ seconds before any skinning/butchering XP.
                            if last_loot and current_timestamp:
                                time_diff = (current_timestamp - last_loot["timestamp"]).total_seconds()
                                if 0 <= time_diff < 1:
                                    loot_creature = last_loot["creature"]
                                    loot_base_name = last_loot["base_name"]
                                    loot_count = last_loot["count"]
                                    today = datetime.now().strftime("%Y-%m-%d")

                                    if loot_creature in self.creature_data:
                                        # Remove from regular loot
                                        items = self.creature_data[loot_creature].get("items", {})
                                        if loot_base_name in items:
                                            del items[loot_base_name]
                                            stats["new_items"] -= 1  # Adjust count

                                        # Add to skinning or butchering
                                        if is_skinning:
                                            category = self.creature_data[loot_creature].setdefault("skinning", {})
                                            stat_key = "new_skinning"
                                        else:
                                            category = self.creature_data[loot_creature].setdefault("butchering", {})
                                            stat_key = "new_butchering"

                                        if loot_base_name not in category:
                                            category[loot_base_name] = {
                                                "count": loot_count,
                                                "drops": 1,  # Number of drop events
                                                "first_seen": today,
                                                "last_seen": today
                                            }
                                            stats[stat_key] = stats.get(stat_key, 0) + 1
                                        else:
                                            category[loot_base_name]["count"] += loot_count
                                            category[loot_base_name]["drops"] = category[loot_base_name].get("drops", 1) + 1
                                            category[loot_base_name]["last_seen"] = today

                            last_loot = None
                            continue

                        # Check if we're within the loot window (30 seconds after kill)
                        in_loot_window = False
                        if creature_killed and kill_timestamp and current_timestamp:
                            time_since_kill = (current_timestamp - kill_timestamp).total_seconds()
                            in_loot_window = 0 <= time_since_kill <= self.loot_window_seconds

                        # Loot - only attribute if within loot window
                        loot_match = self.LOOT_PATTERN.match(message)
                        if loot_match and current_creature and in_loot_window and current_creature in self.creature_data:
                            item_name = loot_match.group(1)
                            count = int(loot_match.group(2)) if loot_match.group(2) else 1
                            base_name = self.strip_prefixes(item_name)
                            today = datetime.now().strftime("%Y-%m-%d")

                            # Regular loot (may be reclassified as skinning later)
                            items = self.creature_data[current_creature].setdefault("items", {})
                            if base_name not in items:
                                items[base_name] = {
                                    "count": count,
                                    "drops": 1,  # Number of drop events (for drop rate calculation)
                                    "first_seen": today,
                                    "last_seen": today,
                                    "zones": [current_zone] if current_zone else ["Unknown"],
                                    "wiki_only": False
                                }
                                stats["new_items"] += 1
                            else:
                                items[base_name]["count"] += count
                                items[base_name]["drops"] = items[base_name].get("drops", 1) + 1  # Increment drop events
                                items[base_name]["last_seen"] = today
                                # Add zone if not already tracked
                                if current_zone:
                                    item_zones = items[base_name].get("zones", [])
                                    if current_zone not in item_zones:
                                        item_zones.append(current_zone)
                                        item_zones.sort()
                                        items[base_name]["zones"] = item_zones
                                # Ensure wiki_only flag exists
                                if "wiki_only" not in items[base_name]:
                                    items[base_name]["wiki_only"] = False

                            # Track for potential skinning reclassification
                            last_loot = {
                                "creature": current_creature,
                                "base_name": base_name,
                                "count": count,
                                "timestamp": current_timestamp
                            }

            # Update processed_state so incremental updates don't re-process these lines
            self.processed_state["files"][log_file.name] = line_count

        # Save processed state so auto-update knows where to start
        self._save_state()
        self._save_creature_data()

        # Mirror all log files after full rescan
        self._mirror_all_logs()

        if callback:
            callback(f"Rescan complete: {stats['new_creatures']} new creatures, {stats['new_items']} new items, {stats['new_skinning']} skinning, {stats.get('new_butchering', 0)} butchering")
            if stats["skipped_old"] > 0:
                callback(f"  (Skipped {stats['skipped_old']} already-processed entries)")

            # DEBUG: Output kill counts to identify double-counting
            callback(f"DEBUG: Kill increments in full_rescan (first 10):")
            for i, (creature, count) in enumerate(sorted(debug_kill_counts.items(), key=lambda x: -x[1])[:10]):
                callback(f"  {creature}: {count} kills")

        return stats

    def rescan_for_skinning(self, callback=None) -> int:
        """
        Re-scan all logs specifically for skinning data.
        Only adds skinning data, does not duplicate kills or loot.
        Returns count of skinning items found.
        """
        if not self.chatlog_dir.exists():
            return 0

        log_files = sorted(self.chatlog_dir.glob("Chat-*.log"))
        total_skinning = 0
        current_creature = None
        skinning_active = False

        for log_file in log_files:
            if callback:
                callback(f"Scanning {log_file.name} for skinning...")

            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    match = self.LOG_LINE_PATTERN.match(line.strip())
                    if not match:
                        continue

                    timestamp_str, channel, message = match.groups()

                    if channel == "Combat":
                        # Track current creature target
                        target_match = self.COMBAT_TARGET_PATTERN.search(message)
                        if target_match:
                            current_creature = target_match.group(1)

                    elif channel == "Status":
                        # Check for skinning/butchering XP
                        if self.SKINNING_XP_PATTERN.match(message) or self.BUTCHERING_XP_PATTERN.match(message):
                            skinning_active = True
                            continue

                        # Check for loot after skinning
                        if skinning_active:
                            loot_match = self.LOOT_PATTERN.match(message)
                            if loot_match and current_creature:
                                item_name = loot_match.group(1)
                                count = int(loot_match.group(2)) if loot_match.group(2) else 1
                                base_name = self.strip_prefixes(item_name)

                                # Only add if creature exists in our data
                                if current_creature in self.creature_data:
                                    # Ensure skinning dict exists
                                    if "skinning" not in self.creature_data[current_creature]:
                                        self.creature_data[current_creature]["skinning"] = {}

                                    skinning = self.creature_data[current_creature]["skinning"]
                                    today = datetime.now().strftime("%Y-%m-%d")

                                    if base_name not in skinning:
                                        skinning[base_name] = {
                                            "count": count,
                                            "first_seen": today,
                                            "last_seen": today
                                        }
                                        total_skinning += 1
                                        if callback:
                                            callback(f"  [SKINNING] {current_creature}: {base_name}")
                                    else:
                                        skinning[base_name]["count"] += count
                                        skinning[base_name]["last_seen"] = today

                                skinning_active = False

        # Save updated data
        self._save_creature_data()

        if callback:
            callback(f"Found {total_skinning} new skinning items")

        return total_skinning

    def get_creature_stats(self, creature: str) -> Optional[dict]:
        """Get full stats for a creature."""
        if creature not in self.creature_data:
            return None

        data = self.creature_data[creature]
        kills = data.get("kills", 0)
        items = data.get("items", {})
        skinning = data.get("skinning", {})
        butchering = data.get("butchering", {})
        zones = data.get("zones", [])

        stats = {
            "kills": kills,
            "zones": zones,
            "items": {},
            "skinning": {},
            "butchering": {}
        }

        for item_name, item_data in items.items():
            count = item_data.get("count", 0)
            # Use drops for rate calculation, fallback to count for old data
            drops = item_data.get("drops", item_data.get("count", 0))
            # wiki_only items don't count toward drop rate
            wiki_only = item_data.get("wiki_only", False)
            drop_rate = (drops / kills * 100) if kills > 0 and not wiki_only else 0

            stats["items"][item_name] = {
                "count": count,
                "drops": drops,
                "drop_rate": round(drop_rate, 2),
                "first_seen": item_data.get("first_seen"),
                "last_seen": item_data.get("last_seen"),
                "zones": item_data.get("zones", []),
                "wiki_only": wiki_only
            }

        for item_name, item_data in skinning.items():
            count = item_data.get("count", 0)
            # Use drops for rate calculation, fallback to count for old data
            drops = item_data.get("drops", item_data.get("count", 0))
            drop_rate = (drops / kills * 100) if kills > 0 else 0

            stats["skinning"][item_name] = {
                "count": count,
                "drops": drops,
                "drop_rate": round(drop_rate, 2),
                "first_seen": item_data.get("first_seen"),
                "last_seen": item_data.get("last_seen")
            }

        for item_name, item_data in butchering.items():
            count = item_data.get("count", 0)
            # Use drops for rate calculation, fallback to count for old data
            drops = item_data.get("drops", item_data.get("count", 0))
            drop_rate = (drops / kills * 100) if kills > 0 else 0

            stats["butchering"][item_name] = {
                "count": count,
                "drops": drops,
                "drop_rate": round(drop_rate, 2),
                "first_seen": item_data.get("first_seen"),
                "last_seen": item_data.get("last_seen")
            }

        return stats

    def get_aggregate_stats(self) -> dict:
        """
        Get aggregate statistics across all creatures.

        Returns:
            Dict with:
                - total_creatures: Number of creatures tracked
                - total_kills: Sum of all kills
                - unique_items: Count of unique loot items
                - skinning_items: Count of unique skinning items
                - butchering_items: Count of unique butchering items
                - top_creature: Tuple of (name, kills) for most killed creature
                - rarest_drop: Tuple of (item, creature, rate) for lowest drop rate
        """
        stats = {
            "total_creatures": 0,
            "total_kills": 0,
            "unique_items": 0,
            "skinning_items": 0,
            "butchering_items": 0,
            "top_creature": None,
            "rarest_drop": None
        }

        if not self.creature_data:
            return stats

        stats["total_creatures"] = len(self.creature_data)

        all_items = set()
        all_skinning = set()
        all_butchering = set()
        top_kills = 0
        top_creature_name = None
        rarest_rate = float('inf')
        rarest_item = None
        rarest_creature = None

        for creature_name, data in self.creature_data.items():
            kills = data.get("kills", 0)
            stats["total_kills"] += kills

            # Track top creature
            if kills > top_kills:
                top_kills = kills
                top_creature_name = creature_name

            # Count unique items
            items = data.get("items", {})
            for item_name, item_data in items.items():
                all_items.add(item_name)

                # Find rarest drop (exclude wiki_only items, require drops > 0)
                # Use drops for rate calculation, fallback to count for old data
                drops = item_data.get("drops", item_data.get("count", 0))
                if not item_data.get("wiki_only", False) and drops > 0:
                    if kills > 0:
                        drop_rate = (drops / kills) * 100
                        if drop_rate < rarest_rate:
                            rarest_rate = drop_rate
                            rarest_item = item_name
                            rarest_creature = creature_name

            # Count skinning items
            skinning = data.get("skinning", {})
            for item_name in skinning.keys():
                all_skinning.add(item_name)

            # Count butchering items
            butchering = data.get("butchering", {})
            for item_name in butchering.keys():
                all_butchering.add(item_name)

        stats["unique_items"] = len(all_items)
        stats["skinning_items"] = len(all_skinning)
        stats["butchering_items"] = len(all_butchering)

        if top_creature_name:
            stats["top_creature"] = (top_creature_name, top_kills)

        if rarest_item and rarest_rate < float('inf'):
            stats["rarest_drop"] = (rarest_item, rarest_creature, rarest_rate)

        return stats

    def extract_creature_name_from_wiki(self, wiki_text: str) -> str | None:
        """Extract creature name from MOB infobox title field."""
        # Pattern: {{MOB infobox | title = Creature Name | ...}}
        pattern = re.compile(r'\{\{MOB\s+infobox[^}]*\|\s*title\s*=\s*([^|}\n]+)', re.IGNORECASE | re.DOTALL)
        match = pattern.search(wiki_text)
        if match:
            return match.group(1).strip()
        return None

    def parse_wiki_loot(self, wiki_text: str) -> dict[str, list[str]]:
        """
        Parse wiki page content and extract loot items by zone.

        Args:
            wiki_text: The raw wiki page content

        Returns:
            Dict mapping zone names to lists of item names.
            Special key "general" for zone-agnostic loot.
        """
        result = defaultdict(list)

        # Patterns for parsing
        loot_pattern = re.compile(r'\{\{Loot\|([^}|]+)(?:\|[^}]*)?\}\}')
        # Match zone section headers like "==== [[Sun Vale]] Loot ===="
        zone_header_pattern = re.compile(r'====\s*\[\[([^\]]+)\]\]\s*Loot\s*====', re.IGNORECASE)
        # Match general loot header like "==== General Loot ===="
        general_header_pattern = re.compile(r'====\s*General\s*Loot\s*====', re.IGNORECASE)
        # Match section headers (any ==== header)
        any_header_pattern = re.compile(r'====\s*.+?\s*====')

        lines = wiki_text.split('\n')
        current_zone = None  # None means we haven't seen a loot section yet

        for line in lines:
            # Check for zone-specific loot header
            zone_match = zone_header_pattern.search(line)
            if zone_match:
                current_zone = zone_match.group(1)
                continue

            # Check for general loot header
            if general_header_pattern.search(line):
                current_zone = "general"
                continue

            # Check if we hit a different section (not a loot section)
            if any_header_pattern.search(line) and not zone_header_pattern.search(line) and not general_header_pattern.search(line):
                # If the header contains "Loot" but doesn't match our patterns, still treat as loot
                if "loot" in line.lower():
                    # Default to general for unrecognized loot sections
                    current_zone = "general"
                else:
                    # Non-loot section - stop tracking
                    current_zone = None
                continue

            # Extract loot items if we're in a loot section
            if current_zone is not None:
                for match in loot_pattern.finditer(line):
                    item_name = match.group(1).strip()
                    if item_name and item_name not in result[current_zone]:
                        result[current_zone].append(item_name)

        return dict(result)

    def merge_wiki_items(self, creature: str, wiki_items: dict[str, list[str]]) -> dict:
        """
        Merge wiki items into creature data.
        Items not in our database get added with count=0, wiki_only=True.

        Args:
            creature: The creature name
            wiki_items: Dict mapping zone names to lists of item names

        Returns:
            Dict with merge statistics: {"added": int, "existing": int}
        """
        if creature not in self.creature_data:
            self.creature_data[creature] = {"kills": 0, "zones": [], "items": {}, "skinning": {}, "butchering": {}}

        items = self.creature_data[creature]["items"]
        creature_zones = self.creature_data[creature].get("zones", [])
        today = datetime.now().strftime("%Y-%m-%d")

        stats = {"added": 0, "existing": 0}

        for zone, item_list in wiki_items.items():
            # Determine the actual zone name (or None for general)
            actual_zone = None if zone == "general" else zone

            for item_name in item_list:
                if item_name in items:
                    # Item exists - add zone if not tracked
                    stats["existing"] += 1
                    if actual_zone:
                        item_zones = items[item_name].get("zones", [])
                        if actual_zone not in item_zones:
                            item_zones.append(actual_zone)
                            item_zones.sort()
                            items[item_name]["zones"] = item_zones
                else:
                    # New item from wiki
                    stats["added"] += 1
                    items[item_name] = {
                        "count": 0,
                        "first_seen": today,
                        "last_seen": today,
                        "zones": [actual_zone] if actual_zone else [],
                        "wiki_only": True
                    }

        # Save changes
        self._save_creature_data()

        return stats

    def _format_loot_table(self, item_list: list[str], items_per_row: int = 4) -> list[str]:
        """
        Format a list of items into wiki table rows with line breaks every N items.

        Args:
            item_list: List of item names (should be pre-sorted)
            items_per_row: Number of items per row before adding a line break

        Returns:
            List of lines for the wiki table (without {| and |})
        """
        lines = []
        for i, item in enumerate(item_list):
            lines.append(f"|{{{{Loot|{item}}}}}")
            # Add row break after every N items, but not after the last item
            if (i + 1) % items_per_row == 0 and i < len(item_list) - 1:
                lines.append("|-")
        return lines

    def generate_wiki_syntax_with_zones(self, creature: str) -> str:
        """
        Generate wiki-formatted loot table syntax with zone-specific sections.

        Args:
            creature: The creature name

        Returns:
            Wiki syntax string with zone sections
        """
        if creature not in self.creature_data:
            return "== Reported Loot ==\nNo loot reported yet.\n"

        data = self.creature_data[creature]
        items = data.get("items", {})
        creature_zones = data.get("zones", [])
        skinning = data.get("skinning", {})
        butchering = data.get("butchering", {})

        if not items and not skinning and not butchering:
            return "== Reported Loot ==\nNo loot reported yet.\n"

        # Categorize items by zone count:
        # - Single-zone items (not Unknown) → zone-specific section
        # - Multi-zone items or Unknown zone → General Loot
        general_items = []  # Items that drop in multiple zones or Unknown
        zone_items = defaultdict(list)  # Items for specific zones (single-zone only)

        for item_name, item_data in items.items():
            item_zones = item_data.get("zones", [])

            # Multi-zone or no zone → General Loot
            if len(item_zones) != 1:
                general_items.append(item_name)
            elif item_zones[0] == "Unknown":
                # Unknown zone → General Loot
                general_items.append(item_name)
            else:
                # Single zone (not Unknown) → zone-specific
                zone_items[item_zones[0]].append(item_name)

        lines = ["== Reported Loot ==", ""]

        # General loot section
        if general_items:
            lines.append("==== General Loot ====")
            lines.append("{|")
            lines.extend(self._format_loot_table(sorted(general_items)))
            lines.append("|}")
            lines.append("")

        # Zone-specific sections
        for zone in sorted(zone_items.keys()):
            zone_item_list = zone_items[zone]
            if zone_item_list:
                lines.append(f"==== [[{zone}]] Loot ====")
                lines.append("{|")
                lines.extend(self._format_loot_table(sorted(zone_item_list)))
                lines.append("|}")
                lines.append("")

        # Skinning section
        if skinning:
            lines.append("== Skinning ==")
            lines.append("{|")
            lines.extend(self._format_loot_table(sorted(skinning.keys())))
            lines.append("|}")
            lines.append("")

        # Butchering section
        if butchering:
            lines.append("== Butchering ==")
            lines.append("{|")
            lines.extend(self._format_loot_table(sorted(butchering.keys())))
            lines.append("|}")
            lines.append("")

        return "\n".join(lines)

    def insert_loot_into_wiki(self, creature: str, wiki_text: str) -> str:
        """
        Replace the Reported Loot section with regenerated content from our database.

        This preserves all other wiki sections (MOB infobox, Locations, Combat Abilities, etc.)
        while replacing the loot-related sections (Reported Loot, Skinning, Butchering) with
        properly formatted content generated from our merged data.

        Args:
            creature: The creature name
            wiki_text: The original wiki page content

        Returns:
            Updated wiki content with replaced loot sections
        """
        if creature not in self.creature_data:
            return wiki_text

        # Generate the fresh loot content from our merged data
        new_loot_content = self.generate_wiki_syntax_with_zones(creature)

        # Find the start of the Reported Loot section
        loot_start_match = re.search(r'^==\s*Reported\s+Loot\s*==', wiki_text, re.MULTILINE | re.IGNORECASE)

        if not loot_start_match:
            # No Reported Loot section found - append our content at the end
            return wiki_text.rstrip() + "\n\n" + new_loot_content

        loot_start = loot_start_match.start()

        # Find the end of loot-related sections
        # Loot sections include: Reported Loot, Skinning, Butchering
        # We need to find the next top-level section (== X ==) that isn't one of these
        remaining_text = wiki_text[loot_start:]

        # Pattern to match top-level sections (== ... == but not ==== ... ====)
        # This works because [^=\n]+? requires at least one non-= character after the opening ==
        section_pattern = re.compile(r'^==\s*([^=\n]+?)\s*==\s*$', re.MULTILINE)

        loot_related_sections = {'reported loot', 'skinning', 'butchering'}
        end_of_loot = len(wiki_text)  # Default to end of document

        for match in section_pattern.finditer(remaining_text):
            if match.start() == 0:
                # Skip the first match (Reported Loot itself)
                continue

            section_name = match.group(1).strip().lower()
            if section_name not in loot_related_sections:
                # Found a non-loot section - this is where loot content ends
                end_of_loot = loot_start + match.start()
                break

        # Build the result: content before loot + new loot + content after loot
        before_loot = wiki_text[:loot_start]
        after_loot = wiki_text[end_of_loot:]

        # Ensure proper spacing
        result = before_loot.rstrip()
        if result:
            result += "\n\n"
        result += new_loot_content.strip()
        if after_loot.strip():
            result += "\n\n" + after_loot.strip()

        return result + "\n"
