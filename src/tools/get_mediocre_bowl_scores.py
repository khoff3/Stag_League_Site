import csv

games = list(csv.DictReader(open('data/processed/schedule/2018/schedule.csv')))
weeks = ['14', '15', '16']
teams = ['The Great Gronksby', 'Risk It For The Trubiscuit']

for week in weeks:
    print(f'WEEK {week}')
    for g in games:
        t1 = g['home_team']
        t2 = g['away_team']
        if g['week'] == week and (t1 in teams or t2 in teams):
            print(f'  {t1} vs {t2}: {g["home_points"]} - {g["away_points"]}') 