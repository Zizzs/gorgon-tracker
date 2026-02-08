"""
Tests for loot classification into regular loot, skinning, and butchering.

These tests use REAL log data copied directly from game chat logs to verify
that items are correctly bucketed:
- Regular loot → items dict
- Skinning drops → skinning dict
- Butchering drops → butchering dict

NO CROSSOVER should occur between these categories.
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from loot_parser import LootParser


# =============================================================================
# Test Log Data - Copied directly from real game chat logs
# =============================================================================

# Real skinning example from Chat-26-02-07.log
# Chicken kill with Feathers skinning drop
SKINNING_LOG = """26-02-07 17:09:00	[Login] Logged in. Username: Zizzs. Timezone Offset +00:00:00
26-02-07 17:09:20	[Combat] Zizzs: Attack on Chicken #123456! Dmg: 50 health. (FATALITY!)
26-02-07 17:09:22	[Status] You earned 149 XP in Knife Fighting.
26-02-07 17:09:22	[Status] You earned 148 XP in Psychology.
26-02-07 17:09:22	[Status] You earned 3 XP in Endurance.
26-02-07 17:09:23	[Status] Feathers added to inventory.
26-02-07 17:09:23	[Status] You earned 50 XP in Skinning.
26-02-07 17:09:24	[Status] You earned 46 XP in Pathology.
"""

# Real butchering example from Chat-26-02-08.log
# Freeze Wasp kill with Stringy Insect Meat butchering drop
BUTCHERING_LOG = """26-02-08 09:27:00	[Login] Logged in. Username: Zizzs. Timezone Offset +00:00:00
26-02-08 09:27:49	[Combat] Freeze Wasp #739349: WaspIceStab on Zizzs! Dmg: 7 health, 6 armor
26-02-08 09:27:50	[NPC Chatter] Freeze Wasp: Bzzz...
26-02-08 09:27:50	[Status] You earned 201 XP in Knife Fighting.
26-02-08 09:27:50	[Status] You earned 201 XP in Psychology.
26-02-08 09:27:50	[Status] You earned 12 XP in Endurance.
26-02-08 09:27:50	[Combat] Zizzs: Duelist's Slash 3 on Freeze Wasp #739349! Dmg: 265 health. (FATALITY!)
26-02-08 09:27:51	[Status] You earned 40 XP in Arthropod Anatomy.
26-02-08 09:27:51	[Status] Stringy Insect Meat added to inventory.
26-02-08 09:27:51	[Status] You earned 40 XP in Butchering.
26-02-08 09:27:51	[Status] You earned 35 XP in Compassion.
"""

# Real regular loot example from Chat-26-02-07.log
# Soldier of the Winter Court with Fairy Wing drop (no skinning/butchering)
REGULAR_LOOT_LOG = """26-02-07 17:11:00	[Login] Logged in. Username: Zizzs. Timezone Offset +00:00:00
26-02-07 17:11:29	[Status] You earned 285 XP in Psychology.
26-02-07 17:11:29	[Status] You earned 27 XP in Endurance.
26-02-07 17:11:29	[Combat] Zizzs: Opening Thrust 4 on Soldier of the Winter Court #1584581! Dmg: 68 health, 68 armor. (FATALITY!)
26-02-07 17:11:29	[Combat] Zizzs: Recovered: 48 health, 51 armor, 72 power
26-02-07 17:11:29	[Combat] Zizzs: Recovered: 11 power
26-02-07 17:11:30	[Status] You earned 54 XP in Pathology.
26-02-07 17:11:30	[Status] You earned 45 XP in Fae Anatomy.
26-02-07 17:11:30	[Status] You earned 40 XP in Compassion.
26-02-07 17:11:30	[Status] You bury the corpse.
26-02-07 17:11:30	[Status] Fairy Wing added to inventory.
"""

# Real botched butchering scenario from Chat-26-02-08.log
# Ice Runner with Pixie Sugar (regular loot) followed by botched butchering
# The Pixie Sugar should NOT be classified as butchering
BOTCHED_BUTCHERING_LOG = """26-02-08 12:52:00	[Login] Logged in. Username: Zizzs. Timezone Offset +00:00:00
26-02-08 12:52:22	[Combat] Zizzs: Recovered: 48 health, 52 armor, 75 power
26-02-08 12:52:24	[Status] You earned 154 XP in Knife Fighting.
26-02-08 12:52:24	[Status] You earned 154 XP in Psychology.
26-02-08 12:52:24	[Combat] Zizzs: Surge Cut 4 on Ice Runner #146688! Dmg: 225 health. (FATALITY!)
26-02-08 12:52:24	[Combat] Zizzs: Recovered: 25 health
26-02-08 12:52:24	[Combat] Zizzs: Recovered: 11 power
26-02-08 12:52:24	[Combat] Zizzs: Recovered: 11 power
26-02-08 12:52:25	[Status] You earned 45 XP in Fae Anatomy.
26-02-08 12:52:25	[Status] You earned 40 XP in Compassion.
26-02-08 12:52:25	[Status] You bury the corpse.
26-02-08 12:52:25	[Status] Pixie Sugar added to inventory.
26-02-08 12:52:26	[Status] You earned 40 XP in Dinosaur Anatomy.
26-02-08 12:52:26	[Status] You botch the butchering!
26-02-08 12:52:26	[Status] You earned 5 XP in Butchering.
"""

# Multiple kills with mixed loot types
MIXED_KILLS_LOG = """26-02-08 10:00:00	[Login] Logged in. Username: Zizzs. Timezone Offset +00:00:00
26-02-08 10:00:05	[Combat] Zizzs: Attack on Chicken #111111! Dmg: 50 health. (FATALITY!)
26-02-08 10:00:06	[Status] Feathers added to inventory.
26-02-08 10:00:06	[Status] You earned 50 XP in Skinning.
26-02-08 10:00:30	[Combat] Zizzs: Attack on Freeze Wasp #222222! Dmg: 100 health. (FATALITY!)
26-02-08 10:00:31	[Status] Stringy Insect Meat added to inventory.
26-02-08 10:00:31	[Status] You earned 40 XP in Butchering.
26-02-08 10:01:00	[Combat] Zizzs: Attack on Soldier of the Winter Court #333333! Dmg: 200 health. (FATALITY!)
26-02-08 10:01:01	[Status] Fairy Wing added to inventory.
"""


# =============================================================================
# Test Classes
# =============================================================================

class TestSkinningClassification:
    """Tests that skinning loot goes to skinning dict only."""

    def test_feathers_classified_as_skinning(self, parser, temp_log_dir):
        """
        Real scenario: Chicken kill with Feathers drop followed by Skinning XP.
        Feathers should be in skinning dict, not items.
        """
        log_file = temp_log_dir / "Chat-26-02-07.log"
        log_file.write_text(SKINNING_LOG)

        parser.full_rescan()

        assert "Chicken" in parser.creature_data
        creature = parser.creature_data["Chicken"]

        # Feathers should be in skinning (followed by Skinning XP within 1 second)
        assert "Feathers" in creature.get("skinning", {}), \
            "Feathers should be classified as skinning"

        # Feathers should NOT be in regular items
        assert "Feathers" not in creature.get("items", {}), \
            "Feathers should NOT be in regular items"

        # Should not appear in butchering
        assert "Feathers" not in creature.get("butchering", {}), \
            "Feathers should NOT be in butchering"


class TestButcheringClassification:
    """Tests that butchering loot goes to butchering dict only."""

    def test_insect_meat_classified_as_butchering(self, parser, temp_log_dir):
        """
        Real scenario: Freeze Wasp kill with Stringy Insect Meat followed by Butchering XP.
        Meat should be in butchering dict, not items.
        """
        log_file = temp_log_dir / "Chat-26-02-08.log"
        log_file.write_text(BUTCHERING_LOG)

        parser.full_rescan()

        assert "Freeze Wasp" in parser.creature_data
        creature = parser.creature_data["Freeze Wasp"]

        # Stringy Insect Meat should be in butchering
        assert "Stringy Insect Meat" in creature.get("butchering", {}), \
            "Stringy Insect Meat should be classified as butchering"

        # Should NOT be in regular items
        assert "Stringy Insect Meat" not in creature.get("items", {}), \
            "Stringy Insect Meat should NOT be in regular items"

        # Should NOT be in skinning
        assert "Stringy Insect Meat" not in creature.get("skinning", {}), \
            "Stringy Insect Meat should NOT be in skinning"


class TestRegularLootClassification:
    """Tests that regular loot (no skinning/butchering) goes to items dict only."""

    def test_fairy_wing_classified_as_regular_loot(self, parser, temp_log_dir):
        """
        Real scenario: Soldier of the Winter Court with Fairy Wing drop.
        No skinning/butchering XP follows, so it's regular loot.
        """
        log_file = temp_log_dir / "Chat-26-02-07.log"
        log_file.write_text(REGULAR_LOOT_LOG)

        parser.full_rescan()

        assert "Soldier of the Winter Court" in parser.creature_data
        creature = parser.creature_data["Soldier of the Winter Court"]

        # Fairy Wing should be in regular items
        assert "Fairy Wing" in creature.get("items", {}), \
            "Fairy Wing should be in regular items"

        # Should NOT be in skinning or butchering
        assert "Fairy Wing" not in creature.get("skinning", {}), \
            "Fairy Wing should NOT be in skinning"
        assert "Fairy Wing" not in creature.get("butchering", {}), \
            "Fairy Wing should NOT be in butchering"


class TestBotchedButcheringScenario:
    """
    Critical test: Regular loot should NOT be misclassified as butchering
    just because butchering XP happens to come within 2 seconds.

    This tests the Pixie Sugar bug where grave loot was incorrectly
    classified as butchering because butchering happened right after.
    """

    def test_pixie_sugar_not_classified_as_butchering(self, parser, temp_log_dir):
        """
        Real scenario: Ice Runner kill where:
        1. Pixie Sugar is looted (regular grave loot)
        2. Butchering is attempted but botched (no item, just XP)

        Pixie Sugar should be in items, NOT butchering.
        The butchering was botched so produced no item.
        """
        log_file = temp_log_dir / "Chat-26-02-08.log"
        log_file.write_text(BOTCHED_BUTCHERING_LOG)

        parser.full_rescan()

        assert "Ice Runner" in parser.creature_data
        creature = parser.creature_data["Ice Runner"]

        # Pixie Sugar should be regular loot
        assert "Pixie Sugar" in creature.get("items", {}), \
            "Pixie Sugar should be regular loot (from grave), not butchering"

        # Pixie Sugar should NOT be in butchering
        assert "Pixie Sugar" not in creature.get("butchering", {}), \
            "Pixie Sugar should NOT be classified as butchering - the butchering was botched!"


class TestMixedKillsClassification:
    """Tests correct classification across multiple kills with different loot types."""

    def test_multiple_creatures_correct_buckets(self, parser, temp_log_dir):
        """
        Three kills in sequence:
        1. Chicken - skinning (Feathers)
        2. Freeze Wasp - butchering (Stringy Insect Meat)
        3. Soldier - regular loot (Fairy Wing)

        Each item should be in the correct bucket with no crossover.
        """
        log_file = temp_log_dir / "Chat-26-02-08.log"
        log_file.write_text(MIXED_KILLS_LOG)

        parser.full_rescan()

        # Chicken - Feathers should be skinning
        chicken = parser.creature_data["Chicken"]
        assert "Feathers" in chicken.get("skinning", {}), \
            "Chicken: Feathers should be in skinning"
        assert "Feathers" not in chicken.get("items", {}), \
            "Chicken: Feathers should NOT be in items"
        assert "Feathers" not in chicken.get("butchering", {}), \
            "Chicken: Feathers should NOT be in butchering"

        # Freeze Wasp - Stringy Insect Meat should be butchering
        wasp = parser.creature_data["Freeze Wasp"]
        assert "Stringy Insect Meat" in wasp.get("butchering", {}), \
            "Freeze Wasp: Stringy Insect Meat should be in butchering"
        assert "Stringy Insect Meat" not in wasp.get("items", {}), \
            "Freeze Wasp: Stringy Insect Meat should NOT be in items"
        assert "Stringy Insect Meat" not in wasp.get("skinning", {}), \
            "Freeze Wasp: Stringy Insect Meat should NOT be in skinning"

        # Soldier - Fairy Wing should be regular items
        soldier = parser.creature_data["Soldier of the Winter Court"]
        assert "Fairy Wing" in soldier.get("items", {}), \
            "Soldier: Fairy Wing should be in items"
        assert "Fairy Wing" not in soldier.get("skinning", {}), \
            "Soldier: Fairy Wing should NOT be in skinning"
        assert "Fairy Wing" not in soldier.get("butchering", {}), \
            "Soldier: Fairy Wing should NOT be in butchering"


class TestNoCrossover:
    """Verify no item ever appears in multiple categories."""

    def test_no_item_in_multiple_categories(self, parser, temp_log_dir):
        """No item should appear in more than one category for any creature."""
        log_file = temp_log_dir / "Chat-26-02-08.log"
        log_file.write_text(MIXED_KILLS_LOG)

        parser.full_rescan()

        for creature_name, creature_data in parser.creature_data.items():
            items = set(creature_data.get("items", {}).keys())
            skinning = set(creature_data.get("skinning", {}).keys())
            butchering = set(creature_data.get("butchering", {}).keys())

            # Check no overlap between any two categories
            items_skinning = items & skinning
            items_butchering = items & butchering
            skinning_butchering = skinning & butchering

            assert len(items_skinning) == 0, \
                f"{creature_name}: Items overlap with skinning: {items_skinning}"
            assert len(items_butchering) == 0, \
                f"{creature_name}: Items overlap with butchering: {items_butchering}"
            assert len(skinning_butchering) == 0, \
                f"{creature_name}: Skinning overlap with butchering: {skinning_butchering}"
