# NFL Fantasy Football API Client

## 🚦 How to Run (Schedule & Results Ingest)

### Run the Schedule Scraper

You can run the schedule scraper directly to fetch, process, and generate playoff brackets and standings for a season:

```bash
# From the project root
python -m src.ingest.nfl.schedule --season 2012
```

- This will fetch the full season schedule, generate playoff brackets, and postseason standings for the specified season.
- Outputs are saved in `data/raw/schedule/` and `data/processed/schedule/`.

### Run the Playoff Annotator

After running the schedule scraper, annotate the schedule with playoff information:

```bash
# Use the fixed annotator for proper playoff round identification
python src/scripts/playoff_annotator_fixed.py --season 2012
```

- This annotates schedule games with playoff status and rounds (Championship, Third Place, Toilet Bowl, etc.)
- Uses the correct bracket file (`playoff_bracket_complete.json`) for accurate annotations.

## 🏆 **Standings Processing Guide**

### **Complete Process Flow**

**Step 1: Scrape Schedule Data (Required First)**
```bash
# Scrape schedule data for the season
python -m src.ingest.nfl.schedule --season 2014 --force-refresh
```

**Step 2: Annotate Playoffs (Required)**
```bash
# Annotate schedule with playoff information
python src/scripts/playoff_annotator_fixed.py --season 2014
```

**Step 3: Generate Standings (Final Step)**
```bash
# Generate all standings for the season
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.save_all_standings(2014)"
```

### **Mediocre Bowl Automation**

The system now automatically handles mediocre bowl games for seasons with 12 teams (2018+):

- **Seeds 7 and 8** from regular season standings automatically play each other in Weeks 14, 15, and 16
- **Real scores** are fetched using the API client to get actual fantasy points for each team
- **Simulated games** are injected into the schedule with proper flags
- **Cumulative standings** are calculated across all three weeks

**Note:** The optimized API client fetches real team scores from NFL Fantasy, including offensive players, kickers, and defense/special teams for complete team scores.

**Mediocre Bowl Process:**
```bash
# The mediocre bowl is automatically handled when generating standings
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.save_all_standings(2018)"
```

**Manual Mediocre Bowl Injection (if needed):**
```bash
# Manually inject mediocre bowl games
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.inject_mediocre_bowl_games(2018)"
```

### **Generate All Standings for a Season**

The system now generates comprehensive standings with regular season-based final placement:

```bash
# Generate all standings for a season
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.save_all_standings(2013)"
```

This creates **4 JSON files** for the season:

1. **`regular_season_standings.json`** - Pure regular season results (weeks 1-14)
2. **`postseason_standings.json`** - Postseason results (weeks 15-16)
3. **`mediocre_bowl_standings.json`** - Two-week cumulative results for bragging rights
4. **`final_standings.json`** - Combined standings with regular season as base

### **Standings Structure**

#### **Final Standings (Primary Output)**
```json
{
  "place": 6,                    // Final place (based on regular season)
  "team_id": "6",
  "team_name": "MONDAY Night MURDERERS",
  "regular_season_record": "7-7-0",
  "regular_season_points_for": 1217.0,
  "regular_season_points_against": 1325.1,
  "regular_season_win_pct": 0.5,
  "postseason_rank": 5,          // Postseason performance (1-12)
  "postseason_label": "Fifth Place",
  "postseason_points": 198.32,
  "week_15_points": 120.94,      // Individual week scores
  "week_16_points": 77.38,
  "mediocre_bowl_total": 198.32, // Two-week cumulative (for bragging rights)
  "playoff_participation": "mediocre_bowl"
}
```

#### **Key Features:**
- **Final placement based on regular season** (not postseason performance)
- **Postseason rank for bragging rights** (1-12)
- **Individual week scores** for detailed analysis
- **Mediocre bowl results** recorded separately
- **Playoff participation type** (championship_bracket, mediocre_bowl, consolation)

### **Example: 2013 Season Results**

```bash
# View final standings summary
python -c "
import json
data = json.load(open('data/processed/schedule/2013/final_standings.json'))
print('Place | Team | Regular Season | Postseason Rank')
print('------|------|---------------|-----------------')
for t in data[:8]:
    print(f'{t[\"place\"]:5} | {t[\"team_name\"]:20} | {t[\"regular_season_record\"]:13} | {t[\"postseason_rank\"]:15}')
"
```

