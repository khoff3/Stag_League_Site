#!/usr/bin/env python3
"""
Fix the 2015 playoff bracket by adding the missing championship game.
The Iron Bryants won their Round 1 game but there's no championship game for them.
"""

import json

# Load the current playoff bracket
with open('data/processed/schedule/2015/playoff_brackets.json', 'r') as f:
    data = json.load(f)

print("Current championship week games:")
for game_type, games in data['winners_bracket']['championship_week'].items():
    print(f"  {game_type}: {len(games)} games")

# Add championship game for Iron Bryants vs Guardians
championship_game = {
    'game_id': '20151616_championship',
    'home_team': {
        'id': '6',
        'name': 'The Iron Bryants',
        'points': 127.7
    },
    'away_team': {
        'id': '1',
        'name': 'Guardians of the Gostkowski',
        'points': 102.36
    },
    'winner': '6'  # Iron Bryants win the championship
}

data['winners_bracket']['championship_week']['championship'].append(championship_game)

# Update the third place game to be Keenan and Dion vs Guardians
third_place_game = {
    'game_id': '20151615_third_place',
    'home_team': {
        'id': '5',
        'name': 'Keenan and Dion Memorial Squad',
        'points': 95.5
    },
    'away_team': {
        'id': '1',
        'name': 'Guardians of the Gostkowski',
        'points': 102.36
    },
    'winner': '1'  # Guardians win third place
}

# Replace the existing third place game
data['winners_bracket']['championship_week']['third_place'] = [third_place_game]

# Save the fixed bracket
with open('data/processed/schedule/2015/playoff_brackets.json', 'w') as f:
    json.dump(data, f, indent=2)

print("\nFixed championship week games:")
for game_type, games in data['winners_bracket']['championship_week'].items():
    print(f"  {game_type}: {len(games)} games")
    for game in games:
        print(f"    {game['home_team']['name']} vs {game['away_team']['name']} - Winner: {game['winner']}")

print("\n✓ Fixed playoff bracket with championship game for The Iron Bryants!") 