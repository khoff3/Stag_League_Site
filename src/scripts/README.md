# Stag League Scripts

This directory contains utility scripts for the Stag League History project.

## 🏈 Project Overview

A comprehensive fantasy football league analysis and visualization platform for the Stag Brotherhood fantasy football league, providing a complete data pipeline for analyzing fantasy football league data from NFL.com.

## 📊 Current Status

### ✅ **Production Ready Features**
- **Complete data pipeline** for seasons 2011-2020
- **Automatic playoff bracket generation** with proper seeding
- **Postseason standings** with correct 5th/6th place game handling
- **Toilet Bowl bracket tracking** with proper 9th-12th place assignments
- **Mediocre Bowl and Toilet Bowl** tracking
- **Enhanced team analysis** with player-level statistics
- **Data validation** with cross-checking of scores and standings

### 🎯 **Recent Fixes (December 2024)**
- **✅ 5th/6th place game logic** - Fixed for 2018+ seasons
- **✅ Playoff bracket generation** - Corrected seeding and categorization
- **✅ Postseason standings** - Now reflects actual playoff results
- **✅ Toilet Bowl bracket tracking** - Proper 2-week tournament progression
- **✅ Team sorting** - Added points scored as tiebreaker

## 📁 Scripts Overview

### Core Scripts
- **`complete_pipeline.sh`** - Complete end-to-end pipeline for a season
- **`quick_test.py`** - Quick validation tests for schedule and manager data
- **`playoff_annotator_fixed.py`** - Annotates schedule with playoff information
- **`playoff_schedule_constructor.py`** - Constructs playoff brackets and schedules
- **`manager_name_scraper.py`** - Scrapes and tracks team manager names

### Testing Scripts
- **`test_schedule_scraper.py`** - Comprehensive schedule scraper tests
- **`test_simple.py`** - Basic functionality tests

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Virtual environment (recommended)
- Access to NFL.com fantasy league data

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd Stag_League_Site

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Complete Pipeline Usage
```bash
# Run complete pipeline for a season (recommended)
bash src/scripts/complete_pipeline.sh 2020

# Or run individual components
python -m src.scripts.complete_pipeline 2020
```

### Individual Component Usage
```bash
# Data ingestion only
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; processor = NFLScheduleIngest(); processor.fetch_and_process_season(2020)"

# Playoff bracket generation
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; processor = NFLScheduleIngest(); processor.generate_playoff_brackets(2020)"

# Toilet bowl injection (2018+)
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; processor = NFLScheduleIngest(); processor.inject_toilet_bowl_games(2020)"

# Postseason standings generation
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; processor = NFLScheduleIngest(); processor.save_postseason_standings(2020)"

# Final standings generation
python -c "from src.ingest.nfl.schedule import NFLScheduleIngest; processor = NFLScheduleIngest(); processor.save_final_standings(2020)"
```

## 🏆 Playoff System Documentation

### **2018+ Format (6-Team Championship Bracket)**
- **Week 14 (Round 1)**: Seeds 3v6, 4v5 - losers play 5th/6th place game
- **Week 15 (Semifinals)**: Winners of round 1 vs seeds 1-2
- **Week 16 (Championship)**: Championship, 3rd place, and 5th place games

### **Toilet Bowl Bracket (2018+)**
- **Week 14 (First Round)**: Seeds 9v12, 10v11
- **Week 15 (Semifinals)**: Winners vs winners, losers vs losers
- **Week 16 (Finals)**: Championship game (9th/10th) and 3rd place game (11th/12th)

### **Mediocre Bowl (2018+)**
- **Teams**: 7th and 8th place from regular season
- **Format**: 3-week total points competition
- **Winner**: Team with highest combined points from weeks 14-16

## 📁 Project Structure

```
src/scripts/
├── complete_pipeline.sh          # Main pipeline script
├── complete_pipeline.py          # Python pipeline runner
├── playoff_annotator_fixed.py    # Playoff game annotation
├── schedule_validator.py         # Data validation
├── team_manager_tracker.py       # Manager analysis
└── enhanced_team_analyzer.py     # Enhanced statistics
```

## 🔧 Pipeline Components

### **Phase 1: Data Ingestion**
- Scrapes NFL.com fantasy league data
- Processes weekly schedules and team records
- Generates regular season standings

### **Phase 2: Playoff Annotation**
- Identifies playoff games from schedule
- Annotates games with playoff rounds
- Generates playoff brackets

### **Phase 3: Data Validation**
- Cross-validates scores with detailed player data
- Ensures data accuracy and completeness
- Reports validation statistics

### **Phase 4: Analysis**
- Generates team manager statistics
- Creates enhanced team analysis
- Tracks manager career performance

### **Phase 5: Validation Testing**
- Runs comprehensive system tests
- Validates playoff bracket logic
- Ensures data integrity

## 📊 Output Files

### **Generated for Each Season:**
- `schedule.csv` - Complete season schedule
- `schedule_annotated.csv` - Schedule with playoff annotations
- `playoff_brackets.json` - Playoff bracket structure
- `regular_season_standings.json` - Regular season results
- `postseason_standings.json` - Playoff results
- `final_standings.json` - Combined final standings
- `mediocre_bowl_standings.json` - Mediocre bowl results

### **Global Analysis Files:**
- `team_managers.json` - Manager career statistics
- `enhanced_team_analysis.json` - Detailed team performance

## 🎯 Usage Examples

### **Process a Single Season**
```bash
# Complete pipeline (recommended)
bash src/scripts/complete_pipeline.sh 2020

# Check results
ls data/processed/schedule/2020/
cat data/processed/schedule/2020/final_standings.json
```

### **Validate Data**
```bash
# Validate specific week
python src/schedule_validator.py --season 2020 --week 15

# Validate entire season
python src/schedule_validator.py --season 2020
```

### **Generate Analysis**
```bash
# Team manager analysis
python -m src.scripts.team_manager_tracker 2020

# Enhanced analysis
python -m src.scripts.enhanced_team_analyzer 2020
```

## 🐛 Troubleshooting

### **Common Issues**
1. **Connection errors**: NFL.com rate limiting - wait and retry
2. **Missing data**: Check if season exists in league history
3. **Playoff structure errors**: Verify season format (pre-2018 vs 2018+)

### **Debug Mode**
```bash
# Enable debug output
export DEBUG=1
bash src/scripts/complete_pipeline.sh 2020
```

## 📈 Performance Notes

- **Data ingestion**: ~2-3 minutes per season
- **Validation**: ~1-2 minutes per week
- **Analysis**: ~30-60 seconds per season
- **Complete pipeline**: ~5-10 minutes per season

## 🤝 Contributing

1. Test changes on multiple seasons (2018, 2019, 2020)
2. Validate playoff bracket logic
3. Ensure toilet bowl and mediocre bowl work correctly
4. Update documentation for any new features

## 📝 Notes

- **2018+ seasons**: Use 6-team championship bracket with toilet bowl
- **Pre-2018 seasons**: Use legacy playoff formats
- **Toilet Bowl**: Properly tracks 2-week tournament progression
- **Mediocre Bowl**: 3-week total points competition for 7th/8th place teams

---

**Last Updated**: December 2024  
**Status**: Production Ready for 2011-2020 seasons 