**Output:**
```
Place | Team | Regular Season | Postseason Rank
------|------|---------------|-----------------
    1 | Charles in Charge    | 12-2-0        |               1
    2 | TA-VON-ME            | 11-3-0        |               3
    3 | For Whom Le'Veon Bell Tolls | 8-6-0         |               4
    4 | Colin The Shots      | 7-7-0         |               2
    5 | Marshall Law         | 7-7-0         |               8
    6 | MONDAY Night MURDERERS | 7-7-0         |               5
    7 | Bearing Down         | 6-8-0         |               7
    8 | Vincent's Brownies   | 6-8-0         |              10
```

### **Mediocre Bowl Results**

The mediocre bowl is for bragging rights only and doesn't affect final placement:

```bash
# For 2011-2017 (2-week format)
python -c "
import json
data = json.load(open('data/processed/schedule/2014/mediocre_bowl_standings.json'))
print('Place | Team | Week 15 | Week 16 | Total')
print('------|------|---------|---------|------')
for t in data:
    print(f'{t[\"place\"]:5} | {t[\"team_name\"]:20} | {t[\"week_15_points\"]:7.2f} | {t[\"week_16_points\"]:7.2f} | {t[\"total_points\"]:5.2f}')
"

# For 2018+ (3-week format)
python -c "
import json
data = json.load(open('data/processed/schedule/2018/mediocre_bowl_standings.json'))
print('Place | Team | Week 14 | Week 15 | Week 16 | Total')
print('------|------|---------|---------|---------|------')
for t in data:
    print(f'{t[\"place\"]:5} | {t[\"team_name\"]:20} | {t.get(\"week_14_points\", 0):7.2f} | {t[\"week_15_points\"]:7.2f} | {t[\"week_16_points\"]:7.2f} | {t[\"total_points\"]:5.2f}')
"
```

### **Processing Multiple Seasons**

```bash
# Process multiple seasons
for season in 2011 2012 2013 2014; do
    echo "Processing season $season..."
    python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.save_all_standings($season)"
done
```

### **Individual Standings Generation**

You can also generate individual standings files:

```bash
# Generate specific standings
python -c "
from src.ingest.nfl.schedule import NFLScheduleIngest
scraper = NFLScheduleIngest()

# Regular season only
scraper.save_regular_season_standings(2013)

# Postseason only  
scraper.save_postseason_standings(2013)

# Mediocre bowl only
scraper.save_mediocre_bowl_standings(2013)

# Final combined standings
scraper.save_final_standings(2013)
"
```

## 🎯 **Key Concepts**

### **Final Standings Philosophy**
- **Final placement is based on regular season performance** (weeks 1-14)
- **Postseason results are for bragging rights only** and don't affect final placement
- **Mediocre bowl is a separate competition** for teams that don't make the championship bracket

### **Data Flow**
1. **Schedule Scraping** → Raw game data from NFL Fantasy
2. **Playoff Annotation** → Mark games with playoff rounds
3. **Standings Generation** → Calculate regular season, postseason, and final standings
4. **JSON Output** → Structured data for analysis and display

### **Playoff Structure (2011-2017)**
- **Seeds 1-4**: Championship bracket (winner gets 1st, runner-up gets 2nd, etc.)
- **Seeds 5-8**: Mediocre bowl (two-week cumulative competition)
- **Seeds 9-12**: Consolation bracket (no additional games)

### **Example: Colin The Shots 2013**
- **Regular Season**: 4th place (7-7-0 record)
- **Postseason**: Runner Up (upset win in Round 1, lost championship game)
- **Final Standing**: 4th place (based on regular season)
- **Bragging Rights**: "Made it to the championship game!"

## 🔧 **Troubleshooting & Common Issues**

### **Error: "No schedule data found for season X"**
**Cause**: Schedule data hasn't been scraped yet for that season.

**Solution**: Run the complete process flow:
```bash
# 1. Scrape schedule data
python -m src.ingest.nfl.schedule --season 2014 --force-refresh

# 2. Annotate playoffs  
python src/scripts/playoff_annotator_fixed.py --season 2014

# 3. Generate standings
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.save_all_standings(2014)"
```

### **Error: "No playoff brackets found"**
**Cause**: Playoff brackets weren't generated during schedule scraping.

**Solution**: Re-run schedule scraper with force refresh:
```bash
python -m src.ingest.nfl.schedule --season 2014 --force-refresh
```

### **Error: "No annotated schedule found"**
**Cause**: Playoff annotation step was skipped.

**Solution**: Run the playoff annotator:
```bash
python src/scripts/playoff_annotator_fixed.py --season 2014
```

### **Individual Week Points Showing as 0.0**
**Cause**: Bug in standings generation (fixed in current version).

**Solution**: Regenerate standings with the latest code:
```bash
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.save_all_standings(2014)"
```

