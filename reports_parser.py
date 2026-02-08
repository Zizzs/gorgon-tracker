"""
Reports Parser for Gorgon Tracker.
Parses character and storage JSON exports from Project Gorgon.
"""

import json
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Optional

from paths import get_gorgon_tracker_data_dir, get_pg_base_dir


# Quest database URL
QUESTS_JSON_URL = "https://cdn.projectgorgon.com/v456/data/quests.json"

# NPC display names (NPC_InternalName -> Display Name)
NPC_DISPLAY_NAMES = {
    "NPC_Agrashab": "Agrashab",
    "NPC_AriannaFangblade": "Arianna Fangblade",
    "NPC_Azalak": "Azalak",
    "NPC_Bahdba": "Bahdba",
    "NPC_Blanche": "Blanche",
    "NPC_Boatman": "Boatman",
    "NPC_Braigon": "Braigon",
    "NPC_BriannaWiller": "Brianna Willer",
    "NPC_CharlesThompson": "Charles Thompson",
    "NPC_CleoConyer": "Cleo Conyer",
    "NPC_DorimirFangblade": "Dorimir Fangblade",
    "NPC_DurstinTallow": "Durstin Tallow",
    "NPC_Echur": "Echur",
    "NPC_Elahil": "Elahil",
    "NPC_Elmetaph": "Elmetaph",
    "NPC_EnslavedFairy": "Enslaved Fairy",
    "NPC_EvelineRastin": "Eveline Rastin",
    "NPC_Fainor": "Fainor",
    "NPC_Fitz": "Fitz",
    "NPC_Flia": "Flia",
    "NPC_GeorgeMadler": "George Madler",
    "NPC_Gershok": "Gershok",
    "NPC_Gisli": "Gisli",
    "NPC_GloriaStonecurl": "Gloria Stonecurl",
    "NPC_Gretchen": "Gretchen",
    "NPC_Gurki": "Gurki",
    "NPC_Harry": "Harry",
    "NPC_Helena": "Helena",
    "NPC_Hogan": "Hogan",
    "NPC_Hulon": "Hulon",
    "NPC_Irkima": "Irkima",
    "NPC_Ivyn": "Ivyn",
    "NPC_JaimeFatholm": "Jaime Fatholm",
    "NPC_JanetLews": "Janet Lews",
    "NPC_Jara": "Jara",
    "NPC_Jesina": "Jesina",
    "NPC_Joe": "Joeh",
    "NPC_JuliusPatton": "Julius Patton",
    "NPC_Jumjab": "Jumjab",
    "NPC_Kalaba": "Kalaba",
    "NPC_Kib": "Kib",
    "NPC_Kleave": "Kleave",
    "NPC_LanaSongtree": "Lana Songtree",
    "NPC_Landri": "Landri the Cold",
    "NPC_Larsan": "Larsan",
    "NPC_LauraNeth": "Laura Neth",
    "NPC_Lawara": "Lawara",
    "NPC_LeonardAllenson": "Leonard Allenson",
    "NPC_Lugnir": "Lugnir",
    "NPC_Mandibles": "Mandibles",
    "NPC_MarithFelgard": "Marith Felgard",
    "NPC_Marna": "Marna",
    "NPC_Merriana": "Merriana",
    "NPC_Mirraverre": "Mirraverre",
    "NPC_MushroomJack": "Mushroom Jack",
    "NPC_Mythander": "Mythander",
    "NPC_NelsonBallard": "Nelson Ballard",
    "NPC_Nightshade": "Nightshade",
    "NPC_Oritania": "Oritania",
    "NPC_Otis": "Otis",
    "NPC_PaulVaughn": "Paul Vaughn",
    "NPC_Pennoc": "Pennoc",
    "NPC_Ragabir": "Ragabir",
    "NPC_Rappanel": "Rappanel",
    "NPC_Riger": "Riger",
    "NPC_Riston": "Riston",
    "NPC_Rita": "Rita",
    "NPC_RoshunTheTraitor": "Roshun the Traitor",
    "NPC_Selphie": "Selphie",
    "NPC_SieAntry": "Sie Antry",
    "NPC_SirArif": "Sir Arif",
    "NPC_SirCoth": "Sir Coth",
    "NPC_Squidlips": "Squidlips",
    "NPC_Tadion": "Tadion",
    "NPC_Tavilak": "Tavilak",
    "NPC_Therese": "Therese",
    "NPC_ThimblePete": "Thimble Pete",
    "NPC_Trasen": "Trasen",
    "NPC_TylerGreen": "Tyler Green",
    "NPC_Ukorga": "Ukorga",
    "NPC_Velkort": "Velkort",
    "NPC_Viedesi": "Viedesi",
    "NPC_WillemFangblade": "Willem Fangblade",
    "NPC_Yasinda": "Yasinda",
    "NPC_Yetta": "Yetta",
    "NPC_Yurra": "Yurra",
    "NPC_Zeratak": "Zeratak",
}

