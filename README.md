# Gorgon Tracker

A desktop tool for **contributing loot data to the Project Gorgon Wiki**. Automatically parses your chat logs to track creature kills and drops, then generates wiki-formatted tables that integrate seamlessly with existing wiki pages.

## Main Feature: Wiki Synchronization

The wiki sync system helps you contribute loot data to the [Project Gorgon Wiki](https://wiki.projectgorgon.com/). It's not just an export tool - it's a full bidirectional sync workflow.

### How Wiki Sync Works

1. **Generate Wiki Table** - Select a creature and click "Copy Wiki" to get a wiki-formatted loot table with:
   - Zone-aware sections (items organized by zone)
   - Skinning and Butchering results in separate sections
   - Proper wiki syntax with item links

2. **Paste Existing Wiki Content** - If the creature already has a wiki page with loot data:
   - Click "Paste Wiki"
   - Paste the existing wiki table content
   - The parser extracts all currently-listed items

3. **Merge Data** - Click "Merge" to combine:
   - Your tracked drops are added to the wiki data
   - Existing wiki items are preserved
   - Duplicates are automatically handled

4. **Copy Updated Table** - The merged result is ready to paste back into the wiki, preserving the original formatting while adding your new discoveries.

### Wiki Sync Features

- **Content validation** - Verifies pasted content matches the selected creature
- **Zone sections** - Groups items by the zone where they dropped
- **Color-coded status** - Visual feedback during the sync process
- **Preserved formatting** - Respects existing wiki table structure

## Additional Features

### Loot Tracking
- **Automatic parsing** of chat logs to track creature kills and loot drops
- **Zone detection** - automatically detects which zone you're in
- **Loot attribution** - correctly attributes loot to the creature that dropped it
- **Skinning/Butchering separation** - distinguishes between regular loot, skinning results, and butchering results
- **Click to open wiki** - click on any creature or item name to open its wiki page

### Quest Tracking
- **Active quest display** with objectives and completion status
- **Item tracking** - shows how many quest items you have vs. how many you need
- **Color-coded status**:
  - Green checkmark - quest items ready (you have all required items)
  - Red X - missing items
  - Gray - non-item objectives (kill quests, etc.)
- **Sortable by completion** - click Status column to sort ready quests to top
- **Wiki links** - double-click any quest to open its wiki page

### Character & Storage
- **Character tab** - view your character's skills and levels
- **Storage tab** - searchable inventory across all vault locations
- **Rarity color coding** - items colored by rarity (Common/Uncommon/Rare/Epic/Legendary)

### Stats Panel
- Total creatures tracked, kills, and unique items
- Skinning and butchering items counted separately
- Most killed creature and rarest drops
- Session statistics for loot rates

### Auto-Parser
- **Configurable automatic log parsing** (default every 60 seconds)
- **Countdown display** showing time until next automatic update
- **Manual update button** for immediate parsing
- **Full rescan option** to reprocess all log data

### Self-Update System
- **Automatic version checking** against GitHub releases on startup
- **In-app download** with progress display
- **Automatic installation** and restart when updates are available
- Never miss new features or bug fixes

### Drag & Drop Import
- Import `.gtdb` database files by dragging onto the window
- Merge imported data with your local database
- Share loot data between users

### Developer Options
- **Debug logging** for verbose parsing output
- **Zone editing unlock** to modify zone assignments
- **Item cache debugging** for troubleshooting

### Color-Coded Display
- **Item rarity colors** - Common, Uncommon, Rare, Epic, Legendary
- **NPC favor level colors** - visual indicators for reputation tiers
- **Quest status colors** - ready, incomplete, and in-progress states

## How It Works

Gorgon Tracker reads the game's chat log files and character data:

1. **Chat Logs** - Located in `%LOCALAPPDATA%Low\Elder Game\Project Gorgon\ChatLogs\`
   - Parses `Chat-YY-MM-DD.log` files for combat and loot events
   - Detects kills via `(FATALITY!)` messages
   - Tracks loot via `{Item} added to inventory` messages

2. **Player.log** - Located in `%LOCALAPPDATA%Low\Elder Game\Project Gorgon\`
   - Reads zone transitions to track your current location

3. **Character Reports** - JSON files containing character data
   - Skills, inventory, quest progress, storage contents

4. **Game CDN** - Fetches quest and item data from the official game database

## Installation

### Option 1: Download Release (Recommended)
Download the latest release from the [Releases](https://github.com/Zizzs/gorgon-tracker/releases) page.

### Option 2: Run from Source

1. **Clone the repository**
   ```bash
   git clone https://github.com/Zizzs/gorgon-tracker.git
   cd gorgon-tracker
   ```

2. **Install Python 3.10+**
   - Download from [python.org](https://www.python.org/downloads/)

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python gui.py
   ```

### Building the Executable

To create a standalone `.exe` file:

```bash
python build.py
```

The executable will be created at `dist/GorgonTracker/GorgonTracker.exe`.

**Note:** The build process uses PyInstaller and bundles all dependencies including CustomTkinter and TkinterDnD2.

## Requirements

- Python 3.10 or higher
- Windows (for the compiled executable)
- Project Gorgon installed with chat logging enabled

### Python Dependencies
- `customtkinter` - Modern UI framework
- `tkinterdnd2` - Drag and drop support
- `python-dotenv` - Environment configuration
- `pyinstaller` - For building the executable

## Usage

### Basic Workflow
1. **Launch the application**
2. **Select your character** from the dropdown (auto-detected from game files)
3. **Choose a log file** or use the current day's log
4. **View loot data** - creatures appear in the left panel, click to see their drops
5. **Check quests** - switch to Quests tab to see active quests and completion status

### Wiki Contribution Workflow
1. **Play the game** and kill creatures as normal
2. **Open Gorgon Tracker** and parse your logs
3. **Select a creature** you want to add loot data for
4. **Copy Wiki** to generate the wiki-formatted table
5. **Edit the wiki page** and paste your new data (or use Paste Wiki + Merge to update existing pages)

## Project Structure

```
gorgon-tracker/
├── gui.py              # Main application GUI
├── loot_parser.py      # Chat log parsing logic
├── reports_parser.py   # Character data and quest parsing
├── paths.py            # File path utilities
├── build.py            # Build script for creating .exe
├── requirements.txt    # Python dependencies
└── tests/              # Unit tests
```

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is not affiliated with Elder Game, LLC or Project Gorgon.

## Acknowledgments

- [Project Gorgon](https://projectgorgon.com/) - The game this tool supports
- [Project Gorgon Wiki](https://wiki.projectgorgon.com/) - Community wiki for data reference