### **Missing Teams in Final Standings**
**Cause**: Incomplete schedule data or playoff annotation issues.

**Solution**: 
1. Check if all 12 teams are in the schedule data
2. Verify playoff annotation completed successfully
3. Regenerate all data from scratch

### **Validation Checklist**
After processing a season, verify:
- [ ] Schedule data exists: `data/processed/schedule/2014/schedule.csv`
- [ ] Playoff brackets exist: `data/processed/schedule/2014/playoff_brackets.json`
- [ ] Annotated schedule exists: `data/processed/schedule/2014/schedule_annotated.csv`
- [ ] All 4 standings files generated:
  - `regular_season_standings.json`
  - `postseason_standings.json`
  - `mediocre_bowl_standings.json`
  - `final_standings.json`
- [ ] Final standings contain all 12 teams
- [ ] Individual week points are populated (not 0.0)

## 🔧 **Corrected Process for Future Years**

### **Important: Schedule Data Validation**

When working with historical seasons (especially older ones like 2011), the scraped schedule data may not match the official playoff bracket structure. Here's the corrected process:

#### **Step 1: Scrape Schedule Data**
```bash
python -m src.ingest.nfl.schedule --season 2012 --force-refresh
```

#### **Step 2: Validate Week 16 Data**
After scraping, check if Week 16 data matches the official playoff bracket:

```bash
# Check the raw Week 16 data
cat data/raw/schedule/2012/week_16.json

# Compare with official NFL Fantasy site data
# If matchups/scores don't match, proceed to Step 3
```

#### **Step 3: Fix Week 16 Data (If Needed)**
If the scraped Week 16 data shows wrong matchups (e.g., consolation games instead of playoff games):

1. **Get official Week 16 scores** from the NFL Fantasy site
2. **Create corrected Week 16 data** with proper playoff matchups
3. **Replace the raw data** and re-run the scraper

```bash
# Example: Fix Week 16 data script
python fix_week16_schedule.py --season 2012 --official-scores "team1:score1,team2:score2,..."
```

#### **Step 4: Regenerate Schedule**
```bash
# Re-run scraper with corrected data
python -m src.ingest.nfl.schedule --season 2012 --force-refresh
```

#### **Step 5: Annotate with Playoff Information**
```bash
# Use the fixed annotator
python src/playoff_annotator_fixed.py --season 2012
```

### **Common Issues & Solutions**

#### **Issue: Wrong Week 16 Matchups**
- **Symptom**: Schedule shows consolation games instead of championship/third place games
- **Cause**: NFL Fantasy site shows different bracket structure for older seasons
- **Solution**: Manually correct Week 16 data with official scores

#### **Issue: Incorrect Playoff Annotations**
- **Symptom**: Championship game marked as "Third Place" or "Toilet Bowl"
- **Cause**: Using wrong bracket file (`playoff_brackets.json` instead of `playoff_bracket_complete.json`)
- **Solution**: Use `playoff_annotator_fixed.py` which uses the correct bracket file

#### **Issue: Missing Playoff Games**
- **Symptom**: Some playoff games not annotated
- **Cause**: Game ID mismatch between bracket and schedule
- **Solution**: Check game IDs in both files and update the annotator logic

### **Validation Checklist**

After completing the process, verify:

- [ ] Week 16 matchups match official NFL Fantasy site
- [ ] Championship game correctly annotated as "Championship"
- [ ] Third place game correctly annotated as "Third Place"
- [ ] All playoff games have correct scores
- [ ] Regular season standings are accurate
- [ ] Playoff bracket structure is correct

### **Example: 2012 Season Process**

```bash
# 1. Scrape schedule
python -m src.ingest.nfl.schedule --season 2012 --force-refresh

# 2. Check Week 16 data
cat data/raw/schedule/2012/week_16.json

# 3. If data is correct, annotate playoffs
python src/playoff_annotator_fixed.py --season 2012

# 4. Validate results
grep "16" data/processed/schedule/2012/schedule_annotated.csv
```

## 🧪 **Testing & Validation**

### **Quick Testing Commands**

#### **1. Schedule Validation Test**
Test the robust scraper with schedule validation:
```bash
# Test 2013 Week 1 (validates reconstructed scores vs schedule scores)
python src/schedule_validator.py --season 2013 --week 1 --force-refresh

# Test 2014 Week 1 (cross-season validation)
python src/schedule_validator.py --season 2014 --week 1 --force-refresh
```

**Expected Output:**
- ✅ All games validated successfully (100% validation rate)
- Complete player extraction (13 offense + 1 kicker + 1 defense = 15 players per team)
- Robust table detection across all 3 table types

