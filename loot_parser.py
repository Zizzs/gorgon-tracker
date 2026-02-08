"""
Core loot parsing logic for Gorgon Tracker.
Designed to be imported by CLI or GUI interfaces.
"""

import re
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict


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
    "AreaRahuSewers": "Rahu Sewer",
    "AreaRahu": "Rahu",
    "AreaDesertTown": "Amulna",
    "AreaRedWing": "Red Wing Casino",
    "AreaFaeRealm": "Fae Realm",
    "AreaWinterNexus": "Winter Nexus",
    "AreaLabyrinth": "Labyrinth",
    "AreaGoblinDungeon": "Goblin Dungeon",
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
}


class LootParser:
    """Parses chat logs and extracts creature loot data."""

    # Regex patterns for chat log
    LOG_LINE_PATTERN = re.compile(r'^(\d{2}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\t\[(\w+)\] (.+)$')
    COMBAT_TARGET_PATTERN = re.compile(r' on (.+?) #\d+[!:]')
    FATALITY_PATTERN = re.compile(r'\(FATALITY!\)$')
    LOOT_PATTERN = re.compile(r'^(.+?)(?: x(\d+))? added to inventory\.$')
    SKINNING_XP_PATTERN = re.compile(r'^You earned \d+ XP in Skinning\.$')
    BUTCHERING_XP_PATTERN = re.compile(r'^You earned \d+ XP in Butchering\.$')

    # Regex patterns for Player.log
    PLAYER_LOG_ZONE_PATTERN = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\] LOADING LEVEL (.+)$')

    # Pattern to extract timezone offset from chat log login line
    TIMEZONE_PATTERN = re.compile(r'Timezone Offset ([+-])(\d{2}):(\d{2}):(\d{2})')

    def __init__(self, chatlog_dir: str, output_dir: str = "CreaturePages",
                 state_file: str = "processed_logs.json", data_file: str = "creature_data.json"):
        self.chatlog_dir = Path(chatlog_dir)
        self.output_dir = Path(output_dir)
        self.state_file = Path(state_file)
        self.data_file = Path(data_file)

        # Player.log is in parent directory of ChatLogs
        self.player_log_path = self.chatlog_dir.parent / "Player.log"

        # Current parsing state
        self.current_creature: Optional[str] = None
        self.creature_killed = False
        self.current_zone: Optional[str] = None
        self.skinning_active = False  # True after skinning XP message

        # Zone transitions parsed from Player.log (time -> zone)
        self.zone_transitions: list[tuple[datetime, str]] = []

        # Track if we're parsing current session (Player.log is valid)
        self._is_current_session = False

        # Timezone offset from chat log (hours to subtract from local to get UTC)
        self._timezone_offset_hours = 0

        # Load creature data (source of truth)
        self.creature_data = self._load_creature_data()

        # Load processing state
        self.processed_state = self._load_state()

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

                        # Parse time and combine with reference date
                        try:
                            time_parts = time_str.split(':')
                            zone_time = reference_date.replace(
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

        Note: timestamp is in local time, zone_transitions are in UTC.
        We compare only the time portion (HH:MM:SS) to avoid date mismatch
        issues when UTC conversion crosses midnight.
        """
        # Convert local timestamp to UTC time-of-day for comparison
        utc_time = (timestamp - timedelta(hours=self._timezone_offset_hours)).time()

        current_zone = None

        for zone_time, zone_name in self.zone_transitions:
            if zone_time.time() <= utc_time:
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
        """Remove known modifier prefixes and suffixes from an item name to get the base name."""
        # First strip suffixes (e.g., "of Daggering", "of the Winter Court")
        name = SUFFIX_PATTERN.sub('', item_name)

        # Then strip prefixes
        words = name.split()

        # Keep removing prefixes from the start
        while words and words[0] in ALL_PREFIXES:
            words.pop(0)

        return ' '.join(words) if words else item_name

    def _record_kill(self, creature: str, zone: Optional[str] = None):
        """Record a creature kill."""
        if creature not in self.creature_data:
            self.creature_data[creature] = {"kills": 0, "zones": [], "items": {}}

        # Ensure zones list exists (for backwards compatibility)
        if "zones" not in self.creature_data[creature]:
            self.creature_data[creature]["zones"] = []

        self.creature_data[creature]["kills"] += 1

        # Add zone if known and not already recorded
        if zone and zone not in self.creature_data[creature]["zones"]:
            self.creature_data[creature]["zones"].append(zone)
            self.creature_data[creature]["zones"].sort()

    def _record_loot(self, creature: str, base_name: str, count: int = 1) -> bool:
        """
        Record a loot drop. Returns True if this is a new item for this creature.
        """
        if creature not in self.creature_data:
            self.creature_data[creature] = {"kills": 0, "zones": [], "items": {}, "skinning": {}}

        # Ensure skinning dict exists (backwards compatibility)
        if "skinning" not in self.creature_data[creature]:
            self.creature_data[creature]["skinning"] = {}

        items = self.creature_data[creature]["items"]
        today = datetime.now().strftime("%Y-%m-%d")
        is_new = base_name not in items

        if is_new:
            items[base_name] = {
                "count": count,
                "first_seen": today,
                "last_seen": today
            }
        else:
            items[base_name]["count"] += count
            items[base_name]["last_seen"] = today

        return is_new

    def _record_skinning(self, creature: str, base_name: str, count: int = 1) -> bool:
        """
        Record a skinning drop. Returns True if this is a new skinning item for this creature.
        """
        if creature not in self.creature_data:
            self.creature_data[creature] = {"kills": 0, "zones": [], "items": {}, "skinning": {}}

        # Ensure skinning dict exists (backwards compatibility)
        if "skinning" not in self.creature_data[creature]:
            self.creature_data[creature]["skinning"] = {}

        skinning = self.creature_data[creature]["skinning"]
        today = datetime.now().strftime("%Y-%m-%d")
        is_new = base_name not in skinning

        if is_new:
            skinning[base_name] = {
                "count": count,
                "first_seen": today,
                "last_seen": today
            }
        else:
            skinning[base_name]["count"] += count
            skinning[base_name]["last_seen"] = today

        return is_new

    def parse_line(self, line: str) -> Optional[dict]:
        """Parse a single chat log line and return event info if relevant."""
        match = self.LOG_LINE_PATTERN.match(line.strip())
        if not match:
            return None

        timestamp_str, channel, message = match.groups()

        # Parse timestamp for zone lookup
        try:
            timestamp = datetime.strptime(timestamp_str, "%y-%m-%d %H:%M:%S")
            self.current_zone = self._get_zone_at_time(timestamp)
        except ValueError:
            pass

        if channel == "Combat":
            # Check for combat target
            target_match = self.COMBAT_TARGET_PATTERN.match(message)
            if target_match:
                creature_name = target_match.group(1)
                # New combat target - reset kill state
                if creature_name != self.current_creature:
                    self.current_creature = creature_name
                    self.creature_killed = False
                return {"type": "combat", "creature": creature_name, "zone": self.current_zone}

            # Check for fatality
            if self.FATALITY_PATTERN.search(message):
                self.creature_killed = True
                if self.current_creature:
                    self._record_kill(self.current_creature, self.current_zone)
                return {"type": "kill", "creature": self.current_creature, "zone": self.current_zone}

        elif channel == "Status":
            # Check for skinning/butchering XP (marks next loot as skinning)
            if self.SKINNING_XP_PATTERN.match(message) or self.BUTCHERING_XP_PATTERN.match(message):
                self.skinning_active = True
                return {"type": "skinning_xp", "creature": self.current_creature}

            # Check for loot
            loot_match = self.LOOT_PATTERN.match(message)
            if loot_match:
                item_name = loot_match.group(1)
                count = int(loot_match.group(2)) if loot_match.group(2) else 1
                base_name = self.strip_prefixes(item_name)

                # Check if this is skinning loot
                if self.skinning_active and self.current_creature:
                    is_new = self._record_skinning(self.current_creature, base_name, count)
                    self.skinning_active = False  # Reset after capturing
                    return {
                        "type": "skinning",
                        "creature": self.current_creature,
                        "item": item_name,
                        "base_name": base_name,
                        "count": count,
                        "is_new": is_new,
                        "zone": self.current_zone
                    }

                # Associate with killed creature (regular loot)
                if self.creature_killed and self.current_creature:
                    is_new = self._record_loot(self.current_creature, base_name, count)
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

        # Extract date from filename (Chat-YY-MM-DD.log)
        try:
            date_match = re.search(r'Chat-(\d{2})-(\d{2})-(\d{2})\.log', file_name)
            if date_match:
                year = 2000 + int(date_match.group(1))
                month = int(date_match.group(2))
                day = int(date_match.group(3))
                reference_date = datetime(year, month, day)

                # Only parse Player.log for zone transitions if current session
                if self._is_current_session:
                    self.zone_transitions = self._parse_player_log(reference_date)
                    if callback and self.zone_transitions:
                        callback(f"  Found {len(self.zone_transitions)} zone transitions in Player.log")
                else:
                    self.zone_transitions = []
        except (ValueError, AttributeError):
            self.zone_transitions = []

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
            self.skinning_active = False

            new_loot = self.parse_log_file(log_file, callback)

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

        for item in sorted(items):
            lines.append(f"| {{{{Loot|{item}}}}}")

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

    def full_rescan(self, callback=None) -> dict:
        """
        Full rescan of all logs. Only adds NEW creatures/items, doesn't duplicate.
        Returns stats about what was found.
        """
        if not self.chatlog_dir.exists():
            return {}

        log_files = sorted(self.chatlog_dir.glob("Chat-*.log"))
        stats = {"new_creatures": 0, "new_items": 0, "new_skinning": 0}

        for log_file in log_files:
            if callback:
                callback(f"Rescanning {log_file.name}...")

            # Check if this is today's log (current session - zone tracking is valid)
            is_current_session = self._is_today(log_file.name)

            # Extract date from filename
            try:
                date_match = re.search(r'Chat-(\d{2})-(\d{2})-(\d{2})\.log', log_file.name)
                if date_match:
                    year = 2000 + int(date_match.group(1))
                    month = int(date_match.group(2))
                    day = int(date_match.group(3))
                    reference_date = datetime(year, month, day)
                    # Only use Player.log zone data for current session
                    if is_current_session:
                        self.zone_transitions = self._parse_player_log(reference_date)
                    else:
                        self.zone_transitions = []
            except (ValueError, AttributeError):
                self.zone_transitions = []

            # Reset state for this file
            current_creature = None
            creature_killed = False
            skinning_active = False
            current_zone = None

            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                # First, try to find timezone offset from the login line
                first_line = f.readline()
                tz_match = self.TIMEZONE_PATTERN.search(first_line)
                if tz_match:
                    sign = 1 if tz_match.group(1) == '+' else -1
                    hours = int(tz_match.group(2))
                    self._timezone_offset_hours = sign * hours
                f.seek(0)  # Reset to beginning

                for line in f:
                    match = self.LOG_LINE_PATTERN.match(line.strip())
                    if not match:
                        continue

                    timestamp_str, channel, message = match.groups()

                    # Parse timestamp for zone lookup (only valid for current session)
                    if is_current_session:
                        try:
                            timestamp = datetime.strptime(timestamp_str, "%y-%m-%d %H:%M:%S")
                            current_zone = self._get_zone_at_time(timestamp)
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

                        # Check for fatality
                        if self.FATALITY_PATTERN.search(message) and current_creature:
                            creature_killed = True

                            # Create creature entry if new
                            if current_creature not in self.creature_data:
                                self.creature_data[current_creature] = {
                                    "kills": 0, "zones": [], "items": {}, "skinning": {}
                                }
                                stats["new_creatures"] += 1
                                if callback:
                                    callback(f"  [NEW] {current_creature}")

                            # Always increment kills
                            self.creature_data[current_creature]["kills"] += 1

                            # Add zone if not present
                            if current_zone:
                                zones = self.creature_data[current_creature].get("zones", [])
                                if current_zone not in zones:
                                    zones.append(current_zone)
                                    zones.sort()
                                    self.creature_data[current_creature]["zones"] = zones

                    elif channel == "Status":
                        # Skinning/butchering XP
                        if self.SKINNING_XP_PATTERN.match(message) or self.BUTCHERING_XP_PATTERN.match(message):
                            skinning_active = True
                            continue

                        # Loot
                        loot_match = self.LOOT_PATTERN.match(message)
                        if loot_match and current_creature and current_creature in self.creature_data:
                            item_name = loot_match.group(1)
                            count = int(loot_match.group(2)) if loot_match.group(2) else 1
                            base_name = self.strip_prefixes(item_name)
                            today = datetime.now().strftime("%Y-%m-%d")

                            if skinning_active:
                                # Skinning loot
                                skinning = self.creature_data[current_creature].setdefault("skinning", {})
                                if base_name not in skinning:
                                    skinning[base_name] = {
                                        "count": count, "first_seen": today, "last_seen": today
                                    }
                                    stats["new_skinning"] += 1
                                else:
                                    skinning[base_name]["count"] += count
                                    skinning[base_name]["last_seen"] = today
                                skinning_active = False
                            elif creature_killed:
                                # Regular loot
                                items = self.creature_data[current_creature].setdefault("items", {})
                                if base_name not in items:
                                    items[base_name] = {
                                        "count": count, "first_seen": today, "last_seen": today
                                    }
                                    stats["new_items"] += 1
                                else:
                                    items[base_name]["count"] += count
                                    items[base_name]["last_seen"] = today

        self._save_creature_data()

        if callback:
            callback(f"Rescan complete: {stats['new_creatures']} new creatures, {stats['new_items']} new items, {stats['new_skinning']} new skinning")

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
                        target_match = self.COMBAT_TARGET_PATTERN.match(message)
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
        zones = data.get("zones", [])

        stats = {
            "kills": kills,
            "zones": zones,
            "items": {},
            "skinning": {}
        }

        for item_name, item_data in items.items():
            count = item_data.get("count", 0)
            drop_rate = (count / kills * 100) if kills > 0 else 0

            stats["items"][item_name] = {
                "count": count,
                "drop_rate": round(drop_rate, 2),
                "first_seen": item_data.get("first_seen"),
                "last_seen": item_data.get("last_seen")
            }

        for item_name, item_data in skinning.items():
            count = item_data.get("count", 0)
            drop_rate = (count / kills * 100) if kills > 0 else 0

            stats["skinning"][item_name] = {
                "count": count,
                "drop_rate": round(drop_rate, 2),
                "first_seen": item_data.get("first_seen"),
                "last_seen": item_data.get("last_seen")
            }

        return stats
