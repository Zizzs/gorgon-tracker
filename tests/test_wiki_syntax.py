"""
Tests for wiki syntax generation, parsing, and merging.

These tests verify:
1. Wiki syntax generation with proper zone categorization
2. Parsing wiki content to extract items by zone
3. Merging wiki data into creature data
"""

import pytest


class TestWikiSyntaxGeneration:
    """Test generate_wiki_syntax_with_zones output."""

    def test_single_zone_items_in_zone_section(self, parser):
        """Single-zone items appear in zone-specific section."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "Sun Vale Item", zone="Sun Vale")

        wiki = parser.generate_wiki_syntax_with_zones("Test Mob")

        assert "[[Sun Vale]] Loot" in wiki
        assert "{{Loot|Sun Vale Item}}" in wiki

    def test_multi_zone_items_in_general_section(self, parser):
        """Multi-zone items appear in General Loot section."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "Common Item", zone="Sun Vale")
        parser._record_kill("Test Mob", zone="Eltibule")
        parser._record_loot("Test Mob", "Common Item", zone="Eltibule")

        wiki = parser.generate_wiki_syntax_with_zones("Test Mob")

        assert "General Loot" in wiki
        assert "{{Loot|Common Item}}" in wiki

    def test_mixed_general_and_zone_sections(self, parser):
        """Output has both General and zone-specific sections."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "Zone Item", zone="Sun Vale")
        parser._record_loot("Test Mob", "Common Item", zone="Sun Vale")
        parser._record_kill("Test Mob", zone="Eltibule")
        parser._record_loot("Test Mob", "Common Item", zone="Eltibule")

        wiki = parser.generate_wiki_syntax_with_zones("Test Mob")

        assert "General Loot" in wiki
        assert "[[Sun Vale]] Loot" in wiki

    def test_skinning_section_separate(self, parser):
        """Skinning items appear in separate section."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "Regular Item", zone="Sun Vale")
        parser._record_skinning("Test Mob", "Hide")

        wiki = parser.generate_wiki_syntax_with_zones("Test Mob")

        assert "Skinning" in wiki
        assert "{{Loot|Hide}}" in wiki

    def test_butchering_section_separate(self, parser):
        """Butchering items appear in separate section."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "Regular Item", zone="Sun Vale")
        parser._record_butchering("Test Mob", "Raw Meat")

        wiki = parser.generate_wiki_syntax_with_zones("Test Mob")

        assert "Butchering" in wiki
        assert "{{Loot|Raw Meat}}" in wiki

    def test_empty_creature_message(self, parser):
        """Non-existent creature returns 'no loot' message."""
        wiki = parser.generate_wiki_syntax_with_zones("Nonexistent Creature")

        assert "No loot reported" in wiki

    def test_multiple_zones_sorted(self, parser):
        """Zone sections are sorted alphabetically."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "Sun Vale Item", zone="Sun Vale")
        parser._record_kill("Test Mob", zone="Eltibule")
        parser._record_loot("Test Mob", "Eltibule Item", zone="Eltibule")
        parser._record_kill("Test Mob", zone="Kur Mountains")
        parser._record_loot("Test Mob", "Kur Item", zone="Kur Mountains")

        wiki = parser.generate_wiki_syntax_with_zones("Test Mob")

        # Check that sections appear in alphabetical order
        eltibule_pos = wiki.find("[[Eltibule]] Loot")
        kur_pos = wiki.find("[[Kur Mountains]] Loot")
        sunvale_pos = wiki.find("[[Sun Vale]] Loot")

        assert eltibule_pos < kur_pos < sunvale_pos