#### **2. Manager Tracking Test**
Test team manager tracking with real manager data:
```bash
# Generate manager data for 2011-2012
python src/cli.py analyze team-managers --seasons 2011 2012

# View manager summary
python -c "
from src.team_manager_tracker import TeamManagerTracker
tracker = TeamManagerTracker()
data = tracker.generate_team_manager_data([2011, 2012])
tracker.print_manager_summary(data)
"
```

**Expected Output:**
- Manager profiles with career stats
- Season-by-season breakdown
- Playoff results and championships

#### **3. Enhanced Analysis Test**
Test detailed player stats integration:
```bash
# Generate enhanced analysis (may take time)
python src/cli.py analyze enhanced --seasons 2012

# Quick test with smaller dataset
python -c "
from src.enhanced_team_analyzer import EnhancedTeamAnalyzer
analyzer = EnhancedTeamAnalyzer()
data = analyzer.enhance_manager_data([2012])
analyzer.print_enhanced_summary(data)
"
```

### **End-to-End Pipeline Test**

#### **Complete Season Processing**
```bash
# 1. Scrape schedule data
python -m src.ingest.nfl.schedule --season 2013 --force-refresh

# 2. Validate schedule scores
python src/schedule_validator.py --season 2013 --week 1 --force-refresh

# 3. Generate manager tracking
python src/cli.py analyze team-managers --seasons 2013

# 4. Enhanced analysis (optional)
python src/cli.py analyze enhanced --seasons 2013
```

### **Data Quality Validation**

#### **Check Extracted Data**
```bash
# Verify player data completeness
python -c "
import json
from pathlib import Path

# Check 2013 Week 1 data
team_file = Path('data/raw/2013/week_01/team_1.json')
if team_file.exists():
    with open(team_file, 'r') as f:
        data = json.load(f)
    
    print(f'Total players: {len(data["players"])}')
    positions = [p.get('position') for p in data['players']]
    print(f'Positions: {set(positions)}')
    starters = [p for p in data['players'] if p.get('lineup_status') == 'starter']
    print(f'Starters: {len(starters)}')
    print(f'Bench: {len(data["players"]) - len(starters)}')
"
```

#### **Verify Manager Data**
```bash
# Check manager mapping accuracy
python -c "
import json
from pathlib import Path

# Load 2012 manager data
manager_file = Path('data/processed/schedule/2012/managers.json')
if manager_file.exists():
    with open(manager_file, 'r') as f:
        managers = json.load(f)
    
    print('=== 2012 Manager Data ===')
    print(f'Total managers: {len(managers)}')
    for team_id, data in managers.items():
        print(f'Team {team_id}: {data["manager_name"]} ({data["team_name"]})')
"
```

### **Performance Testing**

#### **Speed Test**
```bash
# Test scraper performance
time python src/schedule_validator.py --season 2013 --week 1 --force-refresh

# Expected: ~30-60 seconds for 12 teams with robust extraction
```

#### **Robustness Test**
```bash
# Test across multiple seasons
for season in 2011 2012 2013 2014; do
    echo "Testing season $season..."
    python src/schedule_validator.py --season $season --week 1 --force-refresh
done
```

### **Validation Checklist**

After running tests, verify:

- [ ] **Schedule Validation**: 100% validation rate (reconstructed scores match schedule)
- [ ] **Player Extraction**: 15 players per team (13 offense + 1 kicker + 1 defense)
- [ ] **Manager Tracking**: Accurate manager names and team associations
- [ ] **Data Completeness**: All teams processed successfully
- [ ] **Performance**: Reasonable processing time (< 2 minutes for 12 teams)
- [ ] **Cross-Season**: Works consistently across multiple seasons

### **Troubleshooting**

#### **Common Issues**

1. **"No player data extracted"**
   - Check if NFL Fantasy site structure changed
   - Verify league_id and team_id are correct
   - Try with `--force-refresh` flag

2. **"Validation failed"**
   - Check if schedule data is accurate
   - Verify reconstructed scores include all player types
   - Check for scoring rule differences

3. **"Manager data missing"**
   - Ensure schedule scraper ran successfully
   - Check if manager mapping files exist
   - Verify season data is complete

#### **Debug Mode**
```bash
# Enable verbose output for debugging
python src/schedule_validator.py --season 2013 --week 1 --force-refresh 2>&1 | tee debug.log
```

---

An enhanced web scraping client for NFL Fantasy Football data with improved configuration management, error handling, data validation, and performance optimizations.

## Features

### 🚀 **Performance & Scalability**
- **Concurrent scraping** with configurable thread pools
- **Connection pooling** to manage multiple webdriver instances
- **Rate limiting** with configurable requests per minute/second
- **Automatic retry logic** with exponential backoff
- **Caching system** to avoid redundant requests

