# Scripts

## 🏗️ **Updated Folder Structure (2024)**

The scripts have been reorganized for better maintainability:

```
src/
├── ingest/nfl/                    # 🏈 Main NFL data ingestion
│   ├── draft_scraper.py          # Draft data extraction
│   ├── schedule.py               # Schedule and standings
│   └── api_client_v2_optimized.py # Player stats scraper
├── scripts/
│   ├── data_processing/          # 📊 Analysis & processing
│   │   ├── comprehensive_manager_tracker.py
│   │   └── enhanced_team_analyzer.py
│   ├── utilities/                # 🔧 Utility scripts
│   │   ├── manager_name_scraper.py
│   │   ├── schedule_validator.py
│   │   └── playoff_score_analyzer.py
│   └── playoff_schedule_constructor.py
├── tools/                        # 🛠️ One-off tools
│   ├── complete_pipeline.sh
│   ├── compare_standings.py
│   └── clean_duplicates.py
└── tests/                        # ✅ Testing
```

## 🚀 **Quick Start Commands**

### **Complete Pipeline**
```bash
# Run complete pipeline for a season
bash src/tools/complete_pipeline.sh 2021

# Or run individual components
python src/ingest/nfl/schedule.py --season 2021
```

### **Manager Analysis (New!)**
```bash
# Generate comprehensive manager statistics
python src/scripts/data_processing/comprehensive_manager_tracker.py

# This creates detailed career stats for all managers across seasons
# Output: data/processed/comprehensive_manager_history.json
```

### **Draft Data Extraction**
```bash
# Extract draft data for any season
python src/ingest/nfl/draft_scraper.py --season 2021

# Supports both snake and auction drafts
# Output: data/processed/drafts/{year}/draft_results.json
```

## 📊 **Manager Tracking System**

### `src/scripts/data_processing/comprehensive_manager_tracker.py`
**NEW**: Comprehensive manager tracking across all seasons with career statistics.

```python
# Basic usage
python src/scripts/data_processing/comprehensive_manager_tracker.py

# This will:
# - Process all seasons (2011-2022)
# - Generate manager mappings
# - Extract draft data
# - Build career statistics
# - Create comprehensive manager profiles
```

**Features:**
- **Cross-season analysis**: Track managers across multiple seasons
- **Career statistics**: Win/loss records, championships, playoff appearances
- **Draft preferences**: Player selection patterns and strategies
- **Performance metrics**: Average points per game, consistency scores
- **League context**: Team IDs, team names, league affiliations

**Output:**
- `data/processed/comprehensive_manager_history.json` - Complete manager database
- `data/processed/csv_exports/manager_career_stats.csv` - CSV export for analysis

### `src/scripts/data_processing/enhanced_team_analyzer.py`
Enhanced team analysis with detailed player statistics.

```python
# Enhanced analysis with player stats
python src/scripts/data_processing/enhanced_team_analyzer.py

# This will:
# - Pull detailed weekly player stats via API client v2
# - Calculate bench contribution percentages
# - Analyze position breakdowns
# - Generate consistency metrics
# - Create manager comparison reports
```

## 🏈 **NFL Data Ingestion**

### `src/ingest/nfl/draft_scraper.py`
**NEW**: Draft data extraction with player IDs and team information.

```python
# Extract draft data for any season
python src/ingest/nfl/draft_scraper.py --season 2021

# Features:
# - Supports both snake and auction drafts
# - Extracts player names and IDs
# - Captures team information
# - Handles different draft formats
```

**Output Structure:**
```
data/processed/drafts/{year}/
├── draft_results.json    # Complete draft data
└── draft_results.csv     # CSV export
```

### `src/ingest/nfl/api_client_v2_optimized.py`
Optimized NFL scraper with concurrent processing for maximum performance.

```python
# Performance testing
scraper = NFLFantasyMultiTableScraper()
team_data = scraper.get_team_data(league_id="864504", team_id="1", season=2012, week=15)
```