class TestWikiParsing:
    """Test parsing wiki content."""

    def test_parse_general_loot_section(self, parser):
        """Parse items from General Loot section."""
        wiki_text = """== Reported Loot ==
==== General Loot ====
{|
|{{Loot|Pixie Sugar}}
|{{Loot|Fairy Wing}}
|}
"""
        result = parser.parse_wiki_loot(wiki_text)

        assert "general" in result
        assert "Pixie Sugar" in result["general"]
        assert "Fairy Wing" in result["general"]

    def test_parse_zone_specific_section(self, parser):
        """Parse items from zone-specific section."""
        wiki_text = """== Reported Loot ==
==== [[Sun Vale]] Loot ====
{|
|{{Loot|Belt of The Feral Intendant}}
|}
"""
        result = parser.parse_wiki_loot(wiki_text)

        assert "Sun Vale" in result
        assert "Belt of The Feral Intendant" in result["Sun Vale"]

    def test_parse_multiple_zones(self, parser):
        """Parse items from multiple zone sections."""
        wiki_text = """== Reported Loot ==
==== General Loot ====
{|
|{{Loot|Common Drop}}
|}

==== [[Sun Vale]] Loot ====
{|
|{{Loot|Sun Vale Item}}
|}

==== [[Eltibule]] Loot ====
{|
|{{Loot|Eltibule Item}}
|}
"""
        result = parser.parse_wiki_loot(wiki_text)

        assert "general" in result
        assert "Common Drop" in result["general"]
        assert "Sun Vale" in result
        assert "Sun Vale Item" in result["Sun Vale"]
        assert "Eltibule" in result
        assert "Eltibule Item" in result["Eltibule"]

    def test_parse_loot_with_parameters(self, parser):
        """Parse loot templates with additional parameters."""
        wiki_text = """==== General Loot ====
{|
|{{Loot|Special Item|quantity=5}}
|}
"""
        result = parser.parse_wiki_loot(wiki_text)

        assert "general" in result
        assert "Special Item" in result["general"]

    def test_parse_empty_wiki(self, parser):
        """Empty wiki returns empty dict."""
        result = parser.parse_wiki_loot("")

        assert result == {}


class TestWikiMerging:
    """Test merging wiki data into creature data."""

    def test_merge_adds_new_zone_to_existing_item(self, parser):
        """Merging wiki with different zone adds zone to item."""
        # Our data: item in Sun Vale
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "Common Item", zone="Sun Vale")

        # Verify initial state
        item = parser.creature_data["Test Mob"]["items"]["Common Item"]
        assert item["zones"] == ["Sun Vale"]

        # Wiki data: same item in Eltibule
        wiki_items = {"Eltibule": ["Common Item"]}
        parser.merge_wiki_items("Test Mob", wiki_items)

        # Item should now have both zones
        item = parser.creature_data["Test Mob"]["items"]["Common Item"]
        assert "Sun Vale" in item["zones"]
        assert "Eltibule" in item["zones"]

    def test_merge_adds_new_wiki_only_item(self, parser):
        """Items only in wiki get added with wiki_only=True."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "Our Item", zone="Sun Vale")

        wiki_items = {"Sun Vale": ["Wiki Only Item"]}
        parser.merge_wiki_items("Test Mob", wiki_items)

        # Wiki-only item should be added
        assert "Wiki Only Item" in parser.creature_data["Test Mob"]["items"]
        item = parser.creature_data["Test Mob"]["items"]["Wiki Only Item"]
        assert item.get("wiki_only") == True
        assert "Sun Vale" in item["zones"]

    def test_merge_general_loot(self, parser):
        """Merge items from general loot section."""
        parser._record_kill("Test Mob", zone="Sun Vale")

        wiki_items = {"general": ["General Item"]}
        parser.merge_wiki_items("Test Mob", wiki_items)

        assert "General Item" in parser.creature_data["Test Mob"]["items"]
        item = parser.creature_data["Test Mob"]["items"]["General Item"]
        assert item.get("wiki_only") == True

    def test_merge_returns_stats(self, parser):
        """Merge returns statistics about what was changed."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "Existing Item", zone="Sun Vale")

        wiki_items = {
            "Sun Vale": ["Existing Item"],  # Already exists
            "Eltibule": ["New Item"]  # New item
        }
        stats = parser.merge_wiki_items("Test Mob", wiki_items)

        assert "added" in stats
        assert "existing" in stats

    def test_merge_existing_item_same_zone(self, parser):
        """Merging item that exists in same zone doesn't duplicate zone."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "Item", zone="Sun Vale")

        wiki_items = {"Sun Vale": ["Item"]}
        parser.merge_wiki_items("Test Mob", wiki_items)

        item = parser.creature_data["Test Mob"]["items"]["Item"]
        assert item["zones"].count("Sun Vale") == 1


class TestInsertLootIntoWiki:
    """Test insert_loot_into_wiki functionality."""

    def test_insert_new_item_to_general(self, parser):
        """Insert new item into General Loot section."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "New Item", zone="Sun Vale")
        parser._record_loot("Test Mob", "New Item", zone="Eltibule")  # Make it multi-zone

        wiki_text = """== Reported Loot ==
==== General Loot ====
{|
|{{Loot|Existing Item}}
|}
"""
        # First merge wiki items, then insert (this is the actual app workflow)
        wiki_items = parser.parse_wiki_loot(wiki_text)
        parser.merge_wiki_items("Test Mob", wiki_items)
        result = parser.insert_loot_into_wiki("Test Mob", wiki_text)

        assert "{{Loot|New Item}}" in result
        assert "{{Loot|Existing Item}}" in result

    def test_insert_new_item_to_zone_section(self, parser):
        """Insert new single-zone item into zone-specific section."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "New Sun Vale Item", zone="Sun Vale")

        wiki_text = """== Reported Loot ==
