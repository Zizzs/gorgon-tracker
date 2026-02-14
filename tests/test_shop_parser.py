"""
Tests for shop_parser.py.

Tests verify that regex patterns correctly match shop log entries
and that entry processing updates data structures correctly.
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from shop_parser import ShopParser


# Sample test data based on real game format
SALE_SINGLE = "Thu Feb 12 13:35 - PlayerName bought Item at a cost of 100 per 1 = 100"
SALE_STACKED = "Thu Feb 12 13:35 - PlayerName bought Grapefish x5 at a cost of 75 per 1 = 375"
COLLECTION_ENTRY = "Sat Feb 14 12:09 - PlayerName collected 4350 Councils from customer purchases"
CONFIGURE_ENTRY = "Fri Feb 13 21:28 - PlayerName configured Amethystx17 to cost 350 per 1"
VISIBILITY_ENTRY = "Fri Feb 13 01:18 - PlayerName made Rubywall Crystalx40 visible in shop at a cost of 250 per 1"
VENDOR_HIRE_ENTRY = "Sat Feb 14 12:09 - PlayerName paid 1700 Councils to hire Erica Hills for another 24 hours"
ADD_SINGLE = "Thu Feb 12 10:00 - PlayerName added Item to shop"
ADD_STACKED = "Thu Feb 12 10:00 - PlayerName added Grapefish x25 to shop"
REMOVE_SINGLE = "Thu Feb 12 10:05 - PlayerName removed Item from shop"
REMOVE_STACKED = "Thu Feb 12 10:05 - PlayerName removed Grapefish x10 from shop"
SHOP_NAME_ENTRY = 'Thu Feb 12 08:05 - PlayerName set shop name to "My Shop"'
SHOP_SIGN_ENTRY = 'Thu Feb 12 08:10 - PlayerName set shop sign to "Welcome!"'
SHOP_TAG_ENTRY = 'Thu Feb 12 08:15 - PlayerName set shop tag to "Fish"'


class TestSalePattern:
    """Tests for the sale pattern."""

    def test_sale_single_item(self, shop_parser):
        """Single item sale should match with quantity=1."""
        match = shop_parser.SALE_PATTERN.match(SALE_SINGLE)
        assert match is not None
        assert match.group(1) == "Thu Feb 12 13:35"  # timestamp
        assert match.group(2) == "PlayerName"  # buyer
        assert match.group(3) == "Item"  # item name
        assert match.group(4) is None  # quantity (None for single)
        assert match.group(5) == "100"  # price per
        assert match.group(6) == "100"  # total

    def test_sale_stacked_item(self, shop_parser):
        """Stacked item sale should match with correct quantity."""
        match = shop_parser.SALE_PATTERN.match(SALE_STACKED)
        assert match is not None
        assert match.group(1) == "Thu Feb 12 13:35"
        assert match.group(2) == "PlayerName"
        assert match.group(3) == "Grapefish"
        assert match.group(4) == "5"  # quantity
        assert match.group(5) == "75"  # price per
        assert match.group(6) == "375"  # total

    def test_sale_no_match(self, shop_parser):
        """Non-sale lines should not match."""
        non_sale_lines = [
            "Random text",
            COLLECTION_ENTRY,
            CONFIGURE_ENTRY,
            "PlayerName sold Item for 100",  # Wrong format
        ]
        for line in non_sale_lines:
            match = shop_parser.SALE_PATTERN.match(line)
            assert match is None, f"Should not match: {line}"


class TestCollectionPattern:
    """Tests for the collection pattern."""

    def test_collection_pattern(self, shop_parser):
        """Collection entry should match and extract amount."""
        match = shop_parser.COLLECTION_PATTERN.match(COLLECTION_ENTRY)
        assert match is not None
        assert match.group(1) == "Sat Feb 14 12:09"
        assert match.group(2) == "PlayerName"
        assert match.group(3) == "4350"

    def test_collection_no_match(self, shop_parser):
        """Non-collection lines should not match."""
        non_collection_lines = [
            SALE_SINGLE,
            CONFIGURE_ENTRY,
            "PlayerName collected some items",
        ]
        for line in non_collection_lines:
            match = shop_parser.COLLECTION_PATTERN.match(line)
            assert match is None, f"Should not match: {line}"


class TestSetPricePattern:
    """Tests for the set price (configured) pattern."""

    def test_set_price_pattern(self, shop_parser):
        """Configure entry should match."""
        match = shop_parser.SET_PRICE_PATTERN.match(CONFIGURE_ENTRY)
        assert match is not None
        assert match.group(1) == "Fri Feb 13 21:28"
        assert match.group(2) == "PlayerName"
        assert match.group(3) == "Amethyst"  # item name
        assert match.group(4) == "17"  # quantity
        assert match.group(5) == "350"  # price

    def test_set_price_extracts_quantity(self, shop_parser):
        """Verify quantity extraction from configure pattern."""
        test_cases = [
            ("Fri Feb 13 21:28 - Player configured Goldx100 to cost 50 per 1", "Gold", "100", "50"),
            ("Fri Feb 13 21:28 - Player configured Diamondx1 to cost 10000 per 1", "Diamond", "1", "10000"),
        ]
        for line, expected_item, expected_qty, expected_price in test_cases:
            match = shop_parser.SET_PRICE_PATTERN.match(line)
            assert match is not None, f"Should match: {line}"
            assert match.group(3) == expected_item
            assert match.group(4) == expected_qty
            assert match.group(5) == expected_price

    def test_set_price_no_match(self, shop_parser):
        """Non-matching lines should not match."""
        non_matching = [
            SALE_SINGLE,
            COLLECTION_ENTRY,
            "PlayerName configured Item to cost 100",  # Missing quantity
        ]
        for line in non_matching:
            match = shop_parser.SET_PRICE_PATTERN.match(line)
            assert match is None, f"Should not match: {line}"


class TestVisibilityPattern:
    """Tests for the visibility pattern."""

    def test_visibility_pattern(self, shop_parser):
        """Visibility entry should match."""
        match = shop_parser.VISIBILITY_PATTERN.match(VISIBILITY_ENTRY)
        assert match is not None
        assert match.group(1) == "Fri Feb 13 01:18"
        assert match.group(2) == "PlayerName"
        assert match.group(3) == "Rubywall Crystal"
        assert match.group(4) == "40"
        assert match.group(5) == "250"

    def test_visibility_extracts_data(self, shop_parser):
        """Verify quantity and price extraction from visibility pattern."""
        entry = "Fri Feb 13 01:18 - Player made Gemx99 visible in shop at a cost of 500 per 1"
        match = shop_parser.VISIBILITY_PATTERN.match(entry)
        assert match is not None
        assert match.group(3) == "Gem"
        assert match.group(4) == "99"
        assert match.group(5) == "500"

    def test_visibility_no_match(self, shop_parser):
        """Non-matching lines should not match."""
        non_matching = [
            SALE_SINGLE,
            CONFIGURE_ENTRY,
            "PlayerName made Item visible",  # Incomplete format
        ]
        for line in non_matching:
            match = shop_parser.VISIBILITY_PATTERN.match(line)
            assert match is None, f"Should not match: {line}"


class TestVendorHirePattern:
    """Tests for the vendor hire pattern."""

    def test_vendor_hire_pattern(self, shop_parser):
        """Vendor hire entry should match."""
        match = shop_parser.VENDOR_HIRE_PATTERN.match(VENDOR_HIRE_ENTRY)
        assert match is not None
        assert match.group(1) == "Sat Feb 14 12:09"
        assert match.group(2) == "PlayerName"
        assert match.group(3) == "1700"
        assert match.group(4) == "Erica Hills"
        assert match.group(5) == "24"

    def test_vendor_hire_extracts_data(self, shop_parser):
        """Verify vendor name and hours extraction."""
        entry = "Mon Jan 01 00:00 - Player paid 5000 Councils to hire Bob the Vendor for another 168 hours"
        match = shop_parser.VENDOR_HIRE_PATTERN.match(entry)
        assert match is not None
        assert match.group(3) == "5000"  # cost
        assert match.group(4) == "Bob the Vendor"  # vendor name
        assert match.group(5) == "168"  # hours

    def test_vendor_hire_no_match(self, shop_parser):
        """Non-matching lines should not match."""
        non_matching = [
            SALE_SINGLE,
            COLLECTION_ENTRY,
            "PlayerName hired a vendor",  # Incomplete format
        ]
        for line in non_matching:
            match = shop_parser.VENDOR_HIRE_PATTERN.match(line)
            assert match is None, f"Should not match: {line}"


class TestAddRemovePatterns:
    """Tests for add/remove item patterns."""

    def test_add_item_single(self, shop_parser):
        """Add single item should match with quantity=1."""
        match = shop_parser.ADD_ITEM_PATTERN.match(ADD_SINGLE)
        assert match is not None
        assert match.group(1) == "Thu Feb 12 10:00"
        assert match.group(2) == "PlayerName"
        assert match.group(3) == "Item"
        assert match.group(4) is None  # No quantity for single

    def test_add_item_stacked(self, shop_parser):
        """Add stacked items should match with correct quantity."""
        match = shop_parser.ADD_ITEM_PATTERN.match(ADD_STACKED)
        assert match is not None
        assert match.group(3) == "Grapefish"
        assert match.group(4) == "25"

    def test_remove_item_single(self, shop_parser):
        """Remove single item should match with quantity=1."""
        match = shop_parser.REMOVE_ITEM_PATTERN.match(REMOVE_SINGLE)
        assert match is not None
        assert match.group(1) == "Thu Feb 12 10:05"
        assert match.group(2) == "PlayerName"
        assert match.group(3) == "Item"
        assert match.group(4) is None

    def test_remove_item_stacked(self, shop_parser):
        """Remove stacked items should match with correct quantity."""
        match = shop_parser.REMOVE_ITEM_PATTERN.match(REMOVE_STACKED)
        assert match is not None
        assert match.group(3) == "Grapefish"
        assert match.group(4) == "10"


class TestShopSettingsPatterns:
    """Tests for shop settings patterns (name, sign, tag)."""

    def test_shop_name_pattern(self, shop_parser):
        """Shop name change should match."""
        match = shop_parser.SHOP_NAME_PATTERN.match(SHOP_NAME_ENTRY)
        assert match is not None
        assert match.group(1) == "Thu Feb 12 08:05"
        assert match.group(2) == "PlayerName"
        assert match.group(3) == "My Shop"

    def test_shop_sign_pattern(self, shop_parser):
        """Shop sign change should match."""
        match = shop_parser.SHOP_SIGN_PATTERN.match(SHOP_SIGN_ENTRY)
        assert match is not None
        assert match.group(1) == "Thu Feb 12 08:10"
        assert match.group(2) == "PlayerName"
        assert match.group(3) == "Welcome!"

    def test_shop_tag_pattern(self, shop_parser):
        """Shop tag change should match."""
        match = shop_parser.SHOP_TAG_PATTERN.match(SHOP_TAG_ENTRY)
        assert match is not None
        assert match.group(1) == "Thu Feb 12 08:15"
        assert match.group(2) == "PlayerName"
        assert match.group(3) == "Fish"


class TestProcessEntry:
    """Tests for entry processing logic."""

    def test_process_sale_updates_summary(self, shop_parser):
        """Sales should update sales_summary correctly."""
        data = shop_parser._create_empty_data()
        entry = {
            "type": "sale",
            "timestamp": "Thu Feb 12 13:35",
            "data": {
                "buyer": "PlayerName",
                "item": "Grapefish",
                "quantity": 5,
                "price_per": 75,
                "total": 375
            }
        }
        shop_parser._process_entry(entry, data)

        assert "Grapefish" in data["sales_summary"]
        assert data["sales_summary"]["Grapefish"]["total_sold"] == 5
        assert data["sales_summary"]["Grapefish"]["total_revenue"] == 375

    def test_process_sale_decrements_inventory(self, shop_parser):
        """Sales should reduce inventory quantity."""
        data = shop_parser._create_empty_data()
        # First set up some inventory
        data["current_inventory"]["Grapefish"] = {
            "quantity": 25,
            "price": 75,
            "visible": True
        }

        entry = {
            "type": "sale",
            "timestamp": "Thu Feb 12 13:35",
            "data": {
                "buyer": "PlayerName",
                "item": "Grapefish",
                "quantity": 5,
                "price_per": 75,
                "total": 375
            }
        }
        shop_parser._process_entry(entry, data)

        assert data["current_inventory"]["Grapefish"]["quantity"] == 20

    def test_process_set_price_creates_inventory(self, shop_parser):
        """Configure entry should create inventory entry with quantity/price."""
        data = shop_parser._create_empty_data()
        entry = {
            "type": "set_price",
            "timestamp": "Fri Feb 13 21:28",
            "data": {
                "player": "PlayerName",
                "item": "Amethyst",
                "quantity": 17,
                "price": 350
            }
        }
        shop_parser._process_entry(entry, data)

        assert "Amethyst" in data["current_inventory"]
        assert data["current_inventory"]["Amethyst"]["quantity"] == 17
        assert data["current_inventory"]["Amethyst"]["price"] == 350

    def test_process_visibility_creates_inventory(self, shop_parser):
        """Visibility entry should create inventory entry."""
        data = shop_parser._create_empty_data()
        entry = {
            "type": "visibility",
            "timestamp": "Fri Feb 13 01:18",
            "data": {
                "player": "PlayerName",
                "item": "Rubywall Crystal",
                "quantity": 40,
                "price": 250,
                "visible": True
            }
        }
        shop_parser._process_entry(entry, data)

        assert "Rubywall Crystal" in data["current_inventory"]
        assert data["current_inventory"]["Rubywall Crystal"]["quantity"] == 40
        assert data["current_inventory"]["Rubywall Crystal"]["price"] == 250
        assert data["current_inventory"]["Rubywall Crystal"]["visible"] is True

    def test_process_collection_updates_total(self, shop_parser):
        """Collections should increment total_collected."""
        data = shop_parser._create_empty_data()
        entry = {
            "type": "collection",
            "timestamp": "Sat Feb 14 12:09",
            "data": {
                "player": "PlayerName",
                "amount": 4350
            }
        }
        shop_parser._process_entry(entry, data)

        assert data["collections"]["total_collected"] == 4350
        assert len(data["collections"]["history"]) == 1
        assert data["collections"]["history"][0]["amount"] == 4350

    def test_process_add_item_increments_quantity(self, shop_parser):
        """Add item should increase inventory quantity."""
        data = shop_parser._create_empty_data()
        # First add
        entry = {
            "type": "add_item",
            "timestamp": "Thu Feb 12 10:00",
            "data": {
                "player": "PlayerName",
                "item": "Grapefish",
                "quantity": 25
            }
        }
        shop_parser._process_entry(entry, data)

        assert "Grapefish" in data["current_inventory"]
        assert data["current_inventory"]["Grapefish"]["quantity"] == 25

        # Second add should increment
        entry2 = {
            "type": "add_item",
            "timestamp": "Thu Feb 12 10:01",
            "data": {
                "player": "PlayerName",
                "item": "Grapefish",
                "quantity": 10
            }
        }
        shop_parser._process_entry(entry2, data)
        assert data["current_inventory"]["Grapefish"]["quantity"] == 35

    def test_process_remove_item_decrements_quantity(self, shop_parser):
        """Remove item should decrease inventory quantity."""
        data = shop_parser._create_empty_data()
        data["current_inventory"]["Grapefish"] = {
            "quantity": 25,
            "price": 75,
            "visible": True
        }

        entry = {
            "type": "remove_item",
            "timestamp": "Thu Feb 12 10:05",
            "data": {
                "player": "PlayerName",
                "item": "Grapefish",
                "quantity": 10
            }
        }
        shop_parser._process_entry(entry, data)

        assert data["current_inventory"]["Grapefish"]["quantity"] == 15

    def test_process_remove_item_deletes_when_zero(self, shop_parser):
        """Remove item should delete inventory entry when quantity reaches zero."""
        data = shop_parser._create_empty_data()
        data["current_inventory"]["Grapefish"] = {
            "quantity": 10,
            "price": 75,
            "visible": True
        }

        entry = {
            "type": "remove_item",
            "timestamp": "Thu Feb 12 10:05",
            "data": {
                "player": "PlayerName",
                "item": "Grapefish",
                "quantity": 10
            }
        }
        shop_parser._process_entry(entry, data)

        assert "Grapefish" not in data["current_inventory"]


class TestParseBookContent:
    """Tests for parsing ProcessBook content."""

    def test_parse_single_entry(self, shop_parser):
        """Single line book content should parse correctly."""
        content = SALE_SINGLE
        entries = shop_parser._parse_book_content(content, "12:00:00")

        assert len(entries) == 1
        assert entries[0]["type"] == "sale"
        assert entries[0]["data"]["buyer"] == "PlayerName"
        assert entries[0]["data"]["item"] == "Item"

    def test_parse_multiple_entries(self, shop_parser):
        """Multiple lines separated by \\n should parse correctly."""
        content = SALE_SINGLE + "\\n" + COLLECTION_ENTRY
        entries = shop_parser._parse_book_content(content, "12:00:00")

        assert len(entries) == 2
        assert entries[0]["type"] == "sale"
        assert entries[1]["type"] == "collection"

    def test_parse_mixed_entry_types(self, shop_parser):
        """Mixed entry types should all parse correctly."""
        content = "\\n".join([
            SALE_STACKED,
            COLLECTION_ENTRY,
            VISIBILITY_ENTRY
        ])
        entries = shop_parser._parse_book_content(content, "12:00:00")

        assert len(entries) == 3
        types = [e["type"] for e in entries]
        assert "sale" in types
        assert "collection" in types
        assert "visibility" in types

    def test_parse_unknown_entry(self, shop_parser):
        """Unknown format should become type='unknown'."""
        content = "This is not a valid shop log entry"
        entries = shop_parser._parse_book_content(content, "12:00:00")

        assert len(entries) == 1
        assert entries[0]["type"] == "unknown"
        assert entries[0]["raw"] == content


class TestShopParserIntegration:
    """Integration tests for ShopParser."""

    def test_clear_data(self, shop_parser):
        """clear_data() should reset all data."""
        # First add some data
        shop_parser._data = shop_parser._create_empty_data()
        shop_parser._data["sales_summary"]["Item"] = {
            "total_sold": 10,
            "total_revenue": 1000,
            "price_history": {}
        }
        shop_parser._data["collections"]["total_collected"] = 5000

        # Clear it
        shop_parser.clear_data()

        # Verify reset
        data = shop_parser.load_data()
        assert data["sales_summary"] == {}
        assert data["collections"]["total_collected"] == 0
        assert data["current_inventory"] == {}

    def test_get_sales_summary_sorted(self, shop_parser):
        """Sales summary should be sorted by revenue descending."""
        shop_parser._data = shop_parser._create_empty_data()
        shop_parser._data["sales_summary"] = {
            "LowValue": {"total_sold": 100, "total_revenue": 100, "price_history": {}},
            "HighValue": {"total_sold": 1, "total_revenue": 10000, "price_history": {}},
            "MidValue": {"total_sold": 10, "total_revenue": 500, "price_history": {}},
        }

        summary = shop_parser.get_sales_summary()

        assert len(summary) == 3
        assert summary[0]["item"] == "HighValue"
        assert summary[1]["item"] == "MidValue"
        assert summary[2]["item"] == "LowValue"

    def test_get_inventory_sorted(self, shop_parser):
        """Inventory should be sorted by item name."""
        shop_parser._data = shop_parser._create_empty_data()
        shop_parser._data["current_inventory"] = {
            "Zebra Hide": {"quantity": 5, "price": 100, "visible": True},
            "Apple": {"quantity": 10, "price": 50, "visible": True},
            "Banana": {"quantity": 3, "price": 75, "visible": True},
        }

        inventory = shop_parser.get_current_inventory()

        assert len(inventory) == 3
        assert inventory[0]["item"] == "Apple"
        assert inventory[1]["item"] == "Banana"
        assert inventory[2]["item"] == "Zebra Hide"

    def test_deduplication(self, shop_parser):
        """Same entries should not be processed twice."""
        data = shop_parser._create_empty_data()
        shop_parser._data = data

        # Process same entry twice
        entry = {
            "type": "sale",
            "timestamp": "Thu Feb 12 13:35",
            "timestamp_iso": "2025-02-12T13:35:00",
            "raw": SALE_STACKED,
            "data": {
                "buyer": "PlayerName",
                "item": "Grapefish",
                "quantity": 5,
                "price_per": 75,
                "total": 375
            }
        }

        # Create dedup key
        dedup_key = f"{entry['timestamp']}|{entry['raw']}"
        processed = set()

        # First process
        if dedup_key not in processed:
            processed.add(dedup_key)
            shop_parser._process_entry(entry, data)

        # Second process (should be skipped by dedup)
        if dedup_key not in processed:
            processed.add(dedup_key)
            shop_parser._process_entry(entry, data)

        # Should only have been processed once
        assert data["sales_summary"]["Grapefish"]["total_sold"] == 5
        assert data["sales_summary"]["Grapefish"]["total_revenue"] == 375

    def test_get_totals(self, shop_parser):
        """get_totals should return correct aggregate values."""
        shop_parser._data = shop_parser._create_empty_data()
        shop_parser._data["sales_summary"] = {
            "Item1": {"total_sold": 10, "total_revenue": 1000, "price_history": {}},
            "Item2": {"total_sold": 5, "total_revenue": 500, "price_history": {}},
        }

        totals = shop_parser.get_totals()

        assert totals["items"] == 2
        assert totals["sold"] == 15
        assert totals["revenue"] == 1500

    def test_has_data_empty(self, shop_parser):
        """has_data should return False when no data."""
        shop_parser._data = shop_parser._create_empty_data()
        assert shop_parser.has_data() is False

    def test_has_data_with_sales(self, shop_parser):
        """has_data should return True when sales exist."""
        shop_parser._data = shop_parser._create_empty_data()
        shop_parser._data["sales_summary"]["Item"] = {
            "total_sold": 1,
            "total_revenue": 100,
            "price_history": {}
        }
        assert shop_parser.has_data() is True

    def test_shop_name_updated(self, shop_parser):
        """Shop name should be updated by shop_name entry."""
        data = shop_parser._create_empty_data()
        entry = {
            "type": "shop_name",
            "timestamp": "Thu Feb 12 08:05",
            "data": {
                "player": "PlayerName",
                "name": "My Awesome Shop"
            }
        }
        shop_parser._process_entry(entry, data)

        assert data["shop_name"] == "My Awesome Shop"

    def test_shop_sign_updated(self, shop_parser):
        """Shop sign should be updated by shop_sign entry."""
        data = shop_parser._create_empty_data()
        entry = {
            "type": "shop_sign",
            "timestamp": "Thu Feb 12 08:10",
            "data": {
                "player": "PlayerName",
                "sign": "Best prices in town!"
            }
        }
        shop_parser._process_entry(entry, data)

        assert data["shop_sign"] == "Best prices in town!"

    def test_shop_tag_updated(self, shop_parser):
        """Shop tag should be updated by shop_tag entry."""
        data = shop_parser._create_empty_data()
        entry = {
            "type": "shop_tag",
            "timestamp": "Thu Feb 12 08:15",
            "data": {
                "player": "PlayerName",
                "tag": "Gems"
            }
        }
        shop_parser._process_entry(entry, data)

        assert data["shop_tag"] == "Gems"

    def test_get_shop_info(self, shop_parser):
        """get_shop_info should return name, sign, and tag."""
        shop_parser._data = shop_parser._create_empty_data()
        shop_parser._data["shop_name"] = "Test Shop"
        shop_parser._data["shop_sign"] = "Welcome"
        shop_parser._data["shop_tag"] = "Fish"

        info = shop_parser.get_shop_info()

        assert info["name"] == "Test Shop"
        assert info["sign"] == "Welcome"
        assert info["tag"] == "Fish"

    def test_collections_total(self, shop_parser):
        """get_collections_total should return correct total."""
        shop_parser._data = shop_parser._create_empty_data()
        shop_parser._data["collections"]["total_collected"] = 12345

        assert shop_parser.get_collections_total() == 12345