### ⚙️ **Configuration Management**
- **Environment variable support** for all settings
- **Centralized configuration** with validation
- **Flexible configuration** for different environments
- **Default settings** that work out of the box

### 🛡️ **Error Handling & Resilience**
- **Comprehensive exception handling** with custom error types
- **Retry mechanisms** for transient failures
- **Graceful degradation** when services are unavailable
- **Detailed logging** for debugging and monitoring

### 📊 **Data Quality & Validation**
- **Data validation** with comprehensive checks
- **Data cleaning** and normalization
- **Quality reporting** with metrics and issues
- **Consistency validation** for unrealistic values

### 🔧 **Developer Experience**
- **Type hints** throughout the codebase
- **Comprehensive documentation** and examples
- **Modular design** for easy extension
- **Context managers** for resource management

## Quick Start

### Basic Usage

```python
from src.ingest.nfl.api_client import NFLFantasyScraper, ScraperConfig

# Create scraper with default configuration
config = ScraperConfig(headless=True, cache_enabled=True)
with NFLFantasyScraper(config) as scraper:
    data = scraper.get_team_data("864504", "1", 2012, 15)
    if data:
        print(f"Extracted {len(data['players'])} players")
```

### Advanced Usage with Validation

```python
from src.ingest.nfl.api_client import NFLFantasyScraper
from src.ingest.nfl.validators import DataValidator, DataQualityReport

config = ScraperConfig(headless=True, cache_enabled=True)
with NFLFantasyScraper(config) as scraper:
    # Fetch data
    raw_data = scraper.get_team_data("864504", "1", 2012, 15)
    
    # Validate and clean data
    validation_result = DataValidator.validate_team_data(raw_data)
    if validation_result.is_valid:
        cleaned_data = validation_result.cleaned_data
        
        # Generate quality report
        quality_report = DataQualityReport.generate_team_report(cleaned_data)
        DataQualityReport.print_report(quality_report)
```

### Concurrent Scraping

```python
config = ScraperConfig(max_workers=4)
with NFLFantasyScraper(config) as scraper:
    team_ids = ["1", "2", "3", "4", "5"]
    results = scraper.get_multiple_teams("864504", team_ids, 2012, 15)
    
    for team_id, data in results.items():
        if data:
            print(f"Team {team_id}: {len(data['players'])} players")
```

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# API Settings
NFL_BASE_URL=https://fantasy.nfl.com
NFL_HEADLESS=true
NFL_TIMEOUT=30
NFL_WAIT_TIME=10

# Performance
NFL_MAX_RETRIES=3
NFL_MAX_WORKERS=4
NFL_REQUESTS_PER_MINUTE=30
NFL_MIN_DELAY=1.0

# Caching
NFL_CACHE_ENABLED=true
NFL_CACHE_EXPIRY_HOURS=24

# Data
NFL_DATA_DIR=data
NFL_LEAGUE_ID=864504
NFL_DEFAULT_SEASON=2023

# Logging
NFL_LOG_LEVEL=INFO
NFL_LOG_FILE=logs/nfl_scraper.log
```

### Configuration Classes

```python
from src.ingest.nfl.config import create_config

# Create custom configuration
config = create_config(
    headless=False,  # Show browser for debugging
    timeout=45,
    max_retries=5,
    requests_per_minute=20,  # More conservative
    log_level="DEBUG"
)
```

## Data Validation

The client includes comprehensive data validation:

### Player Data Validation
- **Required fields**: name, position
- **Position validation**: QB, RB, WR, TE, K, DEF, etc.
- **NFL team validation**: Standard 3-letter abbreviations
- **Numeric field validation**: Yards, touchdowns, fantasy points
- **Data consistency checks**: Unrealistic values flagged

### Team Data Validation
- **Structure validation**: Required 'players' list
- **Player validation**: Each player validated individually
- **Metadata tracking**: Validation timestamps and statistics

### Quality Reporting

```python
from src.ingest.nfl.validators import DataQualityReport

# Generate comprehensive quality report
report = DataQualityReport.generate_team_report(team_data)
DataQualityReport.print_report(report)
```

Example output:
```
=== DATA QUALITY REPORT ===
Generated: 2024-01-15T10:30:00
Total Players: 15

--- Data Quality Metrics ---
Players with names: 15/15
Players with positions: 15/15
Players with NFL teams: 15/15
Players with fantasy points: 15/15
Average fantasy points: 12.45
Total fantasy points: 186.75

