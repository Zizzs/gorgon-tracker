#!/usr/bin/env python3
"""
Gorgon Tracker - CustomTkinter GUI

A graphical interface for parsing Project Gorgon chat logs
and viewing creature loot statistics.
"""

import os
import sys
import json
import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from tkinter import ttk
from dotenv import load_dotenv
import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

from loot_parser import LootParser, ZONE_NAMES
from paths import get_gorgon_tracker_data_dir, get_pg_chatlog_dir
from reports_parser import ReportsParser, FAVOR_DISPLAY, FAVOR_LEVELS

# List of valid zone display names for dropdown
VALID_ZONES = sorted([name for name in ZONE_NAMES.values() if name is not None])

# Settings file path - now stored in LocalLow/GorgonTracker
SETTINGS_FILE = get_gorgon_tracker_data_dir() / "gui_settings.json"


class LootUploaderApp(ctk.CTk, TkinterDnD.DnDWrapper):
    """Main application window for the loot uploader."""

    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)

        # Window configuration
        self.title("Gorgon Tracker")
        self.geometry("1050x650")
        self.minsize(700, 500)

        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Initialize parser
        self.parser = None
        self.selected_creature = None
        self.creature_buttons = {}
        self.creature_zone_labels = {}

        # Options and Stats state
        self.showing_options = False
        self.showing_stats = False
        self.auto_update_enabled = False
        self.auto_update_interval = 60  # seconds
        self.auto_update_job = None
        self.last_update_timestamp = None  # ISO format string or None

        # Search state
        self.search_var = ctk.StringVar()
        self.storage_search_var = ctk.StringVar()

        # Current left tab selection
        self.current_left_tab = "Creatures"

        # Selected items for each tab
        self.selected_skill = None
        self.selected_npc = None
        self.selected_storage_item = None
        self.selected_quest = None

        # Vault selection for storage tab
        self.selected_vault = "All"

        # Reports parser for character/storage/quests
        self.reports_parser = ReportsParser()

        # Thread synchronization for shared data
        self._data_lock = threading.Lock()

        # Load settings
        self._load_settings()

        # Load configuration and create parser
        self._load_config()

        # Build UI
        self._create_widgets()

        # Initial data load
        self._refresh_creature_list()
        self._refresh_reports_data()

        # Start auto-update if enabled
        if self.auto_update_enabled:
            self._start_auto_update()
        else:
            self._update_auto_status()

    def _load_settings(self):
        """Load GUI settings from file, migrating from legacy location if needed."""
        # Migrate legacy settings if needed
        self._migrate_legacy_settings()

        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    self.auto_update_enabled = settings.get("auto_update_enabled", False)
                    self.auto_update_interval = settings.get("auto_update_interval", 60)
                    self.last_update_timestamp = settings.get("last_update_timestamp", None)
            except (json.JSONDecodeError, IOError):
                pass

    def _migrate_legacy_settings(self):
        """Migrate settings from legacy location (project root) if needed."""
        import shutil

        # Get the project root
        if getattr(sys, 'frozen', False):
            project_root = Path(sys.executable).parent
        else:
            project_root = Path(__file__).parent

        legacy_settings = project_root / "gui_settings.json"

        # Only migrate if legacy exists and new doesn't
        if legacy_settings.exists() and not SETTINGS_FILE.exists():
            try:
                shutil.copy2(legacy_settings, SETTINGS_FILE)
                print(f"Migrated gui_settings.json to {SETTINGS_FILE}")
            except Exception as e:
                print(f"Warning: Could not migrate gui_settings.json: {e}")

    def _save_settings(self):
        """Save GUI settings to file."""
        settings = {
            "auto_update_enabled": self.auto_update_enabled,
            "auto_update_interval": self.auto_update_interval,
            "last_update_timestamp": self.last_update_timestamp
        }
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
        except IOError:
            pass

    def _load_config(self):
        """Load configuration from .env file or auto-detect paths."""
        load_dotenv()

        # Try .env first, then auto-detect
        chatlog_dir = os.getenv("USER_CHATLOG_FILE_LOCATION")

        if not chatlog_dir:
            # Try auto-detection
            detected_dir = get_pg_chatlog_dir()
            if detected_dir:
                chatlog_dir = str(detected_dir)

        if not chatlog_dir:
            self._show_config_error()
            return

        # Storage directory is automatically set to LocalLow/GorgonTracker
        self.parser = LootParser(
            chatlog_dir=chatlog_dir,
            output_dir="CreaturePages"
        )

    def _show_config_error(self):
        """Show error when ChatLogs directory cannot be found."""
        error_frame = ctk.CTkFrame(self)
        error_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            error_frame,
            text="Configuration Error",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=20)

        ctk.CTkLabel(
            error_frame,
            text="Could not find Project Gorgon ChatLogs folder.\n\n"
                 "Auto-detection failed. You can manually set the path\n"
                 "by creating a .env file with:\n"
                 "USER_CHATLOG_FILE_LOCATION=C:\\path\\to\\ChatLogs\n\n"
                 "Typical location:\n"
                 "C:\\Users\\YourName\\AppData\\LocalLow\\Elder Game\\Project Gorgon\\ChatLogs",
            font=ctk.CTkFont(size=14),
            justify="left"
        ).pack(pady=10)

    def _configure_treeview_style(self):
        """Configure ttk.Treeview style for dark mode."""
        style = ttk.Style()

        # Dark mode colors
        bg_color = "#2b2b2b"
        fg_color = "#DCE4EE"
        selected_bg = "#1f538d"
        header_bg = "#333333"

        style.theme_use("clam")

        # Configure Treeview
        style.configure(
            "Dark.Treeview",
            background=bg_color,
            foreground=fg_color,
            fieldbackground=bg_color,
            borderwidth=0,
            rowheight=24
        )

        style.configure(
            "Dark.Treeview.Heading",
            background=header_bg,
            foreground=fg_color,
            borderwidth=1,
            relief="flat"
        )

        style.map(
            "Dark.Treeview",
            background=[("selected", selected_bg)],
            foreground=[("selected", "white")]
        )

        style.map(
            "Dark.Treeview.Heading",
            background=[("active", "#404040")]
        )

        # Remove the border/frame around the Treeview
        style.layout("Dark.Treeview", [
            ('Dark.Treeview.treearea', {'sticky': 'nswe'})
        ])

    def _create_widgets(self):
        """Create the main UI layout."""
        if self.parser is None:
            return

        # Configure treeview style for dark mode
        self._configure_treeview_style()

        # Top button bar
        self._create_button_bar()

        # Main content area (creature list + detail panel)
        self._create_main_content()

        # Status log at bottom
        self._create_status_log()

    def _create_button_bar(self):
        """Create the top button bar."""
        button_frame = ctk.CTkFrame(self, height=50)
        button_frame.pack(fill="x", padx=10, pady=10)
        button_frame.pack_propagate(False)

        self.update_button = ctk.CTkButton(
            button_frame,
            text="Update",
            command=self._run_update,
            width=100,
            height=35,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.update_button.pack(side="left", padx=(10, 5), pady=7)

        self.full_rescan_button = ctk.CTkButton(
            button_frame,
            text="Full Rescan",
            command=self._run_full_rescan,
            width=110,
            height=35,
            font=ctk.CTkFont(size=14)
        )
        self.full_rescan_button.pack(side="left", padx=5, pady=7)

        # Separator
        ctk.CTkLabel(
            button_frame,
            text="|",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        ).pack(side="left", padx=10)

        # Last update timestamp
        self.last_update_label = ctk.CTkLabel(
            button_frame,
            text=self._format_last_update(),
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.last_update_label.pack(side="left", padx=5)

        # Separator
        ctk.CTkLabel(
            button_frame,
            text="|",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        ).pack(side="left", padx=5)

        # Current zone indicator
        self.zone_label = ctk.CTkLabel(
            button_frame,
            text=self._format_current_zone(),
            font=ctk.CTkFont(size=11),
            text_color="#4CAF50"
        )
        self.zone_label.pack(side="left", padx=5)

        # Status indicator
        self.status_label = ctk.CTkLabel(
            button_frame,
            text="Ready",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(side="left", padx=20)

        # Options button (right side)
        self.options_button = ctk.CTkButton(
            button_frame,
            text="Options",
            command=self._toggle_options,
            width=100,
            height=35,
            font=ctk.CTkFont(size=14)
        )
        self.options_button.pack(side="right", padx=10, pady=7)

        # Stats button
        self.stats_button = ctk.CTkButton(
            button_frame,
            text="Stats",
            command=self._toggle_stats,
            width=100,
            height=35,
            font=ctk.CTkFont(size=14)
        )
        self.stats_button.pack(side="right", padx=5, pady=7)


    def _create_main_content(self):
        """Create the main content area with creature list and detail panel."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Configure grid - uniform ensures both columns stay same size
        main_frame.grid_columnconfigure(0, weight=1, uniform="main_cols", minsize=300)
        main_frame.grid_columnconfigure(1, weight=1, uniform="main_cols", minsize=300)
        main_frame.grid_rowconfigure(0, weight=1)

        # Left panel - Creature list
        self._create_creature_list(main_frame)

        # Right panel - Loot details
        self._create_detail_panel(main_frame)

    def _create_creature_list(self, parent):
        """Create the left panel with tabbed interface."""
        left_frame = ctk.CTkFrame(parent)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(5, 5), pady=5)

        # Create tabview
        self.left_tabview = ctk.CTkTabview(left_frame, height=50)
        self.left_tabview.pack(fill="both", expand=True, padx=5, pady=5)

        # Add tabs
        self.left_tabview.add("Creatures")
        self.left_tabview.add("Character")
        self.left_tabview.add("Storage")
        self.left_tabview.add("Quests")

        # Set default tab
        self.left_tabview.set("Creatures")

        # Track which tabs have been populated (lazy loading)
        self._tabs_populated = {"Creatures": False, "Character": False, "Storage": False, "Quests": False}

        # Bind tab change event
        self.left_tabview.configure(command=self._on_tab_changed)

        # Create UI structure for each tab (but don't populate data yet)
        self._create_creatures_tab()
        self._create_character_tab()
        self._create_storage_tab()
        self._create_quests_tab()

    def _on_tab_changed(self):
        """Handle tab change events with lazy loading."""
        self.current_left_tab = self.left_tabview.get()

        # Lazy load tab content on first view
        if not self._tabs_populated.get(self.current_left_tab, False):
            self._tabs_populated[self.current_left_tab] = True
            if self.current_left_tab == "Character":
                self._refresh_character_tab()
            elif self.current_left_tab == "Storage":
                self._refresh_storage_tab()
            elif self.current_left_tab == "Quests":
                self._refresh_quests_tab()

    def _create_creatures_tab(self):
        """Create the Creatures tab content."""
        tab = self.left_tabview.tab("Creatures")

        # Search box
        search_frame = ctk.CTkFrame(tab, fg_color="transparent")
        search_frame.pack(fill="x", padx=5, pady=(5, 5))

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Search creatures or items...",
            textvariable=self.search_var,
            width=220,
            height=28,
            font=ctk.CTkFont(size=12)
        )
        self.search_entry.pack(side="left", fill="x", expand=True)

        self.search_clear_btn = ctk.CTkButton(
            search_frame,
            text="x",
            width=28,
            height=28,
            font=ctk.CTkFont(size=12),
            command=self._clear_search
        )
        self.search_clear_btn.pack(side="left", padx=(5, 0))

        # Bind search variable to callback
        self.search_var.trace_add("write", self._on_search_changed)

        # Column headers
        col_header = ctk.CTkFrame(tab, fg_color="transparent", height=25)
        col_header.pack(fill="x", padx=5)
        col_header.pack_propagate(False)

        ctk.CTkLabel(
            col_header,
            text="Name",
            font=ctk.CTkFont(size=11),
            width=220,
            anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(
            col_header,
            text="Kills",
            font=ctk.CTkFont(size=11),
            width=50,
            anchor="center"
        ).pack(side="left")

        # Scrollable creature list
        self.creature_scroll = ctk.CTkScrollableFrame(tab)
        self.creature_scroll.pack(fill="both", expand=True, padx=0, pady=5)

    def _create_character_tab(self):
        """Create the Character tab content."""
        tab = self.left_tabview.tab("Character")

        # Scrollable content
        self.character_scroll = ctk.CTkScrollableFrame(tab)
        self.character_scroll.pack(fill="both", expand=True, padx=0, pady=5)

        # Character header (will be populated on refresh)
        self.char_header_frame = ctk.CTkFrame(self.character_scroll, fg_color="transparent")
        self.char_header_frame.pack(fill="x", padx=5, pady=(0, 10))

        self.char_name_label = ctk.CTkLabel(
            self.char_header_frame,
            text="No character data",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.char_name_label.pack(anchor="w")

        self.char_info_label = ctk.CTkLabel(
            self.char_header_frame,
            text="Export character data from game to view",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.char_info_label.pack(anchor="w")

        # Currencies section
        self.currencies_frame = ctk.CTkFrame(self.character_scroll)
        self.currencies_frame.pack(fill="x", padx=5, pady=(0, 10))

        # Skills section header
        self.skills_header = ctk.CTkButton(
            self.character_scroll,
            text="Skills",
            anchor="w",
            fg_color=("gray85", "gray25"),
            text_color=("gray10", "gray90"),
            hover_color=("gray75", "gray35"),
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._toggle_section("skills")
        )
        self.skills_header.pack(fill="x", padx=5, pady=(5, 2))

        self.skills_content = ctk.CTkFrame(self.character_scroll, fg_color="transparent")
        self.skills_content.pack(fill="x", padx=5, pady=(0, 10))

        # NPCs section header
        self.npcs_header = ctk.CTkButton(
            self.character_scroll,
            text="NPCs",
            anchor="w",
            fg_color=("gray85", "gray25"),
            text_color=("gray10", "gray90"),
            hover_color=("gray75", "gray35"),
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._toggle_section("npcs")
        )
        self.npcs_header.pack(fill="x", padx=5, pady=(5, 2))

        self.npcs_content = ctk.CTkFrame(self.character_scroll, fg_color="transparent")
        self.npcs_content.pack(fill="x", padx=5, pady=(0, 10))

        # Section expanded states
        self.section_expanded = {"skills": True, "npcs": True}

    def _toggle_section(self, section: str):
        """Toggle collapsible section."""
        self.section_expanded[section] = not self.section_expanded.get(section, True)
        self._refresh_character_tab()

    def _create_storage_tab(self):
        """Create the Storage tab content."""
        tab = self.left_tabview.tab("Storage")

        # Vault selector
        vault_frame = ctk.CTkFrame(tab, fg_color="transparent")
        vault_frame.pack(fill="x", padx=5, pady=(5, 5))

        ctk.CTkLabel(
            vault_frame,
            text="Vault:",
            font=ctk.CTkFont(size=12)
        ).pack(side="left")

        self.vault_dropdown = ctk.CTkOptionMenu(
            vault_frame,
            values=["All"],
            width=150,
            height=28,
            command=self._on_vault_changed
        )
        self.vault_dropdown.pack(side="left", padx=(5, 0))

        # Search box for storage
        search_frame = ctk.CTkFrame(tab, fg_color="transparent")
        search_frame.pack(fill="x", padx=5, pady=(5, 5))

        self.storage_search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Search items...",
            textvariable=self.storage_search_var,
            width=220,
            height=28,
            font=ctk.CTkFont(size=12)
        )
        self.storage_search_entry.pack(side="left", fill="x", expand=True)

        self.storage_search_clear = ctk.CTkButton(
            search_frame,
            text="x",
            width=28,
            height=28,
            font=ctk.CTkFont(size=12),
            command=lambda: self.storage_search_var.set("")
        )
        self.storage_search_clear.pack(side="left", padx=(5, 0))

        self.storage_search_var.trace_add("write", lambda *args: self._refresh_storage_tab())

        # Summary row
        self.storage_summary = ctk.CTkLabel(
            tab,
            text="No storage data",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.storage_summary.pack(anchor="w", padx=10, pady=(0, 5))

        # Use Treeview for performance (handles many items efficiently)
        tree_frame = ctk.CTkFrame(tab, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        columns = ("name", "qty", "location")
        self.storage_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="Dark.Treeview"
        )

        # Sort state: column -> ascending (True/False), default sort by name ascending
        self.storage_sort_state = {"name": True, "qty": True, "location": True}
        self.storage_sort_column = "name"

        # Column headings with click-to-sort (show arrow on default sort column)
        self.storage_tree.heading("name", text="Item \u25b2", anchor="w",
                                   command=lambda: self._sort_storage("name"))
        self.storage_tree.heading("qty", text="Qty", anchor="center",
                                   command=lambda: self._sort_storage("qty"))
        self.storage_tree.heading("location", text="Location", anchor="w",
                                   command=lambda: self._sort_storage("location"))

        self.storage_tree.column("name", width=160, minwidth=100, anchor="w")
        self.storage_tree.column("qty", width=40, minwidth=30, anchor="center")
        self.storage_tree.column("location", width=80, minwidth=50, anchor="w")

        # Rarity color tags
        self.storage_tree.tag_configure("common", foreground="#FFFFFF")
        self.storage_tree.tag_configure("uncommon", foreground="#4CAF50")
        self.storage_tree.tag_configure("rare", foreground="#2196F3")
        self.storage_tree.tag_configure("epic", foreground="#9C27B0")
        self.storage_tree.tag_configure("legendary", foreground="#FF9800")

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.storage_tree.yview)
        self.storage_tree.configure(yscrollcommand=scrollbar.set)

        self.storage_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _sort_storage(self, column: str):
        """Sort storage treeview by column, toggling ascending/descending."""
        # Toggle sort direction if clicking same column, else start ascending
        if self.storage_sort_column == column:
            self.storage_sort_state[column] = not self.storage_sort_state[column]
        else:
            self.storage_sort_state[column] = True
            self.storage_sort_column = column

        ascending = self.storage_sort_state[column]

        # Get all items with their values
        items = []
        for item_id in self.storage_tree.get_children():
            values = self.storage_tree.item(item_id, "values")
            tags = self.storage_tree.item(item_id, "tags")
            items.append((item_id, values, tags))

        # Sort based on column
        col_index = {"name": 0, "qty": 1, "location": 2}[column]

        if column == "qty":
            # Numeric sort for quantity
            items.sort(key=lambda x: int(x[1][col_index]), reverse=not ascending)
        else:
            # Alphabetical sort for name and location
            items.sort(key=lambda x: x[1][col_index].lower(), reverse=not ascending)

        # Reorder items in treeview
        for idx, (item_id, values, tags) in enumerate(items):
            self.storage_tree.move(item_id, "", idx)

        # Update header to show sort indicator
        arrow = " \u25b2" if ascending else " \u25bc"
        headers = {"name": "Item", "qty": "Qty", "location": "Location"}
        for col, text in headers.items():
            if col == column:
                self.storage_tree.heading(col, text=text + arrow)
            else:
                self.storage_tree.heading(col, text=text)

    def _on_vault_changed(self, value):
        """Handle vault selection change."""
        self.selected_vault = value
        self._refresh_storage_tab()

    def _create_quests_tab(self):
        """Create the Quests tab content."""
        tab = self.left_tabview.tab("Quests")

        # Status label
        self.quests_status = ctk.CTkLabel(
            tab,
            text="Loading quest data...",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.quests_status.pack(anchor="w", padx=10, pady=(5, 5))

        # Scrollable quest list
        self.quests_scroll = ctk.CTkScrollableFrame(tab)
        self.quests_scroll.pack(fill="both", expand=True, padx=0, pady=5)

        # Quest zone expanded states
        self.quest_zone_expanded = {}

    def _refresh_reports_data(self):
        """Refresh reports data for currently visible tab only (lazy loading)."""
        # Only refresh the currently visible tab to avoid lag
        if self.current_left_tab == "Character":
            self._refresh_character_tab()
        elif self.current_left_tab == "Storage":
            self._refresh_storage_tab()
        elif self.current_left_tab == "Quests":
            self._refresh_quests_tab()
        # Creatures tab is handled by _refresh_creature_list()

    def _refresh_character_tab(self):
        """Refresh the Character tab content."""
        if not hasattr(self, 'char_name_label'):
            return

        # Load character data
        char_data = self.reports_parser.load_character()

        if not char_data:
            self.char_name_label.configure(text="No character data")
            self.char_info_label.configure(text="Export character data from game to view")
            return

        # Update header
        char_name = self.reports_parser.get_character_name()
        race = self.reports_parser.get_race()
        gold = self.reports_parser.get_gold()

        self.char_name_label.configure(text=char_name or "Unknown")
        self.char_info_label.configure(text=f"{race or 'Unknown'} - {gold:,} Gold")

        # Update currencies
        for widget in self.currencies_frame.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.currencies_frame,
            text="Currencies",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        currencies = self.reports_parser.get_currencies()
        for name, amount in currencies.items():
            if name == "Gold":
                continue  # Already shown in header
            row = ctk.CTkFrame(self.currencies_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=1)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=11), anchor="w", width=140).pack(side="left")
            ctk.CTkLabel(row, text=f"{amount:,}", font=ctk.CTkFont(size=11), anchor="e").pack(side="right")

        # Update skills section
        for widget in self.skills_content.winfo_children():
            widget.destroy()

        arrow = "\u25bc" if self.section_expanded.get("skills", True) else "\u25b6"
        skills = self.reports_parser.get_skills()
        self.skills_header.configure(text=f"{arrow} Skills ({len(skills)})")

        if self.section_expanded.get("skills", True):
            # Show top 15 skills
            for skill in skills[:15]:
                row = ctk.CTkFrame(self.skills_content, fg_color="transparent", height=24)
                row.pack(fill="x", pady=1)
                row.pack_propagate(False)

                name_text = skill["name"]
                if skill["bonus"] > 0:
                    name_text += f" (+{skill['bonus']})"

                name_btn = ctk.CTkButton(
                    row,
                    text=name_text[:25] + "..." if len(name_text) > 25 else name_text,
                    width=180,
                    height=22,
                    anchor="w",
                    fg_color="transparent",
                    text_color=("gray10", "gray90"),
                    hover_color=("gray80", "gray30"),
                    font=ctk.CTkFont(size=11),
                    command=lambda s=skill: self._select_skill(s)
                )
                name_btn.pack(side="left")

                ctk.CTkLabel(
                    row,
                    text=f"Lv {skill['level']}",
                    font=ctk.CTkFont(size=11),
                    width=50,
                    anchor="e"
                ).pack(side="right", padx=(0, 5))

        # Update NPCs section
        for widget in self.npcs_content.winfo_children():
            widget.destroy()

        npcs = self.reports_parser.get_npc_relationships()
        arrow = "\u25bc" if self.section_expanded.get("npcs", True) else "\u25b6"
        self.npcs_header.configure(text=f"{arrow} NPCs ({len(npcs)})")

        if self.section_expanded.get("npcs", True):
            # Group NPCs by favor level
            npcs_by_favor = {}
            for npc in npcs:
                favor = npc["favor_display"]
                if favor not in npcs_by_favor:
                    npcs_by_favor[favor] = []
                npcs_by_favor[favor].append(npc)

            for favor in ["Soul Mates", "Like Family", "Best Friends", "Close Friends", "Friends", "Comfortable", "Tolerated"]:
                if favor not in npcs_by_favor:
                    continue

                # Favor level header
                ctk.CTkLabel(
                    self.npcs_content,
                    text=favor,
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=self._get_favor_color(favor)
                ).pack(anchor="w", padx=5, pady=(5, 2))

                for npc in npcs_by_favor[favor]:
                    row = ctk.CTkFrame(self.npcs_content, fg_color="transparent", height=22)
                    row.pack(fill="x", pady=1)
                    row.pack_propagate(False)

                    ctk.CTkLabel(
                        row,
                        text="  " + npc["display_name"],
                        font=ctk.CTkFont(size=11),
                        anchor="w"
                    ).pack(side="left", padx=(10, 0))

    def _get_favor_color(self, favor: str) -> str:
        """Get color for favor level."""
        colors = {
            "Soul Mates": "#E040FB",
            "Like Family": "#FF4081",
            "Best Friends": "#FF5722",
            "Close Friends": "#FF9800",
            "Friends": "#4CAF50",
            "Comfortable": "#8BC34A",
            "Tolerated": "#9E9E9E",
        }
        return colors.get(favor, "#FFFFFF")

    def _select_skill(self, skill: dict):
        """Handle skill selection."""
        self.selected_skill = skill
        # Could show skill details in right panel
        pass

    def _refresh_storage_tab(self):
        """Refresh the Storage tab content."""
        if not hasattr(self, 'storage_tree'):
            return

        # Clear existing items
        self.storage_tree.delete(*self.storage_tree.get_children())

        # Load storage data
        storage_data = self.reports_parser.load_storage()

        if not storage_data:
            self.storage_summary.configure(text="No storage data - export from game")
            return

        # Update vault dropdown
        vaults = ["All"] + self.reports_parser.get_vault_names()
        self.vault_dropdown.configure(values=vaults)

        # Get items to display
        search_query = self.storage_search_var.get().strip().lower()

        if search_query:
            items = self.reports_parser.search_items(search_query)
        elif self.selected_vault == "All":
            items = self.reports_parser.get_all_items()
        else:
            items_by_vault = self.reports_parser.get_items_by_vault()
            items = items_by_vault.get(self.selected_vault, [])

        # Update summary
        total_value = sum(i.get("Value", 0) * i.get("StackSize", 1) for i in items)
        self.storage_summary.configure(text=f"{len(items)} items - {total_value:,} gold")

        # Insert all items into treeview (Treeview handles large lists efficiently)
        for item in items:
            name = item.get("Name", "Unknown")
            stack = item.get("StackSize", 1)
            vault = item.get("StorageVault", "")
            rarity = item.get("Rarity", "Common").lower()

            # Truncate vault name for display
            vault_short = vault[:12] + ".." if len(vault) > 12 else vault

            self.storage_tree.insert(
                "", "end",
                values=(name, stack, vault_short),
                tags=(rarity,)
            )

        # Apply current sort order
        if self.storage_sort_column:
            self._apply_storage_sort()

    def _apply_storage_sort(self):
        """Apply current sort without toggling direction."""
        column = self.storage_sort_column
        ascending = self.storage_sort_state[column]

        # Get all items with their values
        items = []
        for item_id in self.storage_tree.get_children():
            values = self.storage_tree.item(item_id, "values")
            tags = self.storage_tree.item(item_id, "tags")
            items.append((item_id, values, tags))

        # Sort based on column
        col_index = {"name": 0, "qty": 1, "location": 2}[column]

        if column == "qty":
            items.sort(key=lambda x: int(x[1][col_index]), reverse=not ascending)
        else:
            items.sort(key=lambda x: x[1][col_index].lower(), reverse=not ascending)

        # Reorder items in treeview
        for idx, (item_id, values, tags) in enumerate(items):
            self.storage_tree.move(item_id, "", idx)

    def _get_rarity_color(self, rarity: str) -> str:
        """Get color for item rarity."""
        colors = {
            "Common": "#FFFFFF",
            "Uncommon": "#4CAF50",
            "Rare": "#2196F3",
            "Epic": "#9C27B0",
            "Legendary": "#FF9800",
        }
        return colors.get(rarity, "#FFFFFF")

    def _select_storage_item(self, item: dict):
        """Handle storage item selection."""
        self.selected_storage_item = item
        # Could show item details in right panel
        pass

    def _refresh_quests_tab(self):
        """Refresh the Quests tab content."""
        if not hasattr(self, 'quests_scroll'):
            return

        # Clear existing content
        for widget in self.quests_scroll.winfo_children():
            widget.destroy()

        # Load quest data
        active_quests = self.reports_parser.get_active_quest_ids()

        if not active_quests:
            self.quests_status.configure(text="No active quests")
            return

        # Load quest database (may take time on first load)
        quests_by_zone = self.reports_parser.get_quests_by_zone()

        if not quests_by_zone:
            self.quests_status.configure(text=f"{len(active_quests)} quests (loading details...)")

            # Try to fetch quest database in background
            def fetch_quests():
                self.reports_parser.load_quest_database()
                self.after(0, self._refresh_quests_tab)

            threading.Thread(target=fetch_quests, daemon=True).start()
            return

        total_quests = sum(len(q) for q in quests_by_zone.values())
        self.quests_status.configure(text=f"{total_quests} active quests")

        # Get all item names for matching
        all_items = self.reports_parser.get_all_item_names()

        # Display quests grouped by zone
        for zone in sorted(quests_by_zone.keys()):
            quests = quests_by_zone[zone]

            # Initialize zone expanded state
            if zone not in self.quest_zone_expanded:
                self.quest_zone_expanded[zone] = True

            # Zone header
            arrow = "\u25bc" if self.quest_zone_expanded[zone] else "\u25b6"
            zone_btn = ctk.CTkButton(
                self.quests_scroll,
                text=f"{arrow} {zone} ({len(quests)})",
                anchor="w",
                fg_color=("gray85", "gray25"),
                text_color=("gray10", "gray90"),
                hover_color=("gray75", "gray35"),
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda z=zone: self._toggle_quest_zone(z)
            )
            zone_btn.pack(fill="x", pady=(5, 2))

            if not self.quest_zone_expanded[zone]:
                continue

            # Display quests in this zone
            for quest in quests:
                quest_frame = ctk.CTkFrame(self.quests_scroll, fg_color="transparent")
                quest_frame.pack(fill="x", padx=(15, 5), pady=2)

                # Quest name
                quest_name = quest.get("name", quest.get("id", "Unknown"))
                name_text = quest_name[:35] + "..." if len(quest_name) > 35 else quest_name

                ctk.CTkLabel(
                    quest_frame,
                    text=name_text,
                    font=ctk.CTkFont(size=11),
                    anchor="w"
                ).pack(anchor="w")

                # Display objectives if available
                for obj in quest.get("objectives", [])[:3]:  # Show first 3 objectives
                    obj_frame = ctk.CTkFrame(quest_frame, fg_color="transparent")
                    obj_frame.pack(fill="x", padx=(10, 0))

                    # Status indicator
                    if obj.get("is_item"):
                        has_item = obj.get("has_item", False)
                        indicator = "\u2713" if has_item else "\u2717"
                        color = "#4CAF50" if has_item else "#F44336"
                    else:
                        indicator = "?"
                        color = "gray"

                    ctk.CTkLabel(
                        obj_frame,
                        text=indicator,
                        font=ctk.CTkFont(size=10),
                        text_color=color,
                        width=15
                    ).pack(side="left")

                    # Objective description (truncated)
                    desc = obj.get("description", "")
                    desc_text = desc[:40] + "..." if len(desc) > 40 else desc

                    ctk.CTkLabel(
                        obj_frame,
                        text=desc_text,
                        font=ctk.CTkFont(size=10),
                        text_color="gray",
                        anchor="w"
                    ).pack(side="left", fill="x")

    def _toggle_quest_zone(self, zone: str):
        """Toggle quest zone expanded state."""
        self.quest_zone_expanded[zone] = not self.quest_zone_expanded.get(zone, True)
        self._refresh_quests_tab()

    def _create_detail_panel(self, parent):
        """Create the right panel with stacked detail and options views."""
        self.right_frame = ctk.CTkFrame(parent)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 5), pady=5)

        # Configure grid - both panels will stack in same cell
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(0, weight=1)

        # Create ALL panels upfront, stacked in same grid cell
        self._create_loot_detail_view()
        self._create_options_view()
        self._create_stats_view()

        # Show detail panel on top initially
        self.detail_content.tkraise()

    def _create_loot_detail_view(self):
        """Create the loot detail view."""
        self.detail_content = ctk.CTkFrame(self.right_frame)
        self.detail_content.grid(row=0, column=0, sticky="nsew")

        # Header area
        self.detail_header = ctk.CTkFrame(self.detail_content, fg_color="transparent")
        self.detail_header.pack(fill="x", padx=10, pady=(10, 5))

        self.detail_name = ctk.CTkLabel(
            self.detail_header,
            text="Loot Details",
            font=ctk.CTkFont(size=16, weight="bold"),
            cursor="hand2"
        )
        self.detail_name.pack(anchor="w")
        self.detail_name.bind("<Button-1>", self._on_creature_name_click)
        self.detail_name.bind("<Enter>", lambda e: self.detail_name.configure(font=ctk.CTkFont(size=16, weight="bold", underline=True)))
        self.detail_name.bind("<Leave>", lambda e: self.detail_name.configure(font=ctk.CTkFont(size=16, weight="bold", underline=False)))

        # Clickable zone link
        self.zone_link = ctk.CTkLabel(
            self.detail_header,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#4CAF50",
            cursor="hand2"
        )
        self.zone_link.bind("<Button-1>", self._on_zone_click)
        self.zone_link.bind("<Enter>", lambda e: self.zone_link.configure(font=ctk.CTkFont(size=12, underline=True)))
        self.zone_link.bind("<Leave>", lambda e: self.zone_link.configure(font=ctk.CTkFont(size=12, underline=False)))

        # Info row with zone and kills
        self.detail_info_frame = ctk.CTkFrame(self.detail_header, fg_color="transparent")
        # Don't pack yet - will be shown when creature selected

        # Zone dropdown (for unknown zones)
        self.zone_dropdown = ctk.CTkOptionMenu(
            self.detail_info_frame,
            values=VALID_ZONES,
            width=120,
            height=24,
            font=ctk.CTkFont(size=11),
            command=self._on_zone_changed
        )

        # Initial placeholder label
        self.detail_info = ctk.CTkLabel(
            self.detail_header,
            text="Select a creature to view loot",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.detail_info.pack(anchor="w")

        # Tab view for Info and Wiki
        self.detail_tabs = ctk.CTkTabview(self.detail_content, height=300)
        self.detail_tabs.pack(fill="both", expand=True, padx=5, pady=5)

        # Info tab
        self.info_tab = self.detail_tabs.add("Info")

        # Scrollable content area for both loot and skinning
        self.detail_scroll = ctk.CTkScrollableFrame(self.info_tab)
        self.detail_scroll.pack(fill="both", expand=True)

        # Loot section container (will be populated dynamically)
        self.loot_section = ctk.CTkFrame(self.detail_scroll, fg_color="transparent")
        self.loot_section.pack(fill="x", pady=(0, 10))

        # Skinning section container (will be populated dynamically)
        self.skinning_section = ctk.CTkFrame(self.detail_scroll, fg_color="transparent")
        self.skinning_section.pack(fill="x")

        # Butchering section container (will be populated dynamically)
        self.butchering_section = ctk.CTkFrame(self.detail_scroll, fg_color="transparent")
        self.butchering_section.pack(fill="x")

        # Wiki tab
        self.wiki_tab = self.detail_tabs.add("Wiki")

        # Instructions label
        self.wiki_instruction = ctk.CTkLabel(
            self.wiki_tab,
            text="Paste the current wiki page content below, then click Sync to merge with our data.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.wiki_instruction.pack(fill="x", padx=5, pady=(5, 5))

        # Wiki syntax textbox (editable for paste)
        self.wiki_textbox = ctk.CTkTextbox(
            self.wiki_tab,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word"
        )
        self.wiki_textbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.wiki_textbox.insert("1.0", "Select a creature to view wiki syntax")
        self.wiki_textbox.bind("<KeyRelease>", self._on_wiki_text_changed)

        # Button frame for Sync
        wiki_button_frame = ctk.CTkFrame(self.wiki_tab, fg_color="transparent")
        wiki_button_frame.pack(fill="x", padx=5, pady=(0, 5))

        self.wiki_sync_button = ctk.CTkButton(
            wiki_button_frame,
            text="Sync",
            command=self._sync_wiki,
            width=100,
            height=32,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.wiki_sync_button.pack(side="left")
        self.wiki_sync_button.configure(state="disabled")

        self.wiki_open_button = ctk.CTkButton(
            wiki_button_frame,
            text="Open Wiki",
            command=self._open_wiki_page,
            width=100,
            height=32,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.wiki_open_button.pack(side="left", padx=(10, 0))

        self.wiki_status = ctk.CTkLabel(
            wiki_button_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#4CAF50",
            wraplength=250
        )
        self.wiki_status.pack(side="left", padx=10, fill="x", expand=True)

    def _create_stats_view(self):
        """Create the stats panel view."""
        self.stats_content = ctk.CTkFrame(self.right_frame)
        self.stats_content.grid(row=0, column=0, sticky="nsew")

        # Header (outside scrollable area)
        header = ctk.CTkLabel(
            self.stats_content,
            text="Tracking Statistics",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header.pack(anchor="w", padx=10, pady=10)

        # Scrollable container for stats content
        stats_scroll = ctk.CTkScrollableFrame(self.stats_content)
        stats_scroll.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # Stats container frame
        self.stats_frame = ctk.CTkFrame(stats_scroll, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=10)

        # Create stat labels (will be populated by _refresh_stats)
        self.stat_labels = {}

        stat_items = [
            ("total_creatures", "Total Creatures Tracked"),
            ("total_kills", "Total Kills"),
            ("unique_items", "Unique Items Found"),
            ("skinning_items", "Skinning Items Found"),
            ("butchering_items", "Butchering Items Found"),
            ("top_creature", "Most Killed Creature"),
            ("rarest_drop", "Rarest Drop")
        ]

        for key, label_text in stat_items:
            row = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(
                row,
                text=f"{label_text}:",
                font=ctk.CTkFont(size=12),
                width=180,
                anchor="w"
            ).pack(side="left")

            value_label = ctk.CTkLabel(
                row,
                text="-",
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
                wraplength=250 if key == "rarest_drop" else 0
            )
            value_label.pack(side="left", fill="x", expand=True)
            self.stat_labels[key] = value_label

        # Refresh button
        refresh_frame = ctk.CTkFrame(stats_scroll, fg_color="transparent")
        refresh_frame.pack(fill="x", padx=10, pady=(20, 10))

        ctk.CTkButton(
            refresh_frame,
            text="Refresh Stats",
            command=self._refresh_stats,
            width=120,
            height=32
        ).pack(side="left")

        # Initial refresh
        self._refresh_stats()

    def _refresh_stats(self):
        """Refresh the stats dashboard with current data."""
        if self.parser is None or not hasattr(self, 'stat_labels'):
            return

        with self._data_lock:
            stats = self.parser.get_aggregate_stats()

        # Update labels
        self.stat_labels["total_creatures"].configure(
            text=f"{stats['total_creatures']:,}"
        )
        self.stat_labels["total_kills"].configure(
            text=f"{stats['total_kills']:,}"
        )
        self.stat_labels["unique_items"].configure(
            text=f"{stats['unique_items']:,}"
        )
        self.stat_labels["skinning_items"].configure(
            text=f"{stats['skinning_items']:,}"
        )
        self.stat_labels["butchering_items"].configure(
            text=f"{stats['butchering_items']:,}"
        )

        # Top creature
        if stats['top_creature']:
            name, kills = stats['top_creature']
            self.stat_labels["top_creature"].configure(
                text=f"{name} ({kills:,} kills)"
            )
        else:
            self.stat_labels["top_creature"].configure(text="-")

        # Rarest drop
        if stats['rarest_drop']:
            item, creature, rate = stats['rarest_drop']
            self.stat_labels["rarest_drop"].configure(
                text=f"{item} ({rate:.1f}%) from {creature}"
            )
        else:
            self.stat_labels["rarest_drop"].configure(text="-")

    def _create_options_view(self):
        """Create the options view."""
        self.options_content = ctk.CTkFrame(self.right_frame)
        self.options_content.grid(row=0, column=0, sticky="nsew")

        # Header (outside scrollable area)
        header = ctk.CTkLabel(
            self.options_content,
            text="Options",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header.pack(anchor="w", padx=10, pady=10)

        # Scrollable container for all options
        self.options_scroll = ctk.CTkScrollableFrame(self.options_content)
        self.options_scroll.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # Chat log folder section
        folder_frame = ctk.CTkFrame(self.options_scroll)
        folder_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            folder_frame,
            text="Chat Log Folder",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            folder_frame,
            text="Typical location:\nC:\\Users\\YourName\\AppData\\LocalLow\\Elder Game\\Project Gorgon\\ChatLogs",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        # Folder path entry with browse button
        folder_input_frame = ctk.CTkFrame(folder_frame, fg_color="transparent")
        folder_input_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.folder_entry = ctk.CTkEntry(
            folder_input_frame,
            font=ctk.CTkFont(size=12),
            placeholder_text="C:\\path\\to\\ChatLogs"
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Insert current path
        if self.parser and self.parser.chatlog_dir:
            self.folder_entry.insert(0, str(self.parser.chatlog_dir))

        browse_button = ctk.CTkButton(
            folder_input_frame,
            text="Browse",
            command=self._browse_folder,
            width=80,
            height=28
        )
        browse_button.pack(side="right")

        # Storage location section (read-only info)
        storage_frame = ctk.CTkFrame(self.options_scroll)
        storage_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            storage_frame,
            text="Data Storage Location",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            storage_frame,
            text="Gorgon Tracker stores creature data and settings here:",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(anchor="w", padx=15, pady=(0, 5))

        storage_path = str(get_gorgon_tracker_data_dir())
        self.storage_path_label = ctk.CTkLabel(
            storage_frame,
            text=storage_path,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=("gray30", "gray70"),
            wraplength=400
        )
        self.storage_path_label.pack(anchor="w", padx=15, pady=(0, 15))

        # Auto-update section
        auto_frame = ctk.CTkFrame(self.options_scroll)
        auto_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            auto_frame,
            text="Auto-Update",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            auto_frame,
            text="Automatically run the parser at regular intervals",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        # Enable checkbox
        self.auto_update_var = ctk.BooleanVar(value=self.auto_update_enabled)
        self.auto_update_checkbox = ctk.CTkCheckBox(
            auto_frame,
            text="Enable auto-update",
            variable=self.auto_update_var,
            font=ctk.CTkFont(size=13)
        )
        self.auto_update_checkbox.pack(anchor="w", padx=15, pady=10)

        # Interval input
        interval_frame = ctk.CTkFrame(auto_frame, fg_color="transparent")
        interval_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            interval_frame,
            text="Update interval (seconds):",
            font=ctk.CTkFont(size=13)
        ).pack(side="left")

        self.interval_entry = ctk.CTkEntry(
            interval_frame,
            width=80,
            font=ctk.CTkFont(size=13)
        )
        self.interval_entry.pack(side="left", padx=10)
        self.interval_entry.insert(0, str(self.auto_update_interval))

        # Spacer
        ctk.CTkFrame(auto_frame, height=15, fg_color="transparent").pack()

        # Import section
        import_frame = ctk.CTkFrame(self.options_scroll)
        import_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            import_frame,
            text="Import Database",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            import_frame,
            text="Drag & drop a .gtdb file to merge with your data",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        # Drop zone
        self.drop_zone = ctk.CTkLabel(
            import_frame,
            text="Drop .gtdb file here",
            font=ctk.CTkFont(size=13),
            fg_color=("gray85", "gray25"),
            corner_radius=8,
            height=60
        )
        self.drop_zone.pack(fill="x", padx=15, pady=(5, 15))

        # Register drop zone for drag and drop
        self.drop_zone.drop_target_register(DND_FILES)
        self.drop_zone.dnd_bind('<<Drop>>', self._on_drop)
        self.drop_zone.dnd_bind('<<DragEnter>>', self._on_drag_enter)
        self.drop_zone.dnd_bind('<<DragLeave>>', self._on_drag_leave)

        # Import status
        self.import_status = ctk.CTkLabel(
            import_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#4CAF50"
        )
        self.import_status.pack(anchor="w", padx=15, pady=(0, 10))

        # Export Database section
        export_frame = ctk.CTkFrame(self.options_scroll)
        export_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            export_frame,
            text="Export Database",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            export_frame,
            text="Save your creature data to a shareable file",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        export_btn_frame = ctk.CTkFrame(export_frame, fg_color="transparent")
        export_btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.export_button = ctk.CTkButton(
            export_btn_frame,
            text="Export Database",
            command=self._export_database,
            width=130,
            height=32,
            font=ctk.CTkFont(size=13)
        )
        self.export_button.pack(side="left")

        # Data Management section
        data_frame = ctk.CTkFrame(self.options_scroll)
        data_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            data_frame,
            text="Data Management",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            data_frame,
            text="Clear all creature and loot data (cannot be undone)",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        clear_btn_frame = ctk.CTkFrame(data_frame, fg_color="transparent")
        clear_btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.clear_db_button = ctk.CTkButton(
            clear_btn_frame,
            text="Clear Database",
            command=self._clear_database,
            width=130,
            height=32,
            fg_color="#d32f2f",
            hover_color="#b71c1c",
            font=ctk.CTkFont(size=13)
        )
        self.clear_db_button.pack(side="left")

        self.clear_status = ctk.CTkLabel(
            clear_btn_frame,
            text="",
            font=ctk.CTkFont(size=11)
        )
        self.clear_status.pack(side="left", padx=10)

        # Save button
        save_frame = ctk.CTkFrame(self.options_scroll, fg_color="transparent")
        save_frame.pack(fill="x", padx=10, pady=15)

        self.save_button = ctk.CTkButton(
            save_frame,
            text="Save Settings",
            command=self._save_options,
            width=150,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.save_button.pack(side="left")

        # Status message
        self.save_status = ctk.CTkLabel(
            save_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#4CAF50"
        )
        self.save_status.pack(side="left", padx=15)

    def _toggle_options(self):
        """Toggle between options panel and detail panel."""
        if self.showing_options:
            self._show_detail_panel()
        else:
            self._show_options_panel()

    def _toggle_stats(self):
        """Toggle between stats panel and detail panel."""
        if self.showing_stats:
            self._show_detail_panel()
        else:
            self._show_stats_panel()

    def _show_detail_panel(self):
        """Show the loot detail panel."""
        self.detail_content.tkraise()
        self.options_button.configure(text="Options")
        self.stats_button.configure(text="Stats")
        self.showing_options = False
        self.showing_stats = False

    def _show_options_panel(self):
        """Show the options panel."""
        self.options_content.tkraise()
        self.options_button.configure(text="Back")
        self.stats_button.configure(text="Stats")
        self.showing_options = True
        self.showing_stats = False

    def _show_stats_panel(self):
        """Show the stats panel."""
        self._refresh_stats()
        self.stats_content.tkraise()
        self.stats_button.configure(text="Back")
        self.options_button.configure(text="Options")
        self.showing_stats = True
        self.showing_options = False

    def _save_options(self):
        """Save options and apply changes."""
        # Get values
        self.auto_update_enabled = self.auto_update_var.get()

        try:
            interval = int(self.interval_entry.get())
            if interval < 1:
                interval = 1
            elif interval > 3600:
                interval = 3600
            self.auto_update_interval = interval
        except ValueError:
            self.interval_entry.delete(0, "end")
            self.interval_entry.insert(0, str(self.auto_update_interval))

        # Save to file
        self._save_settings()

        # Apply auto-update setting
        if self.auto_update_enabled:
            self._start_auto_update()
        else:
            self._stop_auto_update()

        # Save folder path
        new_folder = self.folder_entry.get().strip()
        if new_folder and Path(new_folder).exists():
            self._update_chatlog_folder(new_folder)

        # Show confirmation
        self.save_status.configure(text="Settings saved!")
        self.after(2000, lambda: self.save_status.configure(text=""))

    def _clear_database(self):
        """Clear all creature data after confirmation."""
        from tkinter import messagebox

        result = messagebox.askyesno(
            "Clear Database",
            "Are you sure you want to delete all creature and loot data?\n\nThis cannot be undone.",
            icon="warning"
        )

        if result:
            try:
                # Clear creature data
                self.parser.creature_data = {}
                self.parser._save_creature_data()

                # Clear processed logs state so we can re-parse
                self.parser.processed_state = {"files": {}}
                self.parser._save_state()

                # Reset last update timestamp
                self.last_update_timestamp = None
                self._save_settings()
                self._update_last_update_label()

                # Refresh UI
                self._refresh_creature_list()
                self._refresh_stats()

                # Clear detail view
                self.detail_name.configure(text="Loot Details")
                self.detail_info.configure(text="Select a creature to view loot")
                for widget in self.loot_section.winfo_children():
                    widget.destroy()
                for widget in self.skinning_section.winfo_children():
                    widget.destroy()
                for widget in self.butchering_section.winfo_children():
                    widget.destroy()
                self.wiki_textbox.configure(state="normal")
                self.wiki_textbox.delete("1.0", "end")
                self.wiki_textbox.insert("1.0", "Select a creature to view wiki syntax")

                self.clear_status.configure(text="Database cleared!", text_color="#4CAF50")
                self._log_message("Database cleared")
                self.after(3000, lambda: self.clear_status.configure(text=""))

            except Exception as e:
                self.clear_status.configure(text=f"Error: {str(e)}", text_color="#F44336")
                self.after(3000, lambda: self.clear_status.configure(text=""))

    def _browse_folder(self):
        """Open folder browser dialog."""
        from tkinter import filedialog

        folder = filedialog.askdirectory(
            title="Select ChatLogs Folder",
            initialdir=self.folder_entry.get() or None
        )

        if folder:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, folder)

    def _update_chatlog_folder(self, new_folder: str):
        """Update the chat log folder and reinitialize parser."""
        # Update .env file
        env_path = Path(".env")
        env_content = f"USER_CHATLOG_FILE_LOCATION={new_folder}\n"

        try:
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(env_content)

            # Reinitialize parser with new folder (storage_dir automatically set)
            self.parser = LootParser(
                chatlog_dir=new_folder,
                output_dir="CreaturePages"
            )

            self._refresh_creature_list()
            self._log_message(f"Updated chat log folder to: {new_folder}")

        except Exception as e:
            self._log_message(f"Failed to update folder: {str(e)}")

    def _export_database(self):
        """Export creature data to a .gtdb file."""
        if self.parser is None:
            return

        from tkinter import filedialog

        # Generate default filename with date
        date_str = datetime.now().strftime("%Y-%m-%d")
        default_name = f"GorgonTrackerDatabase_{date_str}.gtdb"

        file_path = filedialog.asksaveasfilename(
            defaultextension=".gtdb",
            filetypes=[("Gorgon Tracker Database", "*.gtdb"), ("All files", "*.*")],
            initialfile=default_name,
            title="Export Database"
        )

        if not file_path:
            return

        try:
            export_data = {
                "version": "1.0",
                "exported": datetime.now().isoformat(),
                "creatures": self.parser.creature_data
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, sort_keys=True)

            self._log_message(f"Exported database to {Path(file_path).name}")

        except Exception as e:
            self._log_message(f"Export failed: {str(e)}")

    def _on_drag_enter(self, event):
        """Handle drag enter event."""
        self.drop_zone.configure(fg_color=("gray75", "gray35"))
        return event.action

    def _on_drag_leave(self, event):
        """Handle drag leave event."""
        self.drop_zone.configure(fg_color=("gray85", "gray25"))
        return event.action

    def _on_drop(self, event):
        """Handle file drop event."""
        self.drop_zone.configure(fg_color=("gray85", "gray25"))

        # Parse dropped file path (may have curly braces on Windows)
        file_path = event.data.strip()
        if file_path.startswith('{') and file_path.endswith('}'):
            file_path = file_path[1:-1]

        if not file_path.lower().endswith('.gtdb'):
            self.import_status.configure(text="Error: Not a .gtdb file", text_color="#F44336")
            self.after(3000, lambda: self.import_status.configure(text=""))
            return

        self._import_database(file_path)
        return event.action

    def _import_database(self, file_path: str):
        """Import and merge a .gtdb file with local data."""
        if self.parser is None:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            creatures = import_data.get("creatures", {})
            if not creatures:
                self.import_status.configure(text="Error: No creature data found", text_color="#F44336")
                self.after(3000, lambda: self.import_status.configure(text=""))
                return

            # Merge with existing data
            new_creatures = 0
            updated_creatures = 0

            for creature_name, creature_data in creatures.items():
                if creature_name not in self.parser.creature_data:
                    # New creature - add it
                    self.parser.creature_data[creature_name] = creature_data
                    new_creatures += 1
                else:
                    # Existing creature - merge data
                    existing = self.parser.creature_data[creature_name]

                    # Add kills
                    existing["kills"] = existing.get("kills", 0) + creature_data.get("kills", 0)

                    # Merge zones
                    existing_zones = set(existing.get("zones", []))
                    new_zones = set(creature_data.get("zones", []))
                    existing["zones"] = sorted(existing_zones | new_zones)

                    # Merge items
                    existing_items = existing.get("items", {})
                    for item_name, item_data in creature_data.get("items", {}).items():
                        if item_name not in existing_items:
                            existing_items[item_name] = item_data
                        else:
                            # Add counts together
                            existing_items[item_name]["count"] = (
                                existing_items[item_name].get("count", 0) +
                                item_data.get("count", 0)
                            )
                            # Update last_seen if newer
                            if item_data.get("last_seen", "") > existing_items[item_name].get("last_seen", ""):
                                existing_items[item_name]["last_seen"] = item_data["last_seen"]

                    existing["items"] = existing_items
                    updated_creatures += 1

            # Save merged data
            self.parser._save_creature_data()

            # Refresh UI
            self._refresh_creature_list()
            self._refresh_stats()

            msg = f"Imported: {new_creatures} new, {updated_creatures} updated"
            self.import_status.configure(text=msg, text_color="#4CAF50")
            self._log_message(f"Imported {Path(file_path).name}: {new_creatures} new creatures, {updated_creatures} updated")
            self.after(5000, lambda: self.import_status.configure(text=""))

        except json.JSONDecodeError:
            self.import_status.configure(text="Error: Invalid file format", text_color="#F44336")
            self.after(3000, lambda: self.import_status.configure(text=""))
        except Exception as e:
            self.import_status.configure(text=f"Error: {str(e)}", text_color="#F44336")
            self.after(3000, lambda: self.import_status.configure(text=""))

    def _start_auto_update(self):
        """Start the auto-update timer."""
        self._stop_auto_update()  # Cancel any existing timer

        def auto_run():
            if self.auto_update_enabled and self.parser:
                # Only run if not already parsing
                if self.update_button.cget("state") != "disabled":
                    self._run_update()
                # Schedule next run
                self.auto_update_job = self.after(
                    self.auto_update_interval * 1000,
                    auto_run
                )

        # Start the timer
        self.auto_update_job = self.after(self.auto_update_interval * 1000, auto_run)
        self._log_message(f"Auto-update enabled ({self.auto_update_interval}s interval)")
        self._update_auto_status()

    def _stop_auto_update(self):
        """Stop the auto-update timer."""
        if self.auto_update_job:
            self.after_cancel(self.auto_update_job)
            self.auto_update_job = None
            self._log_message("Auto-update disabled")
        self._update_auto_status()

    def _update_auto_status(self):
        """Update status label to show auto-update state."""
        if self.auto_update_enabled and self.auto_update_job:
            self.status_label.configure(
                text=f"Ready (auto: {self.auto_update_interval}s)",
                text_color="#4CAF50"
            )
        else:
            self.status_label.configure(text="Ready", text_color=("gray10", "gray90"))

    def _format_last_update(self) -> str:
        """Format the last update timestamp for display."""
        with self._data_lock:
            timestamp = self.last_update_timestamp
        if not timestamp:
            return "Last update: Never"
        try:
            dt = datetime.fromisoformat(timestamp)
            return f"Last update: {dt.strftime('%Y-%m-%d %H:%M')}"
        except (ValueError, TypeError):
            return "Last update: Never"

    def _format_current_zone(self) -> str:
        """Format the current zone for display."""
        if self.parser:
            zone = self.parser.get_current_zone()
            if zone:
                return f"Zone: {zone}"
        return "Zone: Unknown"

    def _update_last_update_label(self):
        """Update the last update label with current timestamp."""
        if hasattr(self, 'last_update_label'):
            self.last_update_label.configure(text=self._format_last_update())

    def _update_zone_label(self):
        """Update the zone label with current zone."""
        if hasattr(self, 'zone_label'):
            self.zone_label.configure(text=self._format_current_zone())

    def _create_status_log(self):
        """Create the status log at the bottom."""
        log_frame = ctk.CTkFrame(self, height=150)
        log_frame.pack(fill="x", padx=10, pady=(0, 10))
        log_frame.pack_propagate(False)  # Prevent resizing based on content

        ctk.CTkLabel(
            log_frame,
            text="Status Log",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=10, pady=(5, 0))

        self.status_log = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.status_log.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        self.status_log.configure(state="disabled")

    def _log_message(self, message: str):
        """Add a message to the status log (thread-safe)."""
        def update():
            self.status_log.configure(state="normal")
            self.status_log.insert("end", message + "\n")
            self.status_log.see("end")
            self.status_log.configure(state="disabled")

        self.after(0, update)

    def _run_update(self):
        """Run incremental update in a background thread."""
        if self.parser is None:
            return

        # Disable buttons during parsing
        self.update_button.configure(state="disabled", text="Updating...")
        self.full_rescan_button.configure(state="disabled")
        self.status_label.configure(text="Processing...")

        def parse_thread():
            try:
                self._log_message("Starting incremental update...")

                # Process new log entries only (with lock to protect shared data)
                with self._data_lock:
                    results = self.parser.process_all_logs(callback=self._log_message)

                # Summarize results
                if results:
                    self._log_message(f"Found new loot for {len(results)} creature(s)")
                else:
                    self._log_message("No new entries found")

                self._log_message("Done!")

                # Update timestamp on success (scheduled on main thread)
                def update_timestamp():
                    with self._data_lock:
                        self.last_update_timestamp = datetime.now().isoformat()
                    self._save_settings()
                    self._update_last_update_label()
                self.after(0, update_timestamp)

            except Exception as e:
                self._log_message(f"Error: {str(e)}")

            finally:
                # Re-enable buttons and refresh list
                def finish():
                    self.update_button.configure(state="normal", text="Update")
                    self.full_rescan_button.configure(state="normal")
                    self._update_auto_status()
                    self._update_zone_label()
                    self._refresh_creature_list()
                    self._refresh_stats()

                self.after(0, finish)

        thread = threading.Thread(target=parse_thread, daemon=True)
        thread.start()

    def _run_full_rescan(self):
        """Run full rescan in a background thread."""
        if self.parser is None:
            return

        # Disable buttons during parsing
        self.update_button.configure(state="disabled")
        self.full_rescan_button.configure(state="disabled", text="Rescanning...")
        self.status_label.configure(text="Processing...")

        def rescan_thread():
            try:
                self._log_message("Starting full rescan...")

                # Full rescan to re-read all chat logs (with lock to protect shared data)
                with self._data_lock:
                    rescan_stats = self.parser.full_rescan(callback=self._log_message)

                # Summarize results
                new_creatures = rescan_stats.get("new_creatures", 0)
                new_items = rescan_stats.get("new_items", 0)
                if new_creatures > 0 or new_items > 0:
                    self._log_message(f"Found {new_creatures} new creatures, {new_items} new items")
                else:
                    self._log_message("No new data found")

                self._log_message("Done!")

                # Update timestamp on success (scheduled on main thread)
                def update_timestamp():
                    with self._data_lock:
                        self.last_update_timestamp = datetime.now().isoformat()
                    self._save_settings()
                    self._update_last_update_label()
                self.after(0, update_timestamp)

            except Exception as e:
                self._log_message(f"Error: {str(e)}")

            finally:
                # Re-enable buttons and refresh list
                def finish():
                    self.update_button.configure(state="normal")
                    self.full_rescan_button.configure(state="normal", text="Full Rescan")
                    self._update_auto_status()
                    self._update_zone_label()
                    self._refresh_creature_list()
                    self._refresh_stats()

                self.after(0, finish)

        thread = threading.Thread(target=rescan_thread, daemon=True)
        thread.start()

    def _refresh_creature_list(self):
        """Refresh the creature list from parser data with collapsible zone sections."""
        if self.parser is None:
            return

        # Clear existing widgets
        for widget in self.creature_scroll.winfo_children():
            widget.destroy()
        self.creature_buttons.clear()
        self.creature_zone_labels.clear()

        # Initialize zone_expanded if not exists
        if not hasattr(self, 'zone_expanded'):
            self.zone_expanded = {}

        # Group creatures by zone (with lock to protect shared data)
        creatures_by_zone = {}
        with self._data_lock:
            for creature, data in self.parser.creature_data.items():
                zones = data.get("zones", ["Unknown"])
                zone = zones[0] if zones else "Unknown"
                if zone not in creatures_by_zone:
                    creatures_by_zone[zone] = []
                # Copy the data we need to avoid holding lock too long
                creatures_by_zone[zone].append((creature, {"kills": data.get("kills", 0)}))

        # Apply search filter
        creatures_by_zone = self._filter_creatures(creatures_by_zone)

        # Sort zones alphabetically, sort creatures within each zone by kills
        for zone in sorted(creatures_by_zone.keys()):
            creatures = sorted(
                creatures_by_zone[zone],
                key=lambda x: x[1].get("kills", 0),
                reverse=True
            )

            # Default to expanded
            if zone not in self.zone_expanded:
                self.zone_expanded[zone] = True

            # Create zone header
            header_frame = ctk.CTkFrame(self.creature_scroll, fg_color="transparent", height=28)
            header_frame.pack(fill="x", pady=(4, 1))
            header_frame.pack_propagate(False)

            arrow = "▼" if self.zone_expanded[zone] else "▶"
            header_btn = ctk.CTkButton(
                header_frame,
                text=f"{arrow} {zone} ({len(creatures)})",
                width=280,
                height=24,
                anchor="w",
                fg_color=("gray85", "gray25"),
                text_color=("gray10", "gray90"),
                hover_color=("gray75", "gray35"),
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda z=zone: self._toggle_zone(z)
            )
            header_btn.pack(side="left")

            # Create creature rows (only if expanded)
            if self.zone_expanded[zone]:
                for creature_name, data in creatures:
                    kills = data.get("kills", 0)

                    row = ctk.CTkFrame(self.creature_scroll, fg_color="transparent", height=30)
                    row.pack(fill="x", pady=1)
                    row.pack_propagate(False)

                    # Indent for creatures under zone header
                    ctk.CTkLabel(row, text="", width=15).pack(side="left")

                    # Clickable button for creature name
                    name_btn = ctk.CTkButton(
                        row,
                        text=creature_name[:22] + "..." if len(creature_name) > 22 else creature_name,
                        width=205,
                        height=26,
                        anchor="w",
                        fg_color="transparent",
                        text_color=("gray10", "gray90"),
                        hover_color=("gray80", "gray30"),
                        command=lambda c=creature_name: self._select_creature(c)
                    )
                    name_btn.pack(side="left", padx=(0, 5))
                    self.creature_buttons[creature_name] = name_btn

                    ctk.CTkLabel(
                        row,
                        text=str(kills),
                        width=50,
                        anchor="center",
                        font=ctk.CTkFont(size=12)
                    ).pack(side="left")

    def _toggle_zone(self, zone: str):
        """Toggle zone section expanded/collapsed state."""
        self.zone_expanded[zone] = not self.zone_expanded.get(zone, True)
        self._refresh_creature_list()

    def _clear_search(self):
        """Clear the search box."""
        self.search_var.set("")

    def _on_search_changed(self, *args):
        """Handle search text changes."""
        self._refresh_creature_list()

    def _filter_creatures(self, creatures_by_zone: dict) -> dict:
        """
        Filter creatures by search term.
        Matches creature names and item names (case-insensitive).

        Args:
            creatures_by_zone: Dict of zone -> list of (creature_name, data) tuples

        Returns:
            Filtered dict with same structure
        """
        search_term = self.search_var.get().strip().lower()
        if not search_term:
            return creatures_by_zone

        filtered = {}
        with self._data_lock:
            for zone, creatures in creatures_by_zone.items():
                matching = []
                for creature_name, data in creatures:
                    # Check creature name
                    if search_term in creature_name.lower():
                        matching.append((creature_name, data))
                        continue

                    # Check item names for this creature
                    creature_data = self.parser.creature_data.get(creature_name, {})
                    items = creature_data.get("items", {})
                    skinning = creature_data.get("skinning", {})
                    butchering = creature_data.get("butchering", {})

                    item_match = any(search_term in item.lower() for item in items.keys())
                    skinning_match = any(search_term in item.lower() for item in skinning.keys())
                    butchering_match = any(search_term in item.lower() for item in butchering.keys())

                    if item_match or skinning_match or butchering_match:
                        matching.append((creature_name, data))

                if matching:
                    filtered[zone] = matching

        return filtered

    def _select_creature(self, creature_name: str):
        """Select a creature and display its loot details."""
        if self.parser is None:
            return

        # Switch to detail view if showing options or stats
        if self.showing_options or self.showing_stats:
            self._show_detail_panel()

        # Update button highlights
        for name, btn in self.creature_buttons.items():
            if name == creature_name:
                btn.configure(fg_color=("gray75", "gray35"))
            else:
                btn.configure(fg_color="transparent")

        self.selected_creature = creature_name

        # Get creature stats (with lock to protect shared data)
        with self._data_lock:
            stats = self.parser.get_creature_stats(creature_name)
        if not stats:
            return

        # Update header
        self.detail_name.configure(text=creature_name)

        # Clear and rebuild the info frame
        for widget in self.detail_info_frame.winfo_children():
            widget.pack_forget()

        # Build zone display
        if stats["zones"]:
            # Zone is known - show clickable zone link and kills separately
            zone_name = stats["zones"][0]  # Primary zone
            self.zone_link.configure(text=f"Zone: {zone_name}")
            self.zone_link.pack(anchor="w")
            self.detail_info.configure(text=f"Kills: {stats['kills']}", text_color=("gray30", "gray70"))
            self.detail_info.pack(anchor="w")
            self.detail_info_frame.pack_forget()
        else:
            self.zone_link.pack_forget()
            # Zone is unknown - show dropdown
            self.detail_info.pack_forget()
            self.detail_info_frame.pack(anchor="w", pady=(5, 0))

            zone_prefix = ctk.CTkLabel(
                self.detail_info_frame,
                text="Zone: ",
                font=ctk.CTkFont(size=12),
                text_color=("gray30", "gray70")
            )
            zone_prefix.pack(side="left")

            self.zone_dropdown.set("Unknown")
            self.zone_dropdown.pack(side="left")

            kills_label = ctk.CTkLabel(
                self.detail_info_frame,
                text=f"  |  Kills: {stats['kills']}",
                font=ctk.CTkFont(size=12),
                text_color=("gray30", "gray70")
            )
            kills_label.pack(side="left")

        # Clear sections
        for widget in self.loot_section.winfo_children():
            widget.destroy()
        for widget in self.skinning_section.winfo_children():
            widget.destroy()
        for widget in self.butchering_section.winfo_children():
            widget.destroy()

        # Populate loot section
        self._populate_item_section(
            self.loot_section,
            "Loot Drops",
            stats["items"]
        )

        # Populate skinning section
        self._populate_item_section(
            self.skinning_section,
            "Skinning",
            stats.get("skinning", {})
        )

        # Populate butchering section
        self._populate_item_section(
            self.butchering_section,
            "Butchering",
            stats.get("butchering", {})
        )

        # Clear wiki tab for user input
        self._clear_wiki_for_input()

    def _on_zone_changed(self, zone: str):
        """Handle zone selection from dropdown."""
        if not self.selected_creature or not self.parser or zone == "Unknown":
            return

        # Update creature's zone in the data
        if self.selected_creature in self.parser.creature_data:
            creature_data = self.parser.creature_data[self.selected_creature]
            if zone not in creature_data.get("zones", []):
                if "zones" not in creature_data:
                    creature_data["zones"] = []
                creature_data["zones"].append(zone)
                creature_data["zones"].sort()

            # Also update all items that have no zone to use this zone
            items = creature_data.get("items", {})
            for item_name, item_data in items.items():
                if not item_data.get("zones"):
                    item_data["zones"] = [zone]

            # Save the data
            self.parser._save_creature_data()

            # Update the creature list zone label
            if self.selected_creature in self.creature_zone_labels:
                self.creature_zone_labels[self.selected_creature].configure(text=zone[:12])

            # Refresh the detail view to show zone as text
            self._select_creature(self.selected_creature)

            self._log_message(f"Set zone for {self.selected_creature} to {zone}")

    def _clear_wiki_for_input(self):
        """Clear wiki textbox and show placeholder for user input."""
        self.wiki_textbox.configure(state="normal")
        self.wiki_textbox.delete("1.0", "end")
        self.wiki_status.configure(text="")
        self.wiki_sync_button.configure(state="disabled")

    def _update_wiki_syntax(self, creature_name: str, stats: dict):
        """Update the wiki syntax textbox with zone-aware output."""
        # Use the new zone-aware generator from the parser
        wiki_text = self.parser.generate_wiki_syntax_with_zones(creature_name)

        # Add metadata comment at top
        header = f"<!-- {creature_name} - Loot Data -->\n"
        header += f"<!-- Kills: {stats['kills']} -->\n\n"

        # Update textbox
        self.wiki_textbox.configure(state="normal")
        self.wiki_textbox.delete("1.0", "end")
        self.wiki_textbox.insert("1.0", header + wiki_text)
        # Keep editable for paste/copy

    def _open_wiki_page(self):
        """Open the wiki page for the selected creature."""
        if not self.selected_creature:
            return

        wiki_name = self.selected_creature.replace(' ', '_')
        url = f"https://wiki.projectgorgon.com/wiki/{wiki_name}"
        webbrowser.open(url)

    def _on_creature_name_click(self, event=None):
        """Open wiki page for selected creature."""
        if self.selected_creature:
            wiki_name = self.selected_creature.replace(' ', '_')
            webbrowser.open(f"https://wiki.projectgorgon.com/wiki/{wiki_name}")

    def _on_zone_click(self, event=None):
        """Open wiki page for current zone."""
        if self.selected_creature:
            stats = self.parser.get_creature_stats(self.selected_creature)
            if stats and stats["zones"]:
                zone_name = stats["zones"][0].replace(' ', '_')
                webbrowser.open(f"https://wiki.projectgorgon.com/wiki/{zone_name}")

    def _on_item_double_click(self, event, tree):
        """Open wiki page for double-clicked item."""
        item_id = tree.identify_row(event.y)
        if item_id:
            values = tree.item(item_id, 'values')
            if values:
                item_name = values[0].replace(' ', '_')
                webbrowser.open(f"https://wiki.projectgorgon.com/wiki/{item_name}")

    def _on_wiki_text_changed(self, event=None):
        """Analyze pasted wiki content and show status."""
        if not self.selected_creature or not self.parser:
            self.wiki_sync_button.configure(state="disabled")
            return

        wiki_text = self.wiki_textbox.get("1.0", "end-1c").strip()

        # No content - disable sync
        if not wiki_text or wiki_text == "Select a creature to view wiki syntax":
            self.wiki_status.configure(text="")
            self.wiki_sync_button.configure(state="disabled")
            return

        # Extract creature name from wiki content
        wiki_creature = self.parser.extract_creature_name_from_wiki(wiki_text)

        # Check if creature name matches
        if wiki_creature and wiki_creature != self.selected_creature:
            self.wiki_status.configure(
                text=f'Wrong creature! You entered "{wiki_creature}". Expected "{self.selected_creature}".',
                text_color="#F44336"  # Red
            )
            self.wiki_sync_button.configure(state="disabled")
            return

        # Parse wiki items
        wiki_items = self.parser.parse_wiki_loot(wiki_text)

        # No valid loot items found - disable sync
        if not wiki_items:
            self.wiki_status.configure(
                text="No loot items found in wiki content",
                text_color="#FF9800"  # Orange
            )
            self.wiki_sync_button.configure(state="disabled")
            return

        # Valid content - enable sync button
        self.wiki_sync_button.configure(state="normal")

        # Get our items for comparison
        creature_data = self.parser.creature_data.get(self.selected_creature, {})
        our_items = creature_data.get("items", {})
        our_item_names = set(our_items.keys())

        # Flatten wiki items to set of names
        wiki_item_names = set()
        for items in wiki_items.values():
            wiki_item_names.update(items)

        # Find items we have that wiki doesn't
        items_to_add = our_item_names - wiki_item_names
        items_to_add = {name for name in items_to_add
                        if not our_items.get(name, {}).get("wiki_only", False)}

        if items_to_add:
            self.wiki_status.configure(
                text=f"Wiki is missing {len(items_to_add)} item(s) from your data",
                text_color="#FF9800"  # Orange
            )
        else:
            self.wiki_status.configure(
                text="Wiki content looks up to date",
                text_color="#4CAF50"  # Green
            )

    def _sync_wiki(self):
        """Sync pasted wiki content with our database."""
        if self.parser is None or self.selected_creature is None:
            self.wiki_status.configure(text="Select a creature first", text_color="#F44336")
            self.after(3000, lambda: self.wiki_status.configure(text=""))
            return

        # Get the wiki text from the textbox
        wiki_text = self.wiki_textbox.get("1.0", "end-1c")

        if not wiki_text.strip():
            self.wiki_status.configure(text="No content to sync", text_color="#F44336")
            self.after(3000, lambda: self.wiki_status.configure(text=""))
            return

        # Parse the wiki content
        wiki_items = self.parser.parse_wiki_loot(wiki_text)

        if not wiki_items:
            self.wiki_status.configure(text="No loot items found in wiki content", text_color="#FF9800")
            self.after(3000, lambda: self.wiki_status.configure(text=""))
            return

        # Merge with our database
        merge_stats = self.parser.merge_wiki_items(self.selected_creature, wiki_items)

        # Insert our loot data into the wiki content (preserving other sections)
        updated_wiki = self.parser.insert_loot_into_wiki(self.selected_creature, wiki_text)

        # Update the textbox with merged content
        self.wiki_textbox.configure(state="normal")
        self.wiki_textbox.delete("1.0", "end")
        self.wiki_textbox.insert("1.0", updated_wiki)

        # Refresh the info tab to show new items
        self._refresh_loot_display()
        self._refresh_stats()

        # Show status - count items we added to the wiki
        creature_data = self.parser.creature_data.get(self.selected_creature, {})
        our_items = creature_data.get("items", {})
        our_item_names = set(our_items.keys())

        # Flatten wiki items to get what wiki already had
        wiki_item_names = set()
        for items in wiki_items.values():
            wiki_item_names.update(items)

        # Items we added to wiki = our items minus wiki items (excluding wiki_only)
        items_added_to_wiki = {name for name in (our_item_names - wiki_item_names)
                               if not our_items.get(name, {}).get("wiki_only", False)}

        if items_added_to_wiki:
            self.wiki_status.configure(
                text=f"Synced! {len(items_added_to_wiki)} items added",
                text_color="#4CAF50"
            )
            self._log_message(f"Wiki sync for {self.selected_creature}: +{len(items_added_to_wiki)} items added to wiki")
        else:
            self.wiki_status.configure(
                text="Synced! No new items",
                text_color="#4CAF50"
            )

        self.after(5000, lambda: self.wiki_status.configure(text=""))

    def _refresh_loot_display(self):
        """Refresh the loot display for the currently selected creature."""
        if self.selected_creature is None:
            return

        stats = self.parser.get_creature_stats(self.selected_creature)
        if not stats:
            return

        # Clear and repopulate sections
        for widget in self.loot_section.winfo_children():
            widget.destroy()
        for widget in self.skinning_section.winfo_children():
            widget.destroy()
        for widget in self.butchering_section.winfo_children():
            widget.destroy()

        self._populate_item_section(
            self.loot_section,
            "Loot Drops",
            stats["items"]
        )

        self._populate_item_section(
            self.skinning_section,
            "Skinning",
            stats.get("skinning", {})
        )

        self._populate_item_section(
            self.butchering_section,
            "Butchering",
            stats.get("butchering", {})
        )

    def _populate_item_section(self, parent, title: str, items: dict):
        """Populate a section with item data using a resizable Treeview."""
        if not items:
            return

        # Section header
        ctk.CTkLabel(
            parent,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=5, pady=(5, 5))

        # Create frame for treeview
        tree_frame = ctk.CTkFrame(parent, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=5, pady=(0, 10))

        # Create Treeview with columns - no height limit, let outer scroll handle it
        columns = ("item", "count", "rate")
        tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="Dark.Treeview",
            height=len(items)  # Show all items, outer scrollframe handles scrolling
        )

        # Configure columns
        tree.heading("item", text="Item", anchor="w")
        tree.heading("count", text="Count", anchor="center")
        tree.heading("rate", text="Rate", anchor="center")

        tree.column("item", width=180, minwidth=100, anchor="w")
        tree.column("count", width=60, minwidth=45, anchor="center")
        tree.column("rate", width=70, minwidth=50, anchor="center")

        # Sort items: wiki_only items at the end, then by drop rate (descending)
        sorted_items = sorted(
            items.items(),
            key=lambda x: (x[1].get("wiki_only", False), -x[1]["drop_rate"])
        )

        # Configure tags for rate colors
        tree.tag_configure("rate_green", foreground="#4CAF50")
        tree.tag_configure("rate_light_green", foreground="#8BC34A")
        tree.tag_configure("rate_yellow", foreground="#FFC107")
        tree.tag_configure("rate_orange", foreground="#FF9800")
        tree.tag_configure("rate_red", foreground="#F44336")
        tree.tag_configure("wiki_only", foreground="#9E9E9E")  # Gray for wiki-only items

        # Configure hover versions with underline
        tree.tag_configure("rate_green_hover", foreground="#4CAF50", font=("TkDefaultFont", 10, "underline"))
        tree.tag_configure("rate_light_green_hover", foreground="#8BC34A", font=("TkDefaultFont", 10, "underline"))
        tree.tag_configure("rate_yellow_hover", foreground="#FFC107", font=("TkDefaultFont", 10, "underline"))
        tree.tag_configure("rate_orange_hover", foreground="#FF9800", font=("TkDefaultFont", 10, "underline"))
        tree.tag_configure("rate_red_hover", foreground="#F44336", font=("TkDefaultFont", 10, "underline"))
        tree.tag_configure("wiki_only_hover", foreground="#9E9E9E", font=("TkDefaultFont", 10, "underline"))

        # Track currently hovered item for underline effect
        hovered_item = [None]  # Use list to allow mutation in nested function

        def on_tree_motion(event):
            item_id = tree.identify_row(event.y)
            if item_id == hovered_item[0]:
                return  # No change

            # Remove underline from previously hovered item
            if hovered_item[0]:
                old_tags = tree.item(hovered_item[0], "tags")
                if old_tags:
                    old_tag = old_tags[0]
                    if old_tag.endswith("_hover"):
                        base_tag = old_tag[:-6]  # Remove "_hover" suffix
                        tree.item(hovered_item[0], tags=(base_tag,))

            # Add underline to new hovered item
            if item_id:
                tags = tree.item(item_id, "tags")
                if tags:
                    base_tag = tags[0]
                    if not base_tag.endswith("_hover"):
                        tree.item(item_id, tags=(base_tag + "_hover",))

            hovered_item[0] = item_id

        def on_tree_leave(event):
            # Remove underline from hovered item when mouse leaves
            if hovered_item[0]:
                old_tags = tree.item(hovered_item[0], "tags")
                if old_tags:
                    old_tag = old_tags[0]
                    if old_tag.endswith("_hover"):
                        base_tag = old_tag[:-6]
                        tree.item(hovered_item[0], tags=(base_tag,))
            hovered_item[0] = None

        # Insert items
        for item_name, item_data in sorted_items:
            rate = item_data["drop_rate"]
            wiki_only = item_data.get("wiki_only", False)

            if wiki_only:
                # Wiki-only items show "wiki" instead of rate
                rate_text = "wiki"
                tag = "wiki_only"
                display_name = item_name
            else:
                rate_text = f"{rate:.1f}%" if rate < 100 else "100%"
                display_name = item_name

                # Determine tag based on rate
                if rate >= 50:
                    tag = "rate_green"
                elif rate >= 20:
                    tag = "rate_light_green"
                elif rate >= 10:
                    tag = "rate_yellow"
                elif rate >= 5:
                    tag = "rate_orange"
                else:
                    tag = "rate_red"

            tree.insert("", "end", values=(display_name, item_data["count"], rate_text), tags=(tag,))

        # Pack treeview (no scrollbar - outer scrollframe handles scrolling)
        tree.pack(side="left", fill="both", expand=True)

        # Double-click to open wiki page for item
        tree.bind("<Double-1>", lambda e, t=tree: self._on_item_double_click(e, t))

        # Hover underline effect bindings
        tree.bind("<Motion>", on_tree_motion)
        tree.bind("<Leave>", on_tree_leave)
        tree.configure(cursor="hand2")

    def _get_rate_color(self, rate: float) -> str:
        """Get color based on drop rate."""
        if rate >= 50:
            return "#4CAF50"  # Green - common
        elif rate >= 20:
            return "#8BC34A"  # Light green
        elif rate >= 10:
            return "#FFC107"  # Yellow - uncommon
        elif rate >= 5:
            return "#FF9800"  # Orange
        else:
            return "#F44336"  # Red - rare


def main():
    """Main entry point for the GUI."""
    app = LootUploaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