==== [[Sun Vale]] Loot ====
{|
|{{Loot|Existing Sun Vale Item}}
|}
"""
        # First merge wiki items, then insert (this is the actual app workflow)
        wiki_items = parser.parse_wiki_loot(wiki_text)
        parser.merge_wiki_items("Test Mob", wiki_items)
        result = parser.insert_loot_into_wiki("Test Mob", wiki_text)

        assert "{{Loot|New Sun Vale Item}}" in result
        assert "{{Loot|Existing Sun Vale Item}}" in result

    def test_no_duplicate_items(self, parser):
        """Don't insert items that already exist in wiki."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "Existing Item", zone="Sun Vale")

        wiki_text = """== Reported Loot ==
==== [[Sun Vale]] Loot ====
{|
|{{Loot|Existing Item}}
|}
"""
        # First merge wiki items, then insert (this is the actual app workflow)
        wiki_items = parser.parse_wiki_loot(wiki_text)
        parser.merge_wiki_items("Test Mob", wiki_items)
        result = parser.insert_loot_into_wiki("Test Mob", wiki_text)

        # Count occurrences of the item
        count = result.count("{{Loot|Existing Item}}")
        assert count == 1

    def test_nonexistent_creature_returns_original(self, parser):
        """Non-existent creature returns original wiki text."""
        wiki_text = "== Some Wiki Content =="
        result = parser.insert_loot_into_wiki("Nonexistent Creature", wiki_text)

        assert result == wiki_text

    def test_fixes_malformed_wiki_tables(self, parser):
        """Malformed wiki tables should be regenerated with correct syntax."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "New Item", zone="Sun Vale")

        # Malformed wiki with items outside of table, missing table structure
        wiki_text = """== Reported Loot ==
{|}
{{Loot|Existing Item}}
==== General Loot ====
"""
        wiki_items = parser.parse_wiki_loot(wiki_text)
        parser.merge_wiki_items("Test Mob", wiki_items)
        result = parser.insert_loot_into_wiki("Test Mob", wiki_text)

        # Should have proper table structure with {| and |}
        assert "{|" in result
        assert "|}" in result
        # Items should be inside the table (prefixed with |)
        assert "|{{Loot|New Item}}" in result

    def test_preserves_other_sections(self, parser):
        """Non-loot sections like MOB infobox and Combat Abilities are preserved."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "Dropped Item", zone="Sun Vale")

        wiki_text = """{{MOB
|name = Test Mob
|zone = Sun Vale
}}

== Locations ==
Found in Sun Vale.

== Reported Loot ==
==== [[Sun Vale]] Loot ====
{|
|{{Loot|Wiki Item}}
|}

== Combat Abilities ==
Uses basic attacks.

== Miscellaneous ==
Additional info here.
"""
        wiki_items = parser.parse_wiki_loot(wiki_text)
        parser.merge_wiki_items("Test Mob", wiki_items)
        result = parser.insert_loot_into_wiki("Test Mob", wiki_text)

        # MOB infobox and other sections should be preserved
        assert "{{MOB" in result
        assert "== Locations ==" in result
        assert "Found in Sun Vale." in result
        assert "== Combat Abilities ==" in result
        assert "Uses basic attacks." in result
        assert "== Miscellaneous ==" in result
        assert "Additional info here." in result

    def test_replaces_loot_sections_entirely(self, parser):
        """The entire loot section is replaced, not just inserted into."""
        parser._record_kill("Test Mob", zone="Sun Vale")
        parser._record_loot("Test Mob", "Database Item", zone="Sun Vale")

        wiki_text = """== Reported Loot ==
==== [[Sun Vale]] Loot ====
{|
|{{Loot|Wiki Item}}
|}

== Skinning ==
{|
|{{Loot|Skin}}
|}

== Combat Abilities ==
Uses attacks.
"""
        wiki_items = parser.parse_wiki_loot(wiki_text)
        parser.merge_wiki_items("Test Mob", wiki_items)
        result = parser.insert_loot_into_wiki("Test Mob", wiki_text)

        # Both items should be present
        assert "{{Loot|Database Item}}" in result
        assert "{{Loot|Wiki Item}}" in result
        # Combat Abilities should be preserved
        assert "== Combat Abilities ==" in result
        assert "Uses attacks." in result