--- No Issues Found ---
```

## Rate Limiting & Performance

### Rate Limiting Configuration

```python
from src.ingest.nfl.rate_limiter import RateLimitConfig, ScrapingSession

# Conservative rate limiting
rate_config = RateLimitConfig(
    requests_per_minute=10,
    requests_per_second=1,
    min_delay_between_requests=2.0,
    max_delay_between_requests=5.0,
    jitter_factor=0.1  # Add randomness
)

# Create session with rate limiting
session = ScrapingSession(rate_config, max_connections=2, max_retries=3)
```

### Session Management

```python
# Execute requests with rate limiting
def scrape_team(team_id):
    return scraper.get_team_data(league_id, team_id, season, week)

results = {}
for team_id in team_ids:
    data = session.execute_request(scrape_team, team_id)
    results[team_id] = data

# Print session summary
session.print_session_summary()
```

## Error Handling

### Custom Exception Types

```python
from src.ingest.nfl.api_client import ScraperError, ConfigurationError, DataExtractionError

try:
    data = scraper.get_team_data(league_id, team_id, season, week)
except ConfigurationError as e:
    print(f"Configuration error: {e}")
except DataExtractionError as e:
    print(f"Data extraction failed: {e}")
except ScraperError as e:
    print(f"General scraping error: {e}")
```

### Retry Logic

The client includes automatic retry logic with exponential backoff:

```python
# Configure retry behavior
config = ScraperConfig(
    max_retries=3,
    retry_delay=2.0
)

# Retries happen automatically for:
# - Network timeouts
# - Page load failures
# - Data extraction errors
# - Temporary server errors
```

## Caching

### Cache Management

```python
# Enable/disable caching
config = ScraperConfig(cache_enabled=True)

# Force refresh (ignore cache)
data = scraper.get_team_data(league_id, team_id, season, week, force_refresh=True)

# Cache location: data/raw/{season}/week_{week:02d}/team_{team_id}.json
```

### Cache Structure

```json
{
  "players": [...],
  "source": "html_scraping",
  "metadata": {
    "league_id": "864504",
    "team_id": "1",
    "season": 2012,
    "week": 15,
    "extracted_at": 1705312200.123,
    "player_count": 15
  }
}
```

## Logging

### Logging Configuration

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Different log levels available:
# - DEBUG: Detailed debugging information
# - INFO: General information about scraping progress
# - WARNING: Issues that don't prevent operation
# - ERROR: Errors that prevent successful scraping
```

### Log Output Example

```
2024-01-15 10:30:00,123 - nfl.api_client - INFO - Initialized NFL Fantasy Scraper
2024-01-15 10:30:01,456 - nfl.api_client - INFO - Fetching data for League 864504, Team 1, 2012 Week 15
2024-01-15 10:30:05,789 - nfl.api_client - INFO - Found player table using selector: table.tableType-player
2024-01-15 10:30:06,012 - nfl.api_client - INFO - Successfully extracted 15 players
```

## Examples

See `example_usage.py` for comprehensive examples including:

- Basic usage patterns
- Advanced configuration
- Data validation workflows
- Rate limiting and session management
- Batch processing
- Error handling scenarios

## Architecture

### Module Structure

```
src/ingest/nfl/
├── api_client.py      # Main scraper class
├── config.py          # Configuration management
├── validators.py      # Data validation and quality
├── rate_limiter.py    # Rate limiting and sessions
├── example_usage.py   # Usage examples
├── schedule.py        # Schedule scraping (existing)
├── edit_roster.py     # Roster editing (existing)
└── README.md          # This file
```

### Key Classes

- **`NFLFantasyScraper`**: Main scraping class with context manager support
- **`ScraperConfig`**: Configuration for scraper behavior
- **`NFLConfig`**: Extended configuration with environment variable support
- **`DataValidator`**: Data validation and cleaning
- **`DataQualityReport`**: Quality reporting and metrics
- **`RateLimiter`**: Rate limiting implementation
- **`ScrapingSession`**: Session management with rate limiting
- **`PlayerData`**: Structured player data representation

## Best Practices

### 1. **Use Context Managers**
```python
# Always use context manager for proper cleanup
with NFLFantasyScraper(config) as scraper:
    data = scraper.get_team_data(league_id, team_id, season, week)
```

### 2. **Enable Caching**
```python
# Use caching to avoid redundant requests
config = ScraperConfig(cache_enabled=True)
```

### 3. **Validate Data**
```python
# Always validate scraped data
validation_result = DataValidator.validate_team_data(raw_data)
if not validation_result.is_valid:
    # Handle validation errors
```

