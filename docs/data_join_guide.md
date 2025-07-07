# Data Join Guide: Raw Player Scores + Playoff Schedule

> **Purpose**: Explain how to join the raw player scores (from validation) with playoff-annotated schedule data for comprehensive analysis.

## Table of Contents
1. [Overview](#overview)
2. [Data Sources](#data-sources)
3. [Join Process](#join-process)
4. [Validation Discrepancies](#validation-discrepancies)
5. [Practical Examples](#practical-examples)
6. [Analysis Use Cases](#analysis-use-cases)

---

## Overview

The data join process connects two key data sources:

1. **Raw Player Scores**: Detailed player-level data from `team_{id}.json` files
2. **Playoff-Annotated Schedule**: Game-level data with playoff context from `schedule_annotated.csv`

This join enables comprehensive analysis that combines granular player performance with playoff context.

---

## Data Sources

### **1. Raw Player Data**
**Location**: `data/raw/{season}/week_{week}/team_{id}.json`

**Structure**:
```json
{
  "players": [
    {
      "name": "Tom Brady",
      "position": "QB",
      "fantasy_points": 24.82,
      "lineup_status": "starter",
      "passing_yards": 443,
      "passing_tds": 1,
      "nfl_team": "NE"
    }
  ],
  "team_stats": {
    "total_players": 15,
    "starters": 13,
    "bench": 2,
    "total_points": 69.52
  }
}
```

### **2. Annotated Schedule Data**
**Location**: `data/processed/schedule/{season}/schedule_annotated.csv`

**Structure**:
```csv
game_id,week,home_team,home_team_id,home_points,away_team,away_team_id,away_points,is_playoff,playoff_round,bracket,playoff_round_name
20121541,15,BedonkaGronk,4,69.52,Forgetting Brandon Marshall,1,65.86,True,winners_round_1,winners,Winners Round 1
```

---

## Join Process

### **Step 1: Load Annotated Schedule**
```python
import pandas as pd

# Load playoff-annotated schedule
schedule = pd.read_csv('data/processed/schedule/2012/schedule_annotated.csv')

# Filter for specific week
week_games = schedule[schedule['week'] == 15]
playoff_games = week_games[week_games['is_playoff'] == True]
```

### **Step 2: Load Raw Player Data**
```python
import json

def load_raw_player_data(season: int, week: int, team_id: str):
    raw_path = f"data/raw/{season}/week_{week:02d}/team_{team_id}.json"
    with open(raw_path, 'r') as f:
        return json.load(f)

# Load data for all teams in the week
team_data = {}
for _, game in week_games.iterrows():
    home_team_id = game['home_team_id']
    away_team_id = game['away_team_id']
    
    if home_team_id not in team_data:
        team_data[home_team_id] = load_raw_player_data(season, week, home_team_id)
    if away_team_id not in team_data:
        team_data[away_team_id] = load_raw_player_data(season, week, away_team_id)
```

### **Step 3: Extract Starter Scores**
```python
def get_team_starters(team_data):
    starters = []
    for player in team_data['players']:
        if player.get('lineup_status') == 'starter' and player.get('position') != 'BN':
            starters.append(player)
    return starters

def calculate_team_score(starters):
    return sum(player.get('fantasy_points', 0) for player in starters)

# Calculate reconstructed scores
for team_id, data in team_data.items():
    starters = get_team_starters(data)
    reconstructed_score = calculate_team_score(starters)
    print(f"Team {team_id}: {reconstructed_score:.1f} points")
```

### **Step 4: Join and Validate**
```python
join_results = []

for _, game in week_games.iterrows():
    home_team_id = game['home_team_id']
    away_team_id = game['away_team_id']
    
    # Get raw data
    home_data = team_data.get(home_team_id)
    away_data = team_data.get(away_team_id)
    
    if home_data and away_data:
        # Calculate reconstructed scores
        home_starters = get_team_starters(home_data)
        away_starters = get_team_starters(away_data)
        
        home_reconstructed = calculate_team_score(home_starters)
        away_reconstructed = calculate_team_score(away_starters)
        
        # Get schedule scores
        home_schedule = game['home_points']
        away_schedule = game['away_points']
        
        # Calculate differences
        home_diff = abs(home_reconstructed - home_schedule)
        away_diff = abs(away_reconstructed - away_schedule)
        
        # Join result
        join_result = {
            "game_id": game['game_id'],
            "is_playoff": game['is_playoff'],
            "playoff_round": game.get('playoff_round_name', ''),
            "schedule_scores": {"home": home_schedule, "away": away_schedule},
            "reconstructed_scores": {"home": home_reconstructed, "away": away_reconstructed},
            "validation": {
                "home_diff": home_diff,
                "away_diff": away_diff,
                "both_valid": home_diff < 0.1 and away_diff < 0.1
            }
        }
        
        join_results.append(join_result)
```

---

## Validation Discrepancies

### **Understanding the Differences**

The validation process compares:
- **Schedule Scores**: From the schedule scraper (official game results)
- **Reconstructed Scores**: Sum of starter fantasy points from raw player data

### **Common Causes of Discrepancies**

1. **Scoring Rule Differences**
   - Schedule scraper may use different scoring rules
   - Raw player data may include additional bonuses/penalties

2. **Starter Detection Issues**
   - Different methods for identifying starters vs. bench players
   - Position-based vs. lineup-status-based detection

3. **Data Timing Differences**
   - Schedule data may be from final results
   - Raw player data may be from live game stats

4. **Rounding Differences**
   - Different precision in score calculations
   - Accumulated rounding errors

### **Example Discrepancy Analysis**

```python
# From our example output:
# Game 20121541: BedonkaGronk vs Forgetting Brandon Marshall
# Schedule: 69.5 - 65.9
# Reconstructed: 70.9 - 123.1
# Differences: Home 1.4, Away 57.2

# Analysis:
# - Home team (BedonkaGronk): Small difference (1.4) - likely rounding
# - Away team (Forgetting Brandon Marshall): Large difference (57.2) - significant issue
```

### **Handling Discrepancies**

```python
def analyze_discrepancy(game_result):
    home_diff = game_result['validation']['home_diff']
    away_diff = game_result['validation']['away_diff']
    
    if home_diff > 1.0 or away_diff > 1.0:
        print(f"⚠️  Large discrepancy detected in game {game_result['game_id']}")
        
        if home_diff > 10.0 or away_diff > 10.0:
            print("   🔍 Investigate scoring rules or data source")
        elif home_diff > 1.0 and away_diff > 1.0:
            print("   🔍 Check starter detection logic")
        else:
            print("   🔍 Verify individual player stats")
    
    return home_diff < 0.1 and away_diff < 0.1
```

---

## Practical Examples

### **Example 1: Playoff Week Analysis**

```python
# Run the data join example
python src/scripts/data_join_example.py

# Output shows:
# - 4 playoff games in Week 15
# - Each game with schedule vs. reconstructed scores
# - Validation status for each game
# - Detailed discrepancy analysis
```

### **Example 2: Championship Game Analysis**

```python
# Filter for championship game
championship_games = join_results.filter(
    lambda x: x['playoff_round'] == 'Championship'
)

for game in championship_games:
    print(f"🏆 Championship Game Analysis:")
    print(f"   Winner: {game['schedule_scores']['winner']}")
    print(f"   Score: {game['schedule_scores']['home']:.1f} - {game['schedule_scores']['away']:.1f}")
    print(f"   Validation: {'✅' if game['validation']['both_valid'] else '❌'}")
```

### **Example 3: Season-Wide Analysis**

```python
def analyze_season_playoffs(season):
    # Load full season data
    schedule = pd.read_csv(f'data/processed/schedule/{season}/schedule_annotated.csv')
    playoff_games = schedule[schedule['is_playoff'] == True]
    
    # Analyze each playoff week
    for week in playoff_games['week'].unique():
        week_games = playoff_games[playoff_games['week'] == week]
        print(f"Week {week}: {len(week_games)} playoff games")
        
        # Run join analysis for this week
        join_summary = demonstrate_data_join(season, week)
        print(f"  Validation rate: {join_summary['validation_rate']*100:.1f}%")
```

---

## Analysis Use Cases

### **1. Playoff Performance Analysis**
```python
# Compare regular season vs. playoff performance
def analyze_playoff_performance(team_id, season):
    # Get regular season games
    regular_games = schedule[
        (schedule['home_team_id'] == team_id) & 
        (schedule['is_playoff'] == False)
    ]
    
    # Get playoff games
    playoff_games = schedule[
        (schedule['home_team_id'] == team_id) & 
        (schedule['is_playoff'] == True)
    ]
    
    # Calculate averages
    regular_avg = regular_games['home_points'].mean()
    playoff_avg = playoff_games['home_points'].mean()
    
    return {
        "regular_season_avg": regular_avg,
        "playoff_avg": playoff_avg,
        "playoff_performance": playoff_avg - regular_avg
    }
```

### **2. Championship Game Player Analysis**
```python
# Analyze individual player performance in championship games
def analyze_championship_players(season):
    championship_games = schedule[
        (schedule['playoff_round'] == 'championship') & 
        (schedule['season'] == season)
    ]
    
    for _, game in championship_games.iterrows():
        # Load raw player data for both teams
        home_data = load_raw_player_data(season, game['week'], game['home_team_id'])
        away_data = load_raw_player_data(season, game['week'], game['away_team_id'])
        
        # Find top performers
        home_starters = get_team_starters(home_data)
        away_starters = get_team_starters(away_data)
        
        all_players = home_starters + away_starters
        top_performers = sorted(all_players, key=lambda x: x['fantasy_points'], reverse=True)[:5]
        
        print(f"🏆 Championship Game Top Performers:")
        for i, player in enumerate(top_performers, 1):
            print(f"  {i}. {player['name']} ({player['position']}) - {player['fantasy_points']:.1f} pts")
```

### **3. Bracket Progression Analysis**
```python
# Track team performance through playoff brackets
def analyze_bracket_progression(team_id, season):
    team_games = schedule[
        (schedule['home_team_id'] == team_id) & 
        (schedule['is_playoff'] == True) &
        (schedule['season'] == season)
    ].sort_values('week')
    
    progression = []
    for _, game in team_games.iterrows():
        progression.append({
            "week": game['week'],
            "round": game['playoff_round_name'],
            "opponent": game['away_team'],
            "score": f"{game['home_points']:.1f} - {game['away_points']:.1f}",
            "result": "W" if game['home_points'] > game['away_points'] else "L"
        })
    
    return progression
```

---

## Best Practices

### **1. Always Validate**
- Compare reconstructed vs. schedule scores
- Investigate large discrepancies
- Document validation rates

### **2. Handle Missing Data**
- Check for missing team files
- Provide fallback values
- Log data quality issues

### **3. Use Consistent Join Keys**
- Season, week, team_id for reliable joins
- Validate join completeness
- Handle edge cases (bye weeks, etc.)

### **4. Document Discrepancies**
- Log validation failures
- Analyze patterns in discrepancies
- Update scoring rules if needed

The data join process enables powerful analysis by combining granular player performance with playoff context, creating a comprehensive view of fantasy football success! 