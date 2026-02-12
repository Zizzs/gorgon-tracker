"""
Shop Parser for Gorgon Tracker.
Parses player shop logs from Player.log and caches data.
"""

import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from paths import get_gorgon_tracker_data_dir, get_pg_chatlog_dir


class ShopParser:
    """Parses player shop logs from Player.log ProcessBook entries."""

    # Pattern to extract ProcessBook entries for PlayerShopLog
    # Example: [18:48:27] LocalPlayer: ProcessBook("Today's Shop Logs", "Thu Feb 12 13:35 - PintoNobre bought...", "PlayerShopLog", ...)
    # Note: Content may contain escaped quotes (\") so we use (?:[^"\\]|\\.)* to handle them
    PROCESS_BOOK_PATTERN = re.compile(
        r'\[(\d{2}:\d{2}:\d{2})\] LocalPlayer: ProcessBook\("([^"]+)", "((?:[^"\\]|\\.)*)", "PlayerShopLog"'
    )

    # Pattern to match sale entries
    # Example: Thu Feb 12 13:35 - PintoNobre bought Grapefish x5 at a cost of 75 per 1 = 375
    SALE_PATTERN = re.compile(
        r'^(\w{3} \w{3} \d{1,2} \d{2}:\d{2}) - (\w+) bought (.+?)(?: x(\d+))? at a cost of (\d+) per 1 = (\d+)$'
    )

    # Pattern for collection entries
    # Example: Thu Feb 12 14:00 - PlayerName collected 500 councils
    COLLECTION_PATTERN = re.compile(
        r'^(\w{3} \w{3} \d{1,2} \d{2}:\d{2}) - (\w+) collected (\d+) councils$'
    )

    # Pattern for adding items
    # Example: Thu Feb 12 10:00 - PlayerName added Grapefish x25 to shop
    ADD_ITEM_PATTERN = re.compile(
        r'^(\w{3} \w{3} \d{1,2} \d{2}:\d{2}) - (\w+) added (.+?)(?: x(\d+))? to shop$'
    )

    # Pattern for removing items
    # Example: Thu Feb 12 10:05 - PlayerName removed Grapefish x10 from shop
    REMOVE_ITEM_PATTERN = re.compile(
        r'^(\w{3} \w{3} \d{1,2} \d{2}:\d{2}) - (\w+) removed (.+?)(?: x(\d+))? from shop$'
    )

    # Pattern for configuring price
    # Example: Thu Feb 12 10:10 - PlayerName set price of Grapefish to 75
    SET_PRICE_PATTERN = re.compile(
        r'^(\w{3} \w{3} \d{1,2} \d{2}:\d{2}) - (\w+) set price of (.+?) to (\d+)$'
    )

    # Pattern for making item visible/invisible
    # Example: Thu Feb 12 10:15 - PlayerName made Grapefish visible
    VISIBILITY_PATTERN = re.compile(
        r'^(\w{3} \w{3} \d{1,2} \d{2}:\d{2}) - (\w+) made (.+?) (visible|invisible)$'
    )

    # Pattern for vendor hire
    # Example: Thu Feb 12 08:00 - PlayerName hired vendor for 500 councils
    VENDOR_HIRE_PATTERN = re.compile(
        r'^(\w{3} \w{3} \d{1,2} \d{2}:\d{2}) - (\w+) hired vendor for (\d+) councils$'
    )

    # Pattern for shop name change
    # Example: Thu Feb 12 08:05 - PlayerName set shop name to "My Shop"
    SHOP_NAME_PATTERN = re.compile(
        r'^(\w{3} \w{3} \d{1,2} \d{2}:\d{2}) - (\w+) set shop name to "(.+)"$'
    )

    # Pattern for shop sign change
    # Example: Thu Feb 12 08:10 - PlayerName set shop sign to "Welcome!"
    SHOP_SIGN_PATTERN = re.compile(
        r'^(\w{3} \w{3} \d{1,2} \d{2}:\d{2}) - (\w+) set shop sign to "(.+)"$'
    )

    # Pattern for shop tag change
    # Example: Thu Feb 12 08:15 - PlayerName set shop tag to "Fish"
    SHOP_TAG_PATTERN = re.compile(
        r'^(\w{3} \w{3} \d{1,2} \d{2}:\d{2}) - (\w+) set shop tag to "(.+)"$'
    )

    def __init__(self, storage_dir: Optional[Path] = None):
        """
        Initialize the shop parser.

        Args:
            storage_dir: Path to storage directory. Auto-detected if None.
        """
        if storage_dir is None:
            storage_dir = get_gorgon_tracker_data_dir()

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.data_file = self.storage_dir / "shop_data.json"

        # Player.log path
        chatlog_dir = get_pg_chatlog_dir()
        if chatlog_dir:
            self.player_log_path = chatlog_dir.parent / "Player.log"
        else:
            self.player_log_path = Path("")

        # Cached data
        self._data: Optional[dict] = None

    def _parse_timestamp_with_year(self, timestamp_str: str) -> str:
        """
        Parse a timestamp like "Thu Feb 12 13:35" and add the year.

        Since logs don't include year, we infer it:
        - Use current year by default
        - If the resulting date is in the future, use previous year

        Args:
            timestamp_str: Timestamp like "Thu Feb 12 13:35"

        Returns:
            ISO format string like "2025-02-12T13:35:00"
        """
        if not timestamp_str:
            return ""

        try:
            # Parse without year - format: "Thu Feb 12 13:35"
            parsed = datetime.strptime(timestamp_str, "%a %b %d %H:%M")

            # Try current year first
            now = datetime.now()
            candidate = parsed.replace(year=now.year)

            # If the date is in the future (more than 1 day ahead), use previous year
            if candidate > now + timedelta(days=1):
                candidate = parsed.replace(year=now.year - 1)

            return candidate.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            # If parsing fails, return empty string
            return ""

    def load_data(self) -> dict:
        """Load shop data from cache file."""
        if self._data is not None:
            return self._data

        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = self._create_empty_data()
        else:
            self._data = self._create_empty_data()

        return self._data

    def _create_empty_data(self) -> dict:
        """Create empty shop data structure."""
        return {
            "version": "1.0",
            "last_updated": None,
            "shop_name": None,
            "shop_sign": None,
            "shop_tag": None,
            "sales_summary": {},
            "current_inventory": {},
            "collections": {
                "total_collected": 0,
                "history": []
            },
            "raw_logs": [],
            "processed_entries": []  # For deduplication
        }

    def save_data(self):
        """Save shop data to cache file."""
        if self._data is None:
            return

        self._data["last_updated"] = datetime.now().isoformat()

        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=2)

    def parse_player_log(self) -> bool:
        """
        Parse Player.log for ProcessBook shop log entries.

        Returns:
            True if new entries were found, False otherwise
        """
        if not self.player_log_path.exists():
            return False

        data = self.load_data()
        processed_entries = set(data.get("processed_entries", []))
        new_entries_found = False

        try:
            with open(self.player_log_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    match = self.PROCESS_BOOK_PATTERN.search(line)
                    if match:
                        timestamp = match.group(1)
                        book_title = match.group(2)
                        content = match.group(3)

                        # Parse individual entries from the book content
                        entries = self._parse_book_content(content, timestamp)

                        for entry in entries:
                            # Create deduplication key
                            dedup_key = f"{entry['timestamp']}|{entry['raw']}"

                            if dedup_key not in processed_entries:
                                processed_entries.add(dedup_key)
                                new_entries_found = True

                                # Process the entry
                                self._process_entry(entry, data)

                                # Add to raw logs (unlimited storage)
                                data["raw_logs"].insert(0, entry)

        except IOError:
            return False

        if new_entries_found:
            # Update processed entries list (keep last 2000 for deduplication)
            data["processed_entries"] = list(processed_entries)[-2000:]
            self.save_data()

        return new_entries_found

    def _parse_book_content(self, content: str, log_timestamp: str) -> list[dict]:
        """
        Parse the content of a ProcessBook entry into individual log entries.

        Args:
            content: The raw content string from ProcessBook
            log_timestamp: The timestamp from the Player.log line

        Returns:
            List of parsed entry dicts
        """
        entries = []

        # The content uses literal \n for newlines in the ProcessBook string
        lines = content.split("\\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            entry = {
                "log_timestamp": log_timestamp,
                "timestamp": None,
                "timestamp_iso": "",
                "type": "unknown",
                "raw": line,
                "data": {}
            }

            # Try to match each pattern
            if match := self.SALE_PATTERN.match(line):
                entry["type"] = "sale"
                entry["timestamp"] = match.group(1)
                entry["data"] = {
                    "buyer": match.group(2),
                    "item": match.group(3),
                    "quantity": int(match.group(4)) if match.group(4) else 1,
                    "price_per": int(match.group(5)),
                    "total": int(match.group(6))
                }
            elif match := self.COLLECTION_PATTERN.match(line):
                entry["type"] = "collection"
                entry["timestamp"] = match.group(1)
                entry["data"] = {
                    "player": match.group(2),
                    "amount": int(match.group(3))
                }
            elif match := self.ADD_ITEM_PATTERN.match(line):
                entry["type"] = "add_item"
                entry["timestamp"] = match.group(1)
                entry["data"] = {
                    "player": match.group(2),
                    "item": match.group(3),
                    "quantity": int(match.group(4)) if match.group(4) else 1
                }
            elif match := self.REMOVE_ITEM_PATTERN.match(line):
                entry["type"] = "remove_item"
                entry["timestamp"] = match.group(1)
                entry["data"] = {
                    "player": match.group(2),
                    "item": match.group(3),
                    "quantity": int(match.group(4)) if match.group(4) else 1
                }
            elif match := self.SET_PRICE_PATTERN.match(line):
                entry["type"] = "set_price"
                entry["timestamp"] = match.group(1)
                entry["data"] = {
                    "player": match.group(2),
                    "item": match.group(3),
                    "price": int(match.group(4))
                }
            elif match := self.VISIBILITY_PATTERN.match(line):
                entry["type"] = "visibility"
                entry["timestamp"] = match.group(1)
                entry["data"] = {
                    "player": match.group(2),
                    "item": match.group(3),
                    "visible": match.group(4) == "visible"
                }
            elif match := self.VENDOR_HIRE_PATTERN.match(line):
                entry["type"] = "vendor_hire"
                entry["timestamp"] = match.group(1)
                entry["data"] = {
                    "player": match.group(2),
                    "cost": int(match.group(3))
                }
            elif match := self.SHOP_NAME_PATTERN.match(line):
                entry["type"] = "shop_name"
                entry["timestamp"] = match.group(1)
                entry["data"] = {
                    "player": match.group(2),
                    "name": match.group(3)
                }
            elif match := self.SHOP_SIGN_PATTERN.match(line):
                entry["type"] = "shop_sign"
                entry["timestamp"] = match.group(1)
                entry["data"] = {
                    "player": match.group(2),
                    "sign": match.group(3)
                }
            elif match := self.SHOP_TAG_PATTERN.match(line):
                entry["type"] = "shop_tag"
                entry["timestamp"] = match.group(1)
                entry["data"] = {
                    "player": match.group(2),
                    "tag": match.group(3)
                }

            # Convert timestamp to ISO format with year for sorting
            if entry["timestamp"]:
                entry["timestamp_iso"] = self._parse_timestamp_with_year(entry["timestamp"])

            entries.append(entry)

        return entries

    def _process_entry(self, entry: dict, data: dict):
        """
        Process a parsed entry and update aggregated data.

        Args:
            entry: Parsed entry dict
            data: Shop data dict to update
        """
        entry_type = entry["type"]
        entry_data = entry["data"]

        if entry_type == "sale":
            self._update_sales_summary(entry_data, data)
            self._update_inventory_from_sale(entry_data, data)

        elif entry_type == "collection":
            data["collections"]["total_collected"] += entry_data["amount"]
            data["collections"]["history"].insert(0, {
                "timestamp": entry["timestamp"],
                "amount": entry_data["amount"]
            })
            # Keep last 100 collection entries
            if len(data["collections"]["history"]) > 100:
                data["collections"]["history"] = data["collections"]["history"][:100]

        elif entry_type == "add_item":
            self._update_inventory_add(entry_data, data)

        elif entry_type == "remove_item":
            self._update_inventory_remove(entry_data, data)

        elif entry_type == "set_price":
            item = entry_data["item"]
            if item in data["current_inventory"]:
                data["current_inventory"][item]["price"] = entry_data["price"]

        elif entry_type == "visibility":
            item = entry_data["item"]
            if item in data["current_inventory"]:
                data["current_inventory"][item]["visible"] = entry_data["visible"]

        elif entry_type == "shop_name":
            data["shop_name"] = entry_data["name"]

        elif entry_type == "shop_sign":
            data["shop_sign"] = entry_data["sign"]

        elif entry_type == "shop_tag":
            data["shop_tag"] = entry_data["tag"]

    def _update_sales_summary(self, sale_data: dict, data: dict):
        """Update sales summary with a new sale."""
        item = sale_data["item"]
        quantity = sale_data["quantity"]
        price = sale_data["price_per"]
        total = sale_data["total"]

        if item not in data["sales_summary"]:
            data["sales_summary"][item] = {
                "total_sold": 0,
                "total_revenue": 0,
                "price_history": {}
            }

        summary = data["sales_summary"][item]
        summary["total_sold"] += quantity
        summary["total_revenue"] += total

        # Track price history
        price_str = str(price)
        if price_str not in summary["price_history"]:
            summary["price_history"][price_str] = {
                "count": 0,
                "first_seen": datetime.now().isoformat(),
                "last_seen": None
            }

        summary["price_history"][price_str]["count"] += quantity
        summary["price_history"][price_str]["last_seen"] = datetime.now().isoformat()

    def _update_inventory_from_sale(self, sale_data: dict, data: dict):
        """Update inventory when an item is sold."""
        item = sale_data["item"]
        quantity = sale_data["quantity"]

        if item in data["current_inventory"]:
            data["current_inventory"][item]["quantity"] -= quantity
            if data["current_inventory"][item]["quantity"] <= 0:
                del data["current_inventory"][item]

    def _update_inventory_add(self, add_data: dict, data: dict):
        """Update inventory when items are added."""
        item = add_data["item"]
        quantity = add_data["quantity"]

        if item not in data["current_inventory"]:
            data["current_inventory"][item] = {
                "quantity": 0,
                "price": None,
                "visible": True
            }

        data["current_inventory"][item]["quantity"] += quantity

    def _update_inventory_remove(self, remove_data: dict, data: dict):
        """Update inventory when items are removed."""
        item = remove_data["item"]
        quantity = remove_data["quantity"]

        if item in data["current_inventory"]:
            data["current_inventory"][item]["quantity"] -= quantity
            if data["current_inventory"][item]["quantity"] <= 0:
                del data["current_inventory"][item]

    # --- Public API for GUI ---

    def get_sales_summary(self) -> list[dict]:
        """
        Get sales summary sorted by total revenue (descending).

        Returns:
            List of dicts with item name, total_sold, total_revenue, avg_price
        """
        data = self.load_data()
        sales = []

        for item, summary in data.get("sales_summary", {}).items():
            total_sold = summary.get("total_sold", 0)
            total_revenue = summary.get("total_revenue", 0)
            avg_price = total_revenue / total_sold if total_sold > 0 else 0

            sales.append({
                "item": item,
                "total_sold": total_sold,
                "total_revenue": total_revenue,
                "avg_price": round(avg_price, 1),
                "price_history": summary.get("price_history", {})
            })

        # Sort by total revenue descending
        sales.sort(key=lambda x: x["total_revenue"], reverse=True)
        return sales

    def get_current_inventory(self) -> list[dict]:
        """
        Get current shop inventory.

        Returns:
            List of dicts with item name, quantity, price, visible status
        """
        data = self.load_data()
        inventory = []

        for item, info in data.get("current_inventory", {}).items():
            inventory.append({
                "item": item,
                "quantity": info.get("quantity", 0),
                "price": info.get("price"),
                "visible": info.get("visible", True)
            })

        # Sort by item name
        inventory.sort(key=lambda x: x["item"].lower())
        return inventory

    def get_raw_logs(self, page: int = 1, page_size: int = 100, newest_first: bool = True) -> tuple[list[dict], int]:
        """
        Get raw log entries with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Number of entries per page
            newest_first: Sort order (True = newest first, False = oldest first)

        Returns:
            Tuple of (list of raw log entry dicts, total count)
        """
        data = self.load_data()
        all_logs = data.get("raw_logs", [])
        total = len(all_logs)

        # Sort by timestamp_iso (entries without timestamp_iso sort to the end)
        all_logs = sorted(
            all_logs,
            key=lambda x: x.get("timestamp_iso", ""),
            reverse=newest_first
        )

        # Calculate pagination
        start = (page - 1) * page_size
        end = start + page_size

        return all_logs[start:end], total

    def get_sales_for_item(self, item_name: str) -> list[dict]:
        """
        Get all individual sales for a specific item.

        Args:
            item_name: The item name to filter by

        Returns:
            List of sale entries sorted by timestamp (newest first)
        """
        data = self.load_data()
        raw_logs = data.get("raw_logs", [])

        # Filter for sales of this specific item
        sales = [
            log for log in raw_logs
            if log.get("type") == "sale" and log.get("data", {}).get("item") == item_name
        ]

        # Sort by timestamp_iso (newest first)
        sales.sort(key=lambda x: x.get("timestamp_iso", ""), reverse=True)

        return sales

    def get_collections_total(self) -> int:
        """Get total councils collected from shop."""
        data = self.load_data()
        return data.get("collections", {}).get("total_collected", 0)

    def get_shop_info(self) -> dict:
        """Get shop name, sign, and tag."""
        data = self.load_data()
        return {
            "name": data.get("shop_name"),
            "sign": data.get("shop_sign"),
            "tag": data.get("shop_tag")
        }

    def get_totals(self) -> dict:
        """Get overall totals for summary display."""
        data = self.load_data()
        sales_summary = data.get("sales_summary", {})

        total_items = len(sales_summary)
        total_sold = sum(s.get("total_sold", 0) for s in sales_summary.values())
        total_revenue = sum(s.get("total_revenue", 0) for s in sales_summary.values())

        return {
            "items": total_items,
            "sold": total_sold,
            "revenue": total_revenue
        }

    def has_data(self) -> bool:
        """Check if there is any shop data."""
        data = self.load_data()
        return bool(data.get("sales_summary") or data.get("raw_logs"))

    def clear_data(self):
        """Clear all shop data (reset to empty)."""
        self._data = self._create_empty_data()
        self.save_data()