# Favor level ordering (higher = better)
FAVOR_LEVELS = [
    "Neutral",
    "Tolerated",
    "Comfortable",
    "Friends",
    "CloseFriends",
    "BestFriends",
    "LikeFamily",
    "SoulMates",
]

# Display names for favor levels
FAVOR_DISPLAY = {
    "Neutral": "Neutral",
    "Tolerated": "Tolerated",
    "Comfortable": "Comfortable",
    "Friends": "Friends",
    "CloseFriends": "Close Friends",
    "BestFriends": "Best Friends",
    "LikeFamily": "Like Family",
    "SoulMates": "Soul Mates",
}

# Currency display names
CURRENCY_DISPLAY = {
    "GOLD": "Gold",
    "GUILDCREDITS": "Guild Credits",
    "REDWINGTOKENS": "Red Wing Tokens",
    "DRUIDCREDITS": "Druid Credits",
    "WARDENPOINTS": "Warden Points",
    "FAEENERGY": "Fae Energy",
    "LIVEEVENTCREDITS": "Live Event Credits",
    "GLAMOUR_CREDITS": "Glamour Credits",
    "COMBAT_WISDOM": "Combat Wisdom",
    "BLOOD_OATHS": "Blood Oaths",
    "VIDARIA_RENOWN": "Vidaria Renown",
    "STATEHELM_RENOWN": "Statehelm Renown",
    "STATEHELM_DEMERITS": "Statehelm Demerits",
    "NORALA_TOKENS": "Norala Tokens",
}

# Storage vault display names
VAULT_DISPLAY = {
    "Saddlebag": "Saddlebag",
    "DreamRealmChest": "Dream Realm Chest",
    "Inventory": "Inventory",
}