**Performance Results:**
- **Concurrent**: 6.36s for 12 teams (5.8x faster than original)
- **Sequential**: 8.76s for 12 teams (1.4x faster than original)
- **Wait times**: 0.5s (optimized for speed + reliability)

### `src/ingest/nfl/schedule.py`
Main schedule and standings processor.

```python
# Basic usage
python src/ingest/nfl/schedule.py --season 2021

# Generate playoff brackets
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; processor = NFLScheduleIngest(); processor.generate_playoff_brackets(2021)"
```

## 🔧 **Utility Scripts**

### `src/scripts/utilities/manager_name_scraper.py`
Scrapes and tracks team manager names across seasons.

```bash
# Scrape manager names for a season
python src/scripts/utilities/manager_name_scraper.py --season 2021

# Output: data/processed/schedule/{year}/managers.json
```

### `src/scripts/utilities/schedule_validator.py`
Validates schedule data and detects errors.

```bash
# Validate specific week
python src/scripts/utilities/schedule_validator.py --season 2021 --week 15

# Validate entire season
python src/scripts/utilities/schedule_validator.py --season 2021
```

### `src/scripts/utilities/playoff_score_analyzer.py`
Analyzes playoff scores and generates brackets.

```bash
# Analyze playoff scores
python src/scripts/utilities/playoff_score_analyzer.py --season 2021
```

## 🛠️ **Tools**

### `src/tools/complete_pipeline.sh`
Complete end-to-end pipeline for a season.

```bash
# Run complete pipeline
bash src/tools/complete_pipeline.sh 2021

# This will:
# 1. Scrape schedule data
# 2. Generate playoff brackets
# 3. Create manager mappings
# 4. Extract draft data
# 5. Validate results
```

### `src/tools/compare_standings.py`
Compare standings across seasons.

```bash
# Compare standings
python src/tools/compare_standings.py --seasons 2020 2021
```

### `src/tools/clean_duplicates.py`
Clean duplicate data entries.

```bash
# Clean duplicates
python src/tools/clean_duplicates.py
```

## 🏆 **Playoff System**

### `src/scripts/playoff_schedule_constructor.py`
Constructs playoff schedules for any season.

```python
# Basic usage
from src.scripts.playoff_schedule_constructor import construct_playoff_schedule

seeds = [
    {"seed": 1, "team_id": "2", "team_name": "Granger Danger"},
    {"seed": 2, "team_id": "5", "team_name": "Fencing Beats Football"},
    {"seed": 3, "team_id": "1", "team_name": "The REVolution"},
    {"seed": 4, "team_id": "6", "team_name": "Swagger Badgers"}
]

bracket = construct_playoff_schedule(2011, seeds)
```

**Features:**
- **Generic bracket construction** for any season
- **Automatic score fetching** via API client
- **Multiple playoff formats** (4-team, 6-team)
- **Comprehensive game tracking** with winners/losers

## 📊 **Data Annotation Scripts**

### `src/scripts/utilities/playoff_annotator_fixed.py`
Annotates schedule games with playoff status and rounds.

```bash
# Basic usage
python src/scripts/utilities/playoff_annotator_fixed.py --season 2021

# Custom output location
python src/scripts/utilities/playoff_annotator_fixed.py --season 2021 --output annotated_schedule.csv
```

**Features:**
- **Automatic Type Conversion**: Handles string/int game ID mismatches
- **Comprehensive Playoff Mapping**: Maps all playoff rounds
- **Summary Statistics**: Provides detailed breakdown of playoff vs regular season games
- **Flexible Output**: Saves to default location or custom path

**Output Columns Added:**
- `is_playoff`: Boolean flag for playoff games
- `playoff_round`: Internal round identifier
- `playoff_bracket`: Bracket type ('winners' or 'consolation')
- `playoff_round_name`: Human-readable round name

## 🎯 **Recent Progress (2024)**

