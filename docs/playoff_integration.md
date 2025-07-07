# Playoff Data Integration in the Full Pipeline

> **Purpose**: Explain how playoff data flows through the complete Stag League data pipeline, from raw ingestion to final analysis and visualization.

## Table of Contents
1. [Pipeline Overview](#pipeline-overview)
2. [Data Flow Integration](#data-flow-integration)
3. [Playoff Annotation Process](#playoff-annotation-process)
4. [Analysis Integration](#analysis-integration)
5. [Star Schema Integration](#star-schema-integration)
6. [Complete Pipeline Commands](#complete-pipeline-commands)

---

## Pipeline Overview

The playoff data integration follows this complete flow:

```mermaid
flowchart TD
    subgraph "Phase 1: Data Ingestion"
        A[NFL Schedule Scraper] --> B[schedule.csv]
        A --> C[playoff_brackets.json]
        D[Team Week Scraper] --> E[team_{id}.json files]
    end
    
    subgraph "Phase 2: Data Annotation"
        B --> F[Playoff Annotator]
        C --> F
        F --> G[schedule_annotated.csv]
    end
    
    subgraph "Phase 3: Data Validation"
        E --> H[Schedule Validator]
        G --> H
        H --> I[Validation Reports]
    end
    
    subgraph "Phase 4: Analysis"
        G --> J[Team Manager Tracker]
        E --> J
        J --> K[Manager Analysis]
        
        G --> L[Enhanced Analyzer]
        E --> L
        L --> M[Enhanced Analysis]
    end
    
    subgraph "Phase 5: Star Schema"
        G --> N[Transform Layer]
        E --> N
        N --> O[SQLite Database]
        N --> P[Parquet Files]
    end
    
    subgraph "Phase 6: Visualization"
        O --> Q[Frontend API]
        P --> Q
        Q --> R[Interactive Dashboard]
    end
```

---

## Data Flow Integration

### **Phase 1: Raw Data Ingestion**

The pipeline starts with comprehensive data collection:

```bash
# 1. Scrape schedule data (including playoff brackets)
python src/cli.py ingest schedule --season 2012 --force-refresh
```

**Outputs**:
- `data/processed/schedule/2012/schedule.csv` - All regular season and playoff games
- `data/processed/schedule/2012/playoff_brackets.json` - Playoff bracket structure
- `data/processed/schedule/2012/postseason_standings.json` - Final playoff results

**Key Integration Points**:
- Schedule scraper automatically detects playoff weeks (15-16)
- Generates playoff brackets based on final regular season standings
- Maps game IDs between schedule and bracket data

### **Phase 2: Playoff Annotation**

The playoff annotation bridges raw data to analysis-ready data:

```bash
# 2. Annotate schedule with playoff context
python src/cli.py annotate playoff --season 2012
```

**Transformation**:
```csv
# Before annotation (schedule.csv)
game_id,week,home_team,home_points,away_team,away_points
20121541,15,BedonkaGronk,69.52,Forgetting Brandon Marshall,65.86

# After annotation (schedule_annotated.csv)  
game_id,week,home_team,home_points,away_team,away_points,is_playoff,playoff_round,bracket,playoff_round_name
20121541,15,BedonkaGronk,69.52,Forgetting Brandon Marshall,65.86,True,winners_round_1,winners,Winners Round 1
```

**Added Context**:
- `is_playoff` - Boolean flag for playoff games
- `playoff_round` - Specific round (semifinal, championship, etc.)
- `bracket` - Winners or consolation bracket
- `playoff_round_name` - Human-readable round description

### **Phase 3: Data Validation**

Validate that reconstructed scores match schedule data:

```bash
# 3. Validate data integrity
python src/schedule_validator.py --season 2012 --week 15 --force-refresh
```

**Validation Process**:
1. Load `schedule_annotated.csv` for game scores
2. Scrape detailed player data from `team_{id}.json` files
3. Reconstruct team scores by summing starter fantasy points
4. Compare reconstructed vs. schedule scores
5. Report validation rate and discrepancies

---

## Playoff Annotation Process

### **Bracket Structure Detection**

The annotator handles different playoff formats:

```python
# 4-team playoff (2011)
{
  "semifinals": [...],
  "final": {...},
  "third_place": {...},
  "consolation_games": [...]
}

# 6-team playoff (2012+)  
{
  "winners_bracket": {
    "round_1": [...],
    "championship_week": {
      "championship": [...],
      "third_place": [...]
    }
  },
  "consolation_bracket": {
    "round_1": [...],
    "toilet_bowl": [...]
  }
}
```

### **Game ID Mapping**

The annotator maps bracket games to schedule games:

```python
# Extract playoff games from brackets
playoff_games = {
    "20121541": {
        "playoff_round": "winners_round_1",
        "bracket": "winners", 
        "round_name": "Winners Round 1",
        "is_playoff": True
    }
}

# Annotate schedule with playoff info
schedule.loc[schedule['game_id'] == 20121541, 'is_playoff'] = True
schedule.loc[schedule['game_id'] == 20121541, 'playoff_round'] = 'winners_round_1'
```

---

## Analysis Integration

### **Team Manager Tracking**

Playoff context enhances manager analysis:

```bash
# 4. Generate manager analysis with playoff context
python src/cli.py analyze team-managers --seasons 2012
```

**Enhanced Output**:
```json
{
  "manager_name": "John Doe",
  "career_stats": {
    "total_games": 156,
    "playoff_games": 12,
    "championship_appearances": 2,
    "championships": 1,
    "playoff_win_rate": 0.667
  },
  "season_breakdown": {
    "2012": {
      "regular_season": "8-6-0",
      "playoff_result": "Champion",
      "playoff_games": [
        {"round": "Winners Round 1", "opponent": "Team B", "score": "69.52-65.86", "result": "W"},
        {"round": "Championship", "opponent": "Team C", "score": "75.78-91.34", "result": "L"}
      ]
    }
  }
}
```

### **Enhanced Analysis**

Detailed player stats with playoff context:

```bash
# 5. Enhanced analysis with playoff performance
python src/cli.py analyze enhanced --seasons 2012
```

**Playoff-Specific Metrics**:
- Playoff performance vs. regular season performance
- Championship game player stats
- Playoff pressure performance analysis
- Bracket progression tracking

---

## Star Schema Integration

### **Enhanced Fact Tables**

The star schema includes playoff context:

```sql
-- Enhanced FACT_TEAM_WEEK table
CREATE TABLE FACT_TEAM_WEEK (
    team_id INTEGER,
    week INTEGER,
    season INTEGER,
    pts_for FLOAT,
    pts_against FLOAT,
    result CHAR(1),
    is_playoff BOOLEAN,
    playoff_round VARCHAR(50),
    playoff_bracket VARCHAR(20),
    playoff_round_name VARCHAR(50)
);

-- Playoff-specific queries
SELECT 
    team_id,
    COUNT(*) as playoff_games,
    AVG(pts_for) as avg_playoff_points,
    SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) as playoff_wins
FROM FACT_TEAM_WEEK 
WHERE is_playoff = TRUE
GROUP BY team_id;
```

### **Playoff Dimensions**

Additional dimension tables for playoff analysis:

```sql
-- Playoff rounds dimension
CREATE TABLE DIM_PLAYOFF_ROUND (
    playoff_round_id INTEGER PRIMARY KEY,
    round_name VARCHAR(50),
    bracket VARCHAR(20),
    week_number INTEGER,
    is_championship BOOLEAN
);

-- Playoff games fact table
CREATE TABLE FACT_PLAYOFF_GAME (
    game_id INTEGER PRIMARY KEY,
    season INTEGER,
    playoff_round_id INTEGER,
    home_team_id INTEGER,
    away_team_id INTEGER,
    home_score FLOAT,
    away_score FLOAT,
    winner_team_id INTEGER
);
```

---

## Complete Pipeline Commands

### **Full Season Processing**

```bash
#!/bin/bash
# complete_pipeline.sh

SEASON=$1
echo "Processing complete pipeline for season $SEASON..."

# Phase 1: Data Ingestion
echo "Phase 1: Data Ingestion"
python src/cli.py ingest schedule --season $SEASON --force-refresh

# Phase 2: Data Annotation  
echo "Phase 2: Playoff Annotation"
python src/cli.py annotate playoff --season $SEASON

# Phase 3: Data Validation
echo "Phase 3: Data Validation"
python src/schedule_validator.py --season $SEASON --week 1 --force-refresh
python src/schedule_validator.py --season $SEASON --week 15 --force-refresh

# Phase 4: Analysis
echo "Phase 4: Analysis"
python src/cli.py analyze team-managers --seasons $SEASON
python src/cli.py analyze enhanced --seasons $SEASON

# Phase 5: Testing
echo "Phase 5: Validation Testing"
python src/cli.py test full

echo "Complete pipeline finished for season $SEASON!"
```

### **Individual Phase Commands**

```bash
# Quick validation
python src/cli.py test quick --season 2012

# Schedule validation only
python src/schedule_validator.py --season 2012 --week 15 --force-refresh

# Playoff annotation only
python src/cli.py annotate playoff --season 2012

# Manager analysis only
python src/cli.py analyze team-managers --seasons 2012
```

---

## Data Quality Assurance

### **Validation Checklist**

After running the complete pipeline:

- [ ] **Schedule Data**: All weeks scraped (1-16)
- [ ] **Playoff Brackets**: Correct bracket structure generated
- [ ] **Playoff Annotation**: All playoff games properly tagged
- [ ] **Score Validation**: 100% validation rate for reconstructed scores
- [ ] **Manager Data**: Real manager names mapped to teams
- [ ] **Enhanced Analysis**: Detailed player stats with playoff context

### **Quality Metrics**

```python
# Example quality checks
def validate_playoff_integration(season):
    schedule = pd.read_csv(f'data/processed/schedule/{season}/schedule_annotated.csv')
    
    # Check playoff game count
    playoff_games = schedule[schedule['is_playoff']]
    expected_playoff_games = 8  # 4 semifinals + 4 championship week
    
    # Check championship game
    championship = schedule[schedule['playoff_round'] == 'championship']
    
    # Check bracket consistency
    winners_bracket = schedule[schedule['bracket'] == 'winners']
    consolation_bracket = schedule[schedule['bracket'] == 'consolation']
    
    return {
        'playoff_games_found': len(playoff_games),
        'championship_game_found': len(championship) == 1,
        'bracket_consistency': len(winners_bracket) > 0 and len(consolation_bracket) > 0
    }
```

---

## Benefits of Playoff Integration

### **1. Complete Historical Context**
- Every game knows if it's playoff or regular season
- Full playoff bracket progression tracked
- Championship and consolation game identification

### **2. Enhanced Analysis Capabilities**
- Playoff performance vs. regular season performance
- Championship game player statistics
- Playoff pressure analysis
- Bracket progression tracking

### **3. Data Consistency**
- Single source of truth for playoff structure
- Consistent game ID mapping across all systems
- Validated score reconstruction

### **4. Flexible Querying**
- SQL queries can filter by playoff status
- Time series analysis with playoff context
- Manager performance in playoff vs. regular season

The playoff integration transforms the raw data pipeline into a comprehensive system that captures the full fantasy football experience, from regular season battles to championship glory! 