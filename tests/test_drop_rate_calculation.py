"""
Tests for drop rate calculation fix.

The bug: Drop rates showed incorrect percentages (100%+) because the code counted
total item quantity instead of number of drop events.

Example of the bug:
    10 trolls killed, each drops "Troll Flesh x3"
    Old: count=30, drop_rate = 30/10 = 300% (WRONG)
    Fixed: drops=10, drop_rate = 10/10 = 100% (CORRECT)

The fix: Track two separate values:
    - count: total quantity of items received (for statistics)
    - drops: number of drop events (for drop rate calculation)
"""

import pytest
from pathlib import Path
from datetime import datetime


class TestDropsFieldTracking:
    """Test that the drops field is properly tracked separately from count."""

    def test_stacked_item_single_drop(self, parser, temp_log_dir):
        """Verify stacked item (x5) creates drops=1, count=5."""
        # Create log with one kill and one stacked loot drop
        log_content = """26-02-09 10:00:00\t[Combat] Player: Attack on Troll #12345! Dmg: 100 health. (FATALITY!)
26-02-09 10:00:01\t[Status] Troll Flesh x5 added to inventory.
"""
        log_file = temp_log_dir / "Chat-26-02-09.log"
        log_file.write_text(log_content, encoding='utf-8')

        parser.full_rescan()

        # Verify the data structure
        assert "Troll" in parser.creature_data
        troll_data = parser.creature_data["Troll"]
        assert troll_data["kills"] == 1
        assert "Troll Flesh" in troll_data["items"]

        item_data = troll_data["items"]["Troll Flesh"]
        assert item_data["count"] == 5, "Count should be total quantity (5)"
        assert item_data["drops"] == 1, "Drops should be number of drop events (1)"

    def test_multiple_drops_same_item(self, parser, temp_log_dir):
        """Verify multiple kills with same drop increments drops correctly."""
        # Create log with multiple kills each dropping the same item
        log_content = """26-02-09 10:00:00\t[Combat] Player: Attack on Troll #12345! Dmg: 100 health. (FATALITY!)
26-02-09 10:00:01\t[Status] Troll Flesh x3 added to inventory.
26-02-09 10:01:00\t[Combat] Player: Attack on Troll #12346! Dmg: 100 health. (FATALITY!)
26-02-09 10:01:01\t[Status] Troll Flesh x2 added to inventory.
26-02-09 10:02:00\t[Combat] Player: Attack on Troll #12347! Dmg: 100 health. (FATALITY!)
26-02-09 10:02:01\t[Status] Troll Flesh x4 added to inventory.
"""
        log_file = temp_log_dir / "Chat-26-02-09.log"
        log_file.write_text(log_content, encoding='utf-8')

        parser.full_rescan()

        # Verify the data structure
        assert "Troll" in parser.creature_data
        troll_data = parser.creature_data["Troll"]
        assert troll_data["kills"] == 3

        item_data = troll_data["items"]["Troll Flesh"]
        assert item_data["count"] == 9, "Count should be total quantity (3+2+4=9)"
        assert item_data["drops"] == 3, "Drops should be number of drop events (3)"

    def test_single_item_no_stack(self, parser, temp_log_dir):
        """Verify single item (no x notation) creates drops=1, count=1."""
        log_content = """26-02-09 10:00:00\t[Combat] Player: Attack on Goblin #12345! Dmg: 100 health. (FATALITY!)
26-02-09 10:00:01\t[Status] Goblin Ear added to inventory.
"""
        log_file = temp_log_dir / "Chat-26-02-09.log"
        log_file.write_text(log_content, encoding='utf-8')

        parser.full_rescan()

        item_data = parser.creature_data["Goblin"]["items"]["Goblin Ear"]
        assert item_data["count"] == 1
        assert item_data["drops"] == 1


class TestDropRateCalculation:
    """Test that drop rate uses drops field, not count."""

    def test_drop_rate_uses_drops_not_count(self, parser, temp_log_dir):
        """Verify drop rate is calculated from drops, not count."""
        # 2 kills, each drops "Item x5" = count=10, drops=2
        # Drop rate should be 2/2 = 100%, NOT 10/2 = 500%
        log_content = """26-02-09 10:00:00\t[Combat] Player: Attack on Orc #12345! Dmg: 100 health. (FATALITY!)
26-02-09 10:00:01\t[Status] Orc Tooth x5 added to inventory.
26-02-09 10:01:00\t[Combat] Player: Attack on Orc #12346! Dmg: 100 health. (FATALITY!)
26-02-09 10:01:01\t[Status] Orc Tooth x5 added to inventory.
"""
        log_file = temp_log_dir / "Chat-26-02-09.log"
        log_file.write_text(log_content, encoding='utf-8')

        parser.full_rescan()
        stats = parser.get_creature_stats("Orc")

        assert stats["kills"] == 2
        item_stats = stats["items"]["Orc Tooth"]
        assert item_stats["count"] == 10, "Count should be 10"
        assert item_stats["drops"] == 2, "Drops should be 2"
        assert item_stats["drop_rate"] == 100.0, "Drop rate should be 100% (2 drops / 2 kills)"

    def test_drop_rate_less_than_100(self, parser, temp_log_dir):
        """Verify drop rate < 100% when item doesn't drop every kill."""
        # 4 kills, only 2 drop the item = 50% drop rate
        log_content = """26-02-09 10:00:00\t[Combat] Player: Attack on Wolf #12345! Dmg: 100 health. (FATALITY!)
26-02-09 10:00:01\t[Status] Wolf Pelt added to inventory.
26-02-09 10:01:00\t[Combat] Player: Attack on Wolf #12346! Dmg: 100 health. (FATALITY!)
26-02-09 10:02:00\t[Combat] Player: Attack on Wolf #12347! Dmg: 100 health. (FATALITY!)
26-02-09 10:02:01\t[Status] Wolf Pelt added to inventory.
26-02-09 10:03:00\t[Combat] Player: Attack on Wolf #12348! Dmg: 100 health. (FATALITY!)
"""
        log_file = temp_log_dir / "Chat-26-02-09.log"
        log_file.write_text(log_content, encoding='utf-8')

        parser.full_rescan()
        stats = parser.get_creature_stats("Wolf")

        assert stats["kills"] == 4
        item_stats = stats["items"]["Wolf Pelt"]
        assert item_stats["drops"] == 2
        assert item_stats["drop_rate"] == 50.0, "Drop rate should be 50% (2 drops / 4 kills)"


class TestBackwardsCompatibility:
    """Test backwards compatibility with old data that lacks drops field."""

    def test_fallback_to_count_when_no_drops(self, parser):
        """Old data without drops field should fallback to count for drop rate."""
        # Simulate old data without drops field
        parser.creature_data = {
            "Old Monster": {
                "kills": 10,
                "zones": [],
                "items": {
                    "Old Item": {
                        "count": 5,
                        # No "drops" field - old data format
                        "first_seen": "2025-01-01",
                        "last_seen": "2025-01-01",
                        "zones": [],
                        "wiki_only": False
                    }
                },
                "skinning": {},
                "butchering": {}
            }
        }

        stats = parser.get_creature_stats("Old Monster")
        item_stats = stats["items"]["Old Item"]

        # Should fallback to count (5) for drops calculation
        assert item_stats["drops"] == 5, "Should fallback to count when drops missing"
        assert item_stats["drop_rate"] == 50.0, "Drop rate should be 50% (5/10)"


class TestSkinningButcheringDrops:
    """Test that skinning and butchering also track drops correctly."""

    def test_skinning_drops_tracking(self, parser, temp_log_dir):
        """Verify skinning items track drops separately from count."""
        log_content = """26-02-09 10:00:00\t[Combat] Player: Attack on Deer #12345! Dmg: 100 health. (FATALITY!)
26-02-09 10:00:01\t[Status] Animal Skin x3 added to inventory.
26-02-09 10:00:01\t[Status] You earned 50 XP in Skinning.
26-02-09 10:01:00\t[Combat] Player: Attack on Deer #12346! Dmg: 100 health. (FATALITY!)
26-02-09 10:01:01\t[Status] Animal Skin x2 added to inventory.
26-02-09 10:01:01\t[Status] You earned 50 XP in Skinning.
"""
        log_file = temp_log_dir / "Chat-26-02-09.log"
        log_file.write_text(log_content, encoding='utf-8')

        parser.full_rescan()
        stats = parser.get_creature_stats("Deer")

        skinning_stats = stats["skinning"]["Animal Skin"]
        assert skinning_stats["count"] == 5, "Count should be total (3+2=5)"
        assert skinning_stats["drops"] == 2, "Drops should be 2 skinning events"
        assert skinning_stats["drop_rate"] == 100.0, "Drop rate should be 100% (2/2 kills)"

    def test_butchering_drops_tracking(self, parser, temp_log_dir):
        """Verify butchering items track drops separately from count."""
        log_content = """26-02-09 10:00:00\t[Combat] Player: Attack on Pig #12345! Dmg: 100 health. (FATALITY!)
26-02-09 10:00:01\t[Status] Raw Meat x4 added to inventory.
26-02-09 10:00:01\t[Status] You earned 50 XP in Butchering.
"""
        log_file = temp_log_dir / "Chat-26-02-09.log"
        log_file.write_text(log_content, encoding='utf-8')

        parser.full_rescan()
        stats = parser.get_creature_stats("Pig")

        butchering_stats = stats["butchering"]["Raw Meat"]
        assert butchering_stats["count"] == 4, "Count should be 4"
        assert butchering_stats["drops"] == 1, "Drops should be 1"
        assert butchering_stats["drop_rate"] == 100.0


class TestAggregateStatsRarestDrop:
    """Test that aggregate stats rarest drop uses drops field."""

    def test_rarest_drop_uses_drops(self, parser, temp_log_dir):
        """Verify rarest drop calculation uses drops, not count."""
        # Create scenario:
        # Monster A: 10 kills, drops "Common Item x10" (drops=10, rate=100%)
        # Monster B: 10 kills, drops "Rare Item x1" once (drops=1, rate=10%)
        # Rarest should be Rare Item at 10%, not confused by stack sizes
        log_content = ""
        # Monster A - 10 kills, each drops stacked item
        for i in range(10):
            base_time = 10 + i
            log_content += f"""26-02-09 10:{base_time:02d}:00\t[Combat] Player: Attack on Common Monster #{10000+i}! Dmg: 100 health. (FATALITY!)
26-02-09 10:{base_time:02d}:01\t[Status] Common Item x10 added to inventory.
"""
        # Monster B - 10 kills, only 1 drops the rare item
        for i in range(10):
            base_time = 30 + i
            log_content += f"""26-02-09 10:{base_time:02d}:00\t[Combat] Player: Attack on Rare Monster #{20000+i}! Dmg: 100 health. (FATALITY!)
"""
            if i == 0:  # Only first kill drops the item
                log_content += f"""26-02-09 10:{base_time:02d}:01\t[Status] Rare Item added to inventory.
"""

        log_file = temp_log_dir / "Chat-26-02-09.log"
        log_file.write_text(log_content, encoding='utf-8')

        parser.full_rescan()
        agg_stats = parser.get_aggregate_stats()

        # Rarest drop should be Rare Item at 10% (1 drop / 10 kills)
        # NOT Common Item (which would appear "rarer" if we used count incorrectly)
        assert agg_stats["rarest_drop"] is not None
        rarest_item, rarest_creature, rarest_rate = agg_stats["rarest_drop"]
        assert rarest_item == "Rare Item"
        assert rarest_creature == "Rare Monster"
        assert rarest_rate == 10.0
