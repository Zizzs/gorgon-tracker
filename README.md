# Gorgon Tracker

A desktop application for tracking loot drops, quests, and character data in [Project Gorgon](https://projectgorgon.com/).

## Features

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
- **Rarity color coding** for items

### Export & Stats
- **Export loot data** to wiki-formatted tables
- **Session statistics** - total kills, drops, and loot rates

## How It Works

Gorgon Tracker reads the game's chat log files and character data:

1. **Chat Logs** - Located in `Documents/Project Gorgon/ChatLogs/`
   - Parses `Chat-YY-MM-DD.log` files for combat and loot events
   - Detects kills via `(FATALITY!)` messages
   - Tracks loot via `{Item} added to inventory` messages

2. **Player.log** - Located in `Documents/Project Gorgon/`
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

1. **Launch the application**
2. **Select your character** from the dropdown (auto-detected from game files)
3. **Choose a log file** or use the current day's log
4. **View loot data** - creatures appear in the left panel, click to see their drops
5. **Check quests** - switch to Quests tab to see active quests and completion status
6. **Export data** - use Options panel to export loot tables for the wiki

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
