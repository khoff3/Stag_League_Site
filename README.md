# Stag_League_Site
The backend and front end for a exploratory league site for the Stag Brotherhood

## 🏗️ **New Folder Structure (Updated 2024)**

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

## 🚀 **Quick Start**

### **Complete Pipeline (Recommended)**
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

## 📊 **Recent Progress (2024)**

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

## 📋 **Documentation**

- **📋 [Scripts & Debugging](docs/scripts.md)** - Complete pipeline documentation and debugging procedures
- **🚨 [Debugging Quick Reference](docs/debugging_quick_reference.md)** - Critical issues checklist and common fixes
- **🏗️ [Architecture](docs/architecture.md)** - System design and data flow
- **📊 [Data Integration](docs/data_join_guide.md)** - How to join different data sources
- **🏆 [Playoff Integration](docs/playoff_integration.md)** - Playoff bracket and standings generation
- **👥 [Manager Tracking](docs/team_manager_tracking.md)** - Manager analysis and career statistics
- **🎯 [Recent Progress 2024](docs/recent_progress_2024.md)** - **NEW**: Summary of latest improvements and features

## 🎯 **Key Features**

### **Data Ingestion**
- **Schedule scraping** with playoff detection
- **Draft data extraction** with player IDs
- **Manager name mapping** across seasons
- **Player statistics** via optimized API client

### **Analysis & Processing**
- **Comprehensive manager tracking** with career stats
- **Enhanced team analysis** with detailed metrics
- **Playoff bracket construction** with proper seeding
- **Data validation** and cross-checking

### **Utilities**
- **Schedule validation** and error detection
- **Playoff score analysis** and bracket generation
- **Data cleaning** and duplicate removal
- **Pipeline automation** scripts

## 🔧 **Quality Assurance**

Before running any season pipeline, verify these critical components:

1. **Team Sorting Logic** - Ensure teams are sorted by win percentage, not points
2. **Playoff Bracket Assignment** - Verify middle teams (seeds 7-8) are correct
3. **Mediocre Bowl Games Injection** - Must use playoff bracket teams, not regular season
4. **Playoff Annotation** - Should detect mediocre bowl games for 2018+ seasons

See [Debugging Quick Reference](docs/debugging_quick_reference.md) for detailed validation steps.

## 📈 **Usage Examples**

### **Generate Manager Statistics**
```bash
# Run comprehensive manager analysis
python src/scripts/data_processing/comprehensive_manager_tracker.py

# Check results
cat data/processed/comprehensive_manager_history.json | jq '.managers | keys'
```

### **Extract Draft Data**
```bash
# Extract draft data for multiple seasons
for year in 2011 2012 2020 2021; do
    python src/ingest/nfl/draft_scraper.py --season $year
done
```

### **Validate Data**
```bash
# Validate schedule data
python src/scripts/utilities/schedule_validator.py --season 2021

# Check playoff brackets
cat data/processed/schedule/2021/playoff_brackets.json | jq '.'
```

## 🎯 **To Do**
- Expand https://github.com/hvpkod/NFL-Data/tree/main/NFL-data-Players
- Merge NFL DF with Sleeper
- Playoff detection enhancement
- **Web interface** for manager statistics
- **Advanced analytics** and visualization