### 4. **Respect Rate Limits**
```python
# Use conservative rate limiting for production
rate_config = RateLimitConfig(requests_per_minute=20)
session = ScrapingSession(rate_config)
```

### 5. **Handle Errors Gracefully**
```python
try:
    data = scraper.get_team_data(league_id, team_id, season, week)
except ScraperError as e:
    logger.error(f"Scraping failed: {e}")
    # Implement fallback logic
```

## Troubleshooting

### Common Issues

1. **"No player table found"**
   - Check if the page structure has changed
   - Try increasing `wait_time` in configuration
   - Verify league_id and team_id are correct

2. **"WebDriver initialization failed"**
   - Ensure Chrome/Chromium is installed
   - Check ChromeDriver compatibility
   - Try running with `headless=False` for debugging

3. **"Rate limit exceeded"**
   - Reduce `requests_per_minute` in configuration
   - Increase delays between requests
   - Use session management for better control

4. **"Data validation failed"**
   - Check raw HTML output in debug files
   - Verify page structure hasn't changed
   - Review validation errors for specific issues

### Debug Mode

```python
# Enable debug mode for troubleshooting
config = ScraperConfig(
    headless=False,  # Show browser
    timeout=60,      # Longer timeout
    log_level="DEBUG"
)

# Debug files are saved to:
# - data/raw/{season}/week_{week:02d}/team_{team_id}_full_page.html
# - data/raw/debug_table.html
```

## Contributing

When contributing to this project:

1. **Follow the existing code style** and patterns
2. **Add type hints** to all new functions
3. **Include comprehensive tests** for new features
4. **Update documentation** for any API changes
5. **Use the validation system** for data quality
6. **Respect rate limits** in your implementations

## License

This project is part of the Stag League Site and follows the same licensing terms.

## 📚 What's Next?

After ingesting schedule and results data, check out the `docs/` folder for:

- **`architecture.md`**: System/data model overview and pipeline architecture
- **`documentation.md`**: API/data usage, CLI commands, and environment setup
- **`milestones.md`**: Project roadmap, completed phases, and next development steps
- **`playoff_structure.md`**: Details on playoff logic and formats
- **`scripts.md`**: Example scripts and advanced usage

These docs will guide you through transforming, analyzing, and extending the ingested data, as well as contributing to the project!

## ⚡ **Quick Reference**

### **Most Common Commands**

#### **Process a New Season (Complete Flow)**
```bash
# Replace 2014 with your target season
SEASON=2014

# Step 1: Scrape schedule
python -m src.ingest.nfl.schedule --season $SEASON --force-refresh

# Step 2: Annotate playoffs
python src/scripts/playoff_annotator_fixed.py --season $SEASON

# Step 3: Generate standings (includes mediocre bowl automation for 2018+)
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.save_all_standings($SEASON)"
```

#### **Mediocre Bowl Automation (2018+)**
```bash
# Automatically inject mediocre bowl games with real scores
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.inject_mediocre_bowl_games(2018)"

# View mediocre bowl results
python -c "
import json
data = json.load(open('data/processed/schedule/2018/mediocre_bowl_standings.json'))
print('Place | Team | Week 14 | Week 15 | Week 16 | Total')
print('------|------|---------|---------|---------|------')
for t in data:
    print(f'{t[\"place\"]:5} | {t[\"team_name\"]:20} | {t.get(\"week_14_points\", 0):7.2f} | {t[\"week_15_points\"]:7.2f} | {t[\"week_16_points\"]:7.2f} | {t[\"total_points\"]:5.2f}')
"
```

#### **Regenerate Standings Only (If Data Already Exists)**
```bash
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.save_all_standings(2014)"
```

#### **View Final Standings Summary**
```bash
python -c "
import json
data = json.load(open('data/processed/schedule/2014/final_standings.json'))
print('Place | Team | Regular Season | Postseason Rank')
print('------|------|---------------|-----------------')
for t in data:
    print(f'{t[\"place\"]:5} | {t[\"team_name\"]:20} | {t[\"regular_season_record\"]:13} | {t[\"postseason_rank\"]:15}')
"
```

#### **View Mediocre Bowl Results**
```bash
# For 2011-2017 (2-week format)
python -c "
import json
data = json.load(open('data/processed/schedule/2014/mediocre_bowl_standings.json'))
print('Place | Team | Week 15 | Week 16 | Total')
print('------|------|---------|---------|------')
for t in data:
    print(f'{t[\"place\"]:5} | {t[\"team_name\"]:20} | {t[\"week_15_points\"]:7.2f} | {t[\"week_16_points\"]:7.2f} | {t[\"total_points\"]:5.2f}')
"

# For 2018+ (3-week format)
python -c "
import json
data = json.load(open('data/processed/schedule/2018/mediocre_bowl_standings.json'))
print('Place | Team | Week 14 | Week 15 | Week 16 | Total')
print('------|------|---------|---------|---------|------')
for t in data:
    print(f'{t[\"place\"]:5} | {t[\"team_name\"]:20} | {t.get(\"week_14_points\", 0):7.2f} | {t[\"week_15_points\"]:7.2f} | {t[\"week_16_points\"]:7.2f} | {t[\"total_points\"]:5.2f}')
"
```

#### **Process Multiple Seasons**
```bash
for season in 2011 2012 2013 2014; do
    echo "Processing season $season..."
    python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.save_all_standings($season)"
done
```

### **File Locations**
- **Schedule Data**: `data/processed/schedule/{season}/schedule.csv`
- **Playoff Brackets**: `data/processed/schedule/{season}/playoff_brackets.json`
- **Annotated Schedule**: `data/processed/schedule/{season}/schedule_annotated.csv`
- **Final Standings**: `data/processed/schedule/{season}/final_standings.json`
- **Mediocre Bowl**: `data/processed/schedule/{season}/mediocre_bowl_standings.json`

## 🔧 **Troubleshooting & Common Issues**

### **Toilet Bowl Games as Real Games**

The system now treats toilet bowl games as real games in the schedule with a flag to distinguish them from actual NFL Fantasy games:

#### **Schedule Structure with Simulation Flag**

The schedule CSV now includes two new columns:
- **`is_simulated`**: Boolean flag indicating if the game is simulated (True) or real (False)
- **`simulation_type`**: Type of simulation (e.g., "toilet_bowl", None for real games)

#### **Injecting Toilet Bowl Games**

After generating playoff brackets, inject the simulated toilet bowl games into the schedule:

```bash
# Inject toilet bowl games into schedule
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.inject_toilet_bowl_games(2014)"
```

This creates schedule entries for toilet bowl games with:
- **Week 15**: First round of toilet bowl (consolation teams play each other)
- **Week 16**: Toilet bowl championship (losers advance to crown the biggest loser)
- **Simulated scores**: Based on the playoff bracket generation logic
- **Proper annotation**: Games are marked as "toilet_bowl" in playoff rounds

#### **Complete Process with Toilet Bowl**

```bash
# 1. Scrape schedule data
python -m src.ingest.nfl.schedule --season 2014 --force-refresh

# 2. Inject toilet bowl games
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.inject_toilet_bowl_games(2014)"

# 3. Annotate playoffs (includes toilet bowl games)
python src/scripts/playoff_annotator_fixed.py --season 2014

# 4. Generate standings (includes toilet bowl results)
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; scraper = NFLScheduleIngest(); scraper.save_all_standings(2014)"
```

#### **Example: 2014 Toilet Bowl Results**

```bash
# View toilet bowl games in schedule
python -c "
import csv
games = list(csv.DictReader(open('data/processed/schedule/2014/schedule_annotated.csv')))
toilet_games = [g for g in games if g.get('playoff_round') == 'toilet_bowl']
print('Toilet Bowl Games:')
for g in toilet_games:
    print(f'Week {g[\"week\"]}: {g[\"home_team\"]} vs {g[\"away_team\"]} - {g[\"home_points\"]} to {g[\"away_points\"]}')
"
```

**Output:**
```
Toilet Bowl Games:
Week 15: The Watkins Diet vs Taco's Bell - 85.0 to 75.0
Week 15: The Real McCoy vs Cloudy With A Chance of Montee - 82.0 to 78.0
Week 16: Taco's Bell vs Cloudy With A Chance of Montee - 70.0 to 75.0
Week 16: The Watkins Diet vs The Real McCoy - 88.0 to 85.0
```

#### **Toilet Bowl Championship Logic**

The toilet bowl follows a "losers advance" format:
- **Week 15**: Consolation teams (seeds 9-12) play each other
- **Week 16**: Losers from Week 15 play each other to crown the biggest loser
- **Winner**: The team with the lowest total points over both weeks
- **Result**: Taco's Bell becomes the ultimate loser with 145 total points

#### **Benefits of Real Game Treatment**

1. **Consistent Data Structure**: All games (real and simulated) use the same format
2. **Proper Annotation**: Toilet bowl games are correctly marked in playoff rounds
3. **Complete Standings**: Postseason standings include all teams with proper rankings
4. **Analysis Ready**: Games can be analyzed alongside real games with the simulation flag
5. **Historical Tracking**: Toilet bowl results are preserved in the schedule data

## 🏆 **Standings Processing Guide**

