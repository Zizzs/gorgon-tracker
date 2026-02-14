"""
Shared pytest fixtures for loot parser tests.
"""

import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from loot_parser import LootParser
from shop_parser import ShopParser


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create a temporary directory for chat logs."""
    log_dir = tmp_path / "ChatLogs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def temp_storage_dir(tmp_path):
    """Create a temporary directory for storage."""
    storage = tmp_path / "storage"
    storage.mkdir()
    return storage


@pytest.fixture
def parser(temp_log_dir, temp_storage_dir):
    """Create a LootParser with temp directories and clean state."""
    p = LootParser(chatlog_dir=str(temp_log_dir), storage_dir=temp_storage_dir)
    # Clear any migrated data to ensure clean test state
    p.creature_data = {}
    p.processed_state = {"files": {}}
    return p


@pytest.fixture
def shop_parser(temp_storage_dir):
    """Create a ShopParser with temp storage directory."""
    return ShopParser(storage_dir=temp_storage_dir)


# Sample log data based on real game logs
SUPERSPIDER_LOG = """26-02-08 10:00:00	[Login] Logged in. Username: TestPlayer. Timezone Offset +00:00:00
26-02-08 10:00:05	[Combat] TestPlayer: Slice on Superspider #123456! Dmg: 50 health. (FATALITY!)
26-02-08 10:00:06	[Status] Spiderweb added to inventory.
26-02-08 10:00:07	[Status] Peppy Ring of Vague Poison Resistance added to inventory.
26-02-08 10:00:08	[Status] Giant Spider Leg added to inventory.
"""

MULTIPLE_KILLS_LOG = """26-02-08 10:00:00	[Login] Logged in. Username: TestPlayer. Timezone Offset +00:00:00
26-02-08 10:00:05	[Combat] TestPlayer: Slice on Wolf #111111! Dmg: 50 health. (FATALITY!)
26-02-08 10:00:06	[Status] Wolf Skin added to inventory.
26-02-08 10:00:30	[Combat] TestPlayer: Slice on Bear #222222! Dmg: 100 health. (FATALITY!)
26-02-08 10:00:31	[Status] Bear Claw added to inventory.
26-02-08 10:00:32	[Status] Bear Meat added to inventory.
"""

LOOT_OUTSIDE_WINDOW_LOG = """26-02-08 10:00:00	[Login] Logged in. Username: TestPlayer. Timezone Offset +00:00:00
26-02-08 10:00:05	[Combat] TestPlayer: Slice on Goblin #333333! Dmg: 50 health. (FATALITY!)
26-02-08 10:00:06	[Status] Goblin Spear added to inventory.
26-02-08 10:01:00	[Status] Gold Coins x5 added to inventory.
"""

SKINNING_LOG = """26-02-08 10:00:00	[Login] Logged in. Username: TestPlayer. Timezone Offset +00:00:00
26-02-08 10:00:05	[Combat] TestPlayer: Slice on Deer #444444! Dmg: 50 health. (FATALITY!)
26-02-08 10:00:06	[Status] Venison added to inventory.
26-02-08 10:00:07	[Status] Deer Skin added to inventory.
26-02-08 10:00:08	[Status] You earned 10 XP in Skinning.
"""
