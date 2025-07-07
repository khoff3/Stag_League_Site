import csv

# Load all games
games = list(csv.DictReader(open('data/processed/schedule/2018/schedule.csv')))

# Remove duplicate mediocre bowl games
seen_mediocre = set()
non_mediocre = []
for g in games:
    if '_mediocre' in g.get('game_id', ''):
        if g['game_id'] not in seen_mediocre:
            seen_mediocre.add(g['game_id'])
            non_mediocre.append(g)
    else:
        non_mediocre.append(g)

print(f'Removed {len(games) - len(non_mediocre)} duplicate mediocre bowl games')

# Save cleaned schedule
with open('data/processed/schedule/2018/schedule.csv', 'w', newline='') as f:
    fieldnames = list(non_mediocre[0].keys())
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for g in non_mediocre:
        writer.writerow(g)

print('Schedule cleaned successfully') 