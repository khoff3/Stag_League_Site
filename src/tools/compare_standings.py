import json

# Load the final standings
with open('data/processed/schedule/2017/final_standings.json', 'r') as f:
    data = json.load(f)

print('=== CURRENT 2017 FINAL STANDINGS ===')
print('Place | Team | Regular Season | Postseason Rank | Postseason Label')
print('------|------|---------------|-----------------|----------------')

for t in data:
    place = t.get('place', '')
    team_name = t.get('team_name', '')
    record = t.get('regular_season_record', '')
    rank = t.get('postseason_rank', '')
    label = t.get('postseason_label', '')
    
    # Handle None values
    if place is None: place = ''
    if team_name is None: team_name = ''
    if record is None: record = ''
    if rank is None: rank = ''
    if label is None: label = ''
    
    print(f'{place:5} | {team_name:20} | {record:13} | {rank:15} | {label}')

print('\n=== OFFICIAL 2017 FINAL STANDINGS ===')
official = [
    (1, "New Gurley", "Champion"),
    (2, "Hooked on a Thielen", "Runner Up"),
    (3, "Roaring Rivers", "Third Place"),
    (4, "Ultralight Kareem", "Fourth Place"),
    (5, "Allen the Family", "Fifth Place"),
    (6, "Nuthin but a Green Thang", "Sixth Place"),
    (7, "Don't Check My Pryors", "Seventh Place"),
    (8, "Suicide Squad", "Eighth Place"),
    (9, "O Beckham Where Art Thou", "Ninth Place"),
    (10, "Diggs It", "Tenth Place")
]

print('Place | Team | Label')
print('------|------|------')
for place, team, label in official:
    print(f'{place:5} | {team:20} | {label}')

print('\n=== COMPARISON ===')
print('Place | Our System | Official | Match?')
print('------|------------|----------|-------')

for i in range(1, 11):
    our_team = next((t['team_name'] for t in data if t.get('place') == i), 'MISSING')
    official_team = next((team for place, team, _ in official if place == i), 'MISSING')
    match = '✅' if our_team == official_team else '❌'
    print(f'{i:5} | {our_team:10} | {official_team:8} | {match}')

# Count matches
matches = sum(1 for i in range(1, 11) 
              if next((t['team_name'] for t in data if t.get('place') == i), '') == 
                 next((team for place, team, _ in official if place == i), ''))

print(f'\nTotal Matches: {matches}/10 ({matches*10}%)') 