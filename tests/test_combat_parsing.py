import re
from datetime import datetime

# Patterns from loot_parser.py
LOG_LINE_PATTERN = re.compile(r'^(\d{2}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\t\[(\w+)\] (.+)$')
COMBAT_TARGET_PATTERN = re.compile(r' on (.+?) #\d+[!:]')
FATALITY_PATTERN = re.compile(r'\(FATALITY!\)$')

# Actual log lines from Chat-26-02-08.log
TEST_LINES = [
    "26-02-08 08:44:31\t[Combat] Zizzs: Duelist's Slash 3 on Goblin Guard #732848! Dmg: 124 health, 124 armor. (FATALITY!)",
    "26-02-08 08:48:17\t[Combat] Zizzs: Surge Cut 4 on Goblin Spear Scout #739971! Dmg: 96 health, 96 armor. (FATALITY!)",
    "26-02-08 08:49:38\t[Combat] Zizzs: Opening Thrust 5 on Goblin Spear Scout #745238! Dmg: 78 health, 77 armor. (FATALITY!)",
    "26-02-08 08:44:17\t[Combat] Zizzs: Soothe 2 on Goblin Guard #727622! Dmg: 131 health",  # No fatality
    "26-02-08 08:44:18\t[Combat] Goblin Guard #727622: Spear Thrust on Zizzs! Dmg: 10 health, 10 armor",  # Monster attacks player
]

def test_parsing():
    for line in TEST_LINES:
        match = LOG_LINE_PATTERN.match(line.strip())
        if match:
            timestamp_str, channel, message = match.groups()
            print(f"\nLine: {line[:60]}...")
            print(f"  Channel: {channel}")
            print(f"  Message: {message[:50]}...")

            if channel == "Combat":
                target_match = COMBAT_TARGET_PATTERN.search(message)
                fatality_match = FATALITY_PATTERN.search(message)

                print(f"  Target match: {target_match.group(1) if target_match else None}")
                print(f"  Fatality: {bool(fatality_match)}")

if __name__ == "__main__":
    test_parsing()