class ReportsParser:
    """Parses character and storage exports from Project Gorgon."""

    def __init__(self, reports_dir: Optional[Path] = None):
        """
        Initialize the reports parser.

        Args:
            reports_dir: Path to Reports directory. Auto-detected if None.
        """
        if reports_dir is None:
            pg_base = get_pg_base_dir()
            if pg_base:
                reports_dir = pg_base / "Reports"

        self.reports_dir = reports_dir
        self.data_dir = get_gorgon_tracker_data_dir()

        # Cached data
        self._character_data: Optional[dict] = None
        self._character_file: Optional[Path] = None
        self._storage_data: Optional[dict] = None
        self._storage_file: Optional[Path] = None
        self._quest_database: Optional[dict] = None
        self._quest_index: Optional[dict] = None

    def get_reports_dir(self) -> Optional[Path]:
        """Get the Reports directory path."""
        return self.reports_dir

    def has_reports(self) -> bool:
        """Check if Reports directory exists and has files."""
        if not self.reports_dir or not self.reports_dir.exists():
            return False
        return any(self.reports_dir.glob("*.json"))

    # --- File Detection ---

    def get_latest_character_file(self) -> Optional[Path]:
        """Get the most recent Character_*.json file."""
        if not self.reports_dir or not self.reports_dir.exists():
            return None

        files = list(self.reports_dir.glob("Character_*.json"))
        if not files:
            return None

        # Sort by modification time (newest first)
        return max(files, key=lambda f: f.stat().st_mtime)

    def get_latest_storage_file(self) -> Optional[Path]:
        """Get the most recent *_items_*.json file."""
        if not self.reports_dir or not self.reports_dir.exists():
            return None

        files = list(self.reports_dir.glob("*_items_*.json"))
        if not files:
            return None

        # Sort by modification time (newest first)
        return max(files, key=lambda f: f.stat().st_mtime)

    def check_for_updates(self) -> tuple[bool, bool]:
        """
        Check if character or storage files have been updated.

        Returns:
            Tuple of (character_updated, storage_updated)
        """
        char_updated = False
        storage_updated = False

        latest_char = self.get_latest_character_file()
        if latest_char and latest_char != self._character_file:
            char_updated = True

        latest_storage = self.get_latest_storage_file()
        if latest_storage and latest_storage != self._storage_file:
            storage_updated = True

        return char_updated, storage_updated

    # --- Character Data ---

    def load_character(self, force_reload: bool = False) -> Optional[dict]:
        """
        Load character data from the latest Character export.

        Args:
            force_reload: Force reload even if already cached

        Returns:
            Character data dict or None if not available
        """
        char_file = self.get_latest_character_file()
        if not char_file:
            return None

        # Use cache if file hasn't changed
        if not force_reload and self._character_file == char_file and self._character_data:
            return self._character_data

        try:
            with open(char_file, 'r', encoding='utf-8') as f:
                self._character_data = json.load(f)
                self._character_file = char_file
                return self._character_data
        except (json.JSONDecodeError, IOError):
            return None

    def get_character_name(self) -> Optional[str]:
        """Get the character name."""
        data = self.load_character()
        if data:
            return data.get("Character")
        return None

    def get_race(self) -> Optional[str]:
        """Get the character race."""
        data = self.load_character()
        if data:
            return data.get("Race")
        return None

    def get_skills(self) -> list[dict]:
        """
        Get character skills sorted by level.

        Returns:
            List of skill dicts with name, level, bonus, xp, xp_needed
        """
        data = self.load_character()
        if not data:
            return []

        skills_data = data.get("Skills", {})
        skills = []

        for name, info in skills_data.items():
            # Skip the "Unknown" skill placeholder
            if name == "Unknown":
                continue

            level = info.get("Level", 0)
            # Skip level 0 skills
            if level == 0:
                continue

            skills.append({
                "name": self._format_skill_name(name),
                "internal_name": name,
                "level": level,
                "bonus": info.get("BonusLevels", 0),
                "xp": info.get("XpTowardNextLevel", 0),
                "xp_needed": info.get("XpNeededForNextLevel", 0),
                "abilities": info.get("Abilities", []),
            })

        # Sort by level descending
        return sorted(skills, key=lambda s: s["level"], reverse=True)

    def _format_skill_name(self, name: str) -> str:
        """Convert internal skill name to display name."""
        # Handle Anatomy_ prefixes
        if name.startswith("Anatomy_"):
            sub = name[8:]
            return f"Anatomy ({sub})"

        # Handle Performance_ prefixes
        if name.startswith("Performance_"):
            sub = name[12:]
            return f"Performance ({sub})"

        # Add spaces before capitals (CamelCase -> Title Case)
        result = ""
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result += " "
            result += char

        return result

    def get_currencies(self) -> dict[str, int]:
        """
        Get character currencies.

        Returns:
            Dict of currency name -> amount (only non-zero currencies)
        """
        data = self.load_character()
        if not data:
            return {}

        currencies = {}
        for key, value in data.get("Currencies", {}).items():
            if value > 0:
                display_name = CURRENCY_DISPLAY.get(key, key)
                currencies[display_name] = value

        return currencies

    def get_gold(self) -> int:
        """Get current gold amount."""
        data = self.load_character()
        if data:
            return data.get("Currencies", {}).get("GOLD", 0)
        return 0

    def get_npc_relationships(self) -> list[dict]:
        """
        Get NPC relationships sorted by favor level.

        Returns:
            List of dicts with npc, display_name, favor_level, favor_display
        """
        data = self.load_character()
        if not data:
            return []

        npcs = []
        for npc_id, info in data.get("NPCs", {}).items():
            favor = info.get("FavorLevel", "Neutral")

            # Skip Neutral NPCs and non-NPC entries
            if favor == "Neutral":
                continue

            # Skip non-person NPCs
            if not npc_id.startswith("NPC_"):
                continue

            display_name = NPC_DISPLAY_NAMES.get(npc_id, npc_id.replace("NPC_", ""))

            npcs.append({
                "npc": npc_id,
                "display_name": display_name,
                "favor_level": favor,
                "favor_display": FAVOR_DISPLAY.get(favor, favor),
            })

        # Sort by favor level (highest first)
        def favor_sort_key(npc):
            try:
                return -FAVOR_LEVELS.index(npc["favor_level"])
            except ValueError:
                return 0

        return sorted(npcs, key=favor_sort_key)

    def get_active_quest_ids(self) -> list[str]:
        """Get list of active quest internal IDs."""
        data = self.load_character()
        if data:
            return data.get("ActiveQuests", [])
        return []

    def get_current_stats(self) -> dict:
        """Get character current stats."""
        data = self.load_character()
        if data:
            return data.get("CurrentStats", {})
        return {}

    # --- Storage Data ---

    def load_storage(self, force_reload: bool = False) -> Optional[dict]:
        """
        Load storage data from the latest items export.

        Args:
            force_reload: Force reload even if already cached

        Returns:
            Storage data dict or None if not available
        """
        storage_file = self.get_latest_storage_file()
        if not storage_file:
            return None

        # Use cache if file hasn't changed
        if not force_reload and self._storage_file == storage_file and self._storage_data:
            return self._storage_data

        try:
            with open(storage_file, 'r', encoding='utf-8') as f:
                self._storage_data = json.load(f)
                self._storage_file = storage_file
                return self._storage_data
        except (json.JSONDecodeError, IOError):
            return None

    def get_all_items(self) -> list[dict]:
        """Get all items from storage."""
        data = self.load_storage()
        if data:
            return data.get("Items", [])
        return []

    def get_vault_names(self) -> list[str]:
        """Get list of unique vault names."""
        items = self.get_all_items()
        vaults = set()
        for item in items:
            vault = item.get("StorageVault", "Unknown")
            vaults.add(vault)
        return sorted(vaults)

    def get_items_by_vault(self) -> dict[str, list[dict]]:
        """
        Get items grouped by vault.

        Returns:
            Dict of vault name -> list of items
        """
        items = self.get_all_items()
        by_vault = {}

        for item in items:
            vault = item.get("StorageVault", "Unknown")
            if vault not in by_vault:
                by_vault[vault] = []
            by_vault[vault].append(item)

        # Sort items in each vault by value (highest first)
        for vault in by_vault:
            by_vault[vault].sort(key=lambda i: i.get("Value", 0), reverse=True)

        return by_vault

    def get_all_item_names(self) -> set[str]:
        """Get set of all item names in storage."""
        items = self.get_all_items()
        return {item.get("Name", "") for item in items if item.get("Name")}

    def get_item_count(self, item_name: str) -> int:
        """Get total count of an item across all storage."""
        items = self.get_all_items()
        total = 0
        for item in items:
            if item.get("Name") == item_name:
                total += item.get("StackSize", 1)
        return total

    def search_items(self, query: str) -> list[dict]:
        """
        Search items by name.

        Args:
            query: Search string (case-insensitive)

        Returns:
            List of matching items with vault info
        """
        query = query.lower().strip()
        if not query:
            return []

        items = self.get_all_items()
        results = []

        for item in items:
            name = item.get("Name", "")
            if query in name.lower():
                results.append(item)

        # Sort by relevance (exact match first, then by value)
        def relevance(item):
            name = item.get("Name", "").lower()
            if name == query:
                return (0, -item.get("Value", 0))
            elif name.startswith(query):
                return (1, -item.get("Value", 0))
            else:
                return (2, -item.get("Value", 0))

        return sorted(results, key=relevance)

    def get_vault_summary(self) -> dict[str, dict]:
        """
        Get summary for each vault.

        Returns:
            Dict of vault -> {item_count, total_value}
        """
        by_vault = self.get_items_by_vault()
        summary = {}

        for vault, items in by_vault.items():
            total_value = sum(
                item.get("Value", 0) * item.get("StackSize", 1)
                for item in items
            )
            summary[vault] = {
                "item_count": len(items),
                "total_value": total_value,
            }

        return summary

    # --- Quest Database ---

    def load_quest_database(self, force_download: bool = False) -> Optional[dict]:
        """
        Load quest database from CDN (with caching).

        Args:
            force_download: Force re-download even if cached

        Returns:
            Quest database dict or None if failed
        """
        if self._quest_database and not force_download:
            return self._quest_database

        cache_file = self.data_dir / "quests_cache.json"

        # Check cache (valid for 7 days)
        if not force_download and cache_file.exists():
            cache_age = datetime.now().timestamp() - cache_file.stat().st_mtime
            if cache_age < 7 * 24 * 3600:
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        self._quest_database = json.load(f)
                        return self._quest_database
                except (json.JSONDecodeError, IOError):
                    pass

        # Download from CDN
        try:
            req = urllib.request.Request(
                QUESTS_JSON_URL,
                headers={'User-Agent': 'GorgonTracker/1.0'}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))

                # Cache the data
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f)

                self._quest_database = data
                return data
        except Exception as e:
            print(f"Warning: Could not load quest database: {e}")

            # Try to use stale cache
            if cache_file.exists():
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        self._quest_database = json.load(f)
                        return self._quest_database
                except (json.JSONDecodeError, IOError):
                    pass

            return None

    def _build_quest_index(self) -> dict[str, dict]:
        """Build an index of InternalName -> quest data for fast lookups."""
        if hasattr(self, '_quest_index') and self._quest_index:
            return self._quest_index

        db = self.load_quest_database()
        if not db:
            return {}

        self._quest_index = {}
        for key, quest in db.items():
            internal_name = quest.get("InternalName")
            if internal_name:
                self._quest_index[internal_name] = quest

        return self._quest_index

    def get_quest_details(self, quest_id: str) -> Optional[dict]:
        """
        Get details for a specific quest.

        Args:
            quest_id: Internal quest ID (e.g., "DeerInTheCrypt")

        Returns:
            Quest data dict or None if not found
        """
        # Build or use cached index for InternalName lookups
        index = self._build_quest_index()

        # Direct lookup by InternalName
        if quest_id in index:
            return index[quest_id]

        # Try case-insensitive search as fallback
        quest_id_lower = quest_id.lower()
        for name, quest in index.items():
            if name.lower() == quest_id_lower:
                return quest

        return None

    def get_active_quests_with_details(self) -> list[dict]:
        """
        Get active quests with full details from database.

        Returns:
            List of quest dicts with merged character and database info
        """
        active_ids = self.get_active_quest_ids()
        if not active_ids:
            return []

        all_item_names = self.get_all_item_names()
        quests = []

        for quest_id in active_ids:
            details = self.get_quest_details(quest_id)

            # Get zone from multiple possible fields
            zone = None
            if details:
                zone = details.get("DisplayedLocation") or details.get("Zone")

            quest = {
                "id": quest_id,
                "name": details.get("Name", quest_id) if details else quest_id,
                "zone": zone,
                "objectives": [],
                "has_details": details is not None,
            }

            # Parse objectives if available
            if details and "Objectives" in details:
                for obj in details.get("Objectives", []):
                    obj_info = {
                        "description": obj.get("Description", ""),
                        "type": obj.get("Type", ""),
                        "target": obj.get("Target"),
                        "count": obj.get("Number", 1),
                        "is_item": False,
                        "has_item": False,
                    }

                    # Check if this is an item-related objective
                    if obj.get("Type") in ["CollectItem", "DeliverItem", "HaveItem"]:
                        obj_info["is_item"] = True
                        item_name = obj.get("ItemName") or obj.get("Target")
                        if item_name:
                            obj_info["item_name"] = item_name
                            obj_info["has_item"] = item_name in all_item_names

                    quest["objectives"].append(obj_info)

            quests.append(quest)

        # Sort by zone, then by name
        return sorted(quests, key=lambda q: (q.get("zone") or "ZZZ", q.get("name", "")))

    def get_quests_by_zone(self) -> dict[str, list[dict]]:
        """
        Get active quests grouped by zone.

        Returns:
            Dict of zone -> list of quests
        """
        quests = self.get_active_quests_with_details()
        by_zone = {}

        for quest in quests:
            zone = quest.get("zone") or "Unknown"
            if zone not in by_zone:
                by_zone[zone] = []
            by_zone[zone].append(quest)

        return by_zone