### ✅ **Manager Tracking System**
- **Comprehensive manager history** across all seasons (2011-2022)
- **Career statistics**: Win rates, playoff appearances, championships
- **Draft preferences**: Player selection patterns and strategies
- **Performance analysis**: Consistency metrics and trends

### ✅ **Enhanced Data Pipeline**
- **Draft data extraction** for all seasons with player IDs
- **Manager name mapping** across seasons
- **Playoff bracket construction** with proper seeding
- **Data validation** and cross-checking

### ✅ **Organized Codebase**
- **Logical folder structure** with clear separation of concerns
- **Removed duplicate scripts** and deprecated code
- **Fixed import issues** and API compatibility
- **Consistent naming conventions**

## 🐛 **Debugging & Quality Assurance Procedures**

### Critical Issues to Check Before Production

Based on our debugging experience, here are the key issues that can break the pipeline:

#### 1. **Team Sorting Logic** ⚠️ **CRITICAL**
**Issue**: Wrong sorting criteria can completely break playoff seeding
**Symptoms**: 
- Middle teams assigned incorrectly in playoff brackets
- Mediocre bowl games use wrong teams
- Playoff annotation fails to detect games

**Prevention Checklist**:
```bash
# ✅ ALWAYS verify sorting logic before running pipeline
python -c "
from src.ingest.nfl.schedule import NFLScheduleIngest
ingest = NFLScheduleIngest()
# Check what teams are being assigned to each bracket
winners, middle, consolation = ingest._get_playoff_teams(team_records, season, playoff_games)
print('Winners:', [(tid, data['team_name']) for tid, data in winners])
print('Middle:', [(tid, data['team_name']) for tid, data in middle])
print('Consolation:', [(tid, data['team_name']) for tid, data in consolation])
"
```

#### 2. **Import Issues** ⚠️ **CRITICAL**
**Issue**: Scripts may have incorrect import paths after reorganization
**Symptoms**: 
- ModuleNotFoundError when running scripts
- Import errors for API client classes

**Prevention Checklist**:
```bash
# ✅ Test imports before running
python -c "from src.scripts.playoff_schedule_constructor import PlayoffScheduleConstructor; print('✅ Import successful!')"

# ✅ Check API client imports
python -c "from src.ingest.nfl.api_client_v2_optimized import NFLFantasyMultiTableScraper; print('✅ API client import successful!')"
```

#### 3. **Manager Data Consistency** ⚠️ **IMPORTANT**
**Issue**: Manager names may not be consistent across seasons
**Symptoms**: 
- Same manager appears as different entries
- Career statistics are split across multiple profiles

**Prevention Checklist**:
```bash
# ✅ Verify manager mappings
cat data/processed/schedule/*/managers.json | jq '.managers'

# ✅ Check comprehensive manager history
cat data/processed/comprehensive_manager_history.json | jq '.managers | keys'
```

## 📈 **Performance Notes**

- **Data ingestion**: ~2-3 minutes per season
- **Manager analysis**: ~1-2 minutes per season
- **Draft extraction**: ~30-60 seconds per season
- **Validation**: ~1-2 minutes per week
- **Complete pipeline**: ~5-10 minutes per season

## 🤝 **Contributing**

1. Test changes on multiple seasons (2018, 2019, 2020, 2021)
2. Validate playoff bracket logic
3. Ensure manager tracking works correctly
4. Update documentation for any new features
5. Follow the new folder structure conventions

## 📝 **Notes**

- **2018+ seasons**: Use 6-team championship bracket with toilet bowl
- **Pre-2018 seasons**: Use legacy playoff formats
- **Manager tracking**: Requires manager name mapping for accurate career stats
- **Draft data**: Supports both snake and auction formats
- **API client**: Use `api_client_v2_optimized.py` for best performance

---

**Last Updated**: December 2024  
**Status**: Production Ready for 2011-2022 seasons with comprehensive manager tracking
