# Project Gorgon Wiki Uploader - Context

## Game Mechanics: Loot System

### How Loot Works
1. **Kill a mob** - Combat ends with `(FATALITY!)` in the log
2. **Loot items from corpse** - Items appear as `[Status] {Item} added to inventory.`
3. **Optional: Skin OR Butcher** - After looting, you can perform one of these skills on the corpse

### Skinning vs Butchering
- **Skinning**: Extracts hides, skins, feathers (animal materials)
- **Butchering**: Extracts meat, bones, organs (consumable/crafting materials)
- These are mutually exclusive - you can only do one per corpse
- Each gives XP: `You earned X XP in Skinning.` or `You earned X XP in Butchering.`

### Log Sequence Example
```
[Combat] Player: Attack on Creature #123! Dmg: 100 health. (FATALITY!)
[Status] You earned 50 XP in Combat Skill.
[Status] Gold Coins x5 added to inventory.     <- Regular loot from corpse
[Status] Rare Item added to inventory.          <- Regular loot from corpse
[Status] You earned 20 XP in Butchering.        <- Butchering skill used
[Status] Raw Meat added to inventory.           <- Butchering result
```

### Important Notes
- "You bury the corpse" is flavor text, not a separate mechanic
- Items looted BEFORE skinning/butchering XP = regular mob drops
- Items looted AFTER skinning/butchering XP = skill results
- Butchering can fail: `You botch the butchering!` (gives reduced XP, no items)

## Chat Log Format

### File Naming
- `Chat-YY-MM-DD.log` - One file per day

### Line Format
```
YY-MM-DD HH:MM:SS\t[Channel] Message
```

### Channels
- `[Combat]` - Damage, abilities, fatalities
- `[Status]` - XP gains, loot, skill messages
- `[Global]`, `[Trade]`, `[Help]` - Chat channels (ignore for loot tracking)

### Key Patterns
- Kill detection: `(FATALITY!)` at end of combat line
- Creature ID: `Creature Name #123456` (number is instance ID)
- Loot: `{Item Name} added to inventory.` or `{Item Name} x{count} added to inventory.`
- Skinning XP: `You earned \d+ XP in Skinning.`
- Butchering XP: `You earned \d+ XP in Butchering.`

## Zone Detection

### Player.log
Located in parent directory of ChatLogs. Contains zone transitions:
```
[HH:MM:SS] LOADING LEVEL AreaSunVale
```

### Zone Name Mapping
Internal names like `AreaSunVale` map to display names like `Sun Vale`.
See `ZONE_NAMES` dict in `loot_parser.py`.
