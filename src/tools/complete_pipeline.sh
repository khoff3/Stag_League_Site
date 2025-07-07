#!/bin/bash
# Complete Pipeline with Playoff Integration
# Usage: ./complete_pipeline.sh <season>

set -e  # Exit on any error

SEASON=$1

if [ -z "$SEASON" ]; then
    echo "Usage: ./complete_pipeline.sh <season>"
    echo "Example: ./complete_pipeline.sh 2012"
    exit 1
fi

echo "🏈 Stag League Complete Pipeline - Season $SEASON"
echo "=================================================="

# Phase 1: Data Ingestion
echo ""
echo "📥 Phase 1: Data Ingestion"
echo "---------------------------"
echo "Scraping schedule data and playoff brackets..."
python src/cli.py ingest schedule --season $SEASON --force-refresh

# Check if schedule was created
if [ ! -f "data/processed/schedule/$SEASON/schedule.csv" ]; then
    echo "❌ Error: Schedule data not found. Check if scraping completed successfully."
    exit 1
fi

echo "✅ Schedule data ingested successfully"

# Phase 2: Playoff Annotation
echo ""
echo "🏆 Phase 2: Playoff Annotation"
echo "-------------------------------"
echo "Annotating schedule with playoff information..."
python src/cli.py annotate playoff --season $SEASON

# Check if annotated schedule was created
if [ ! -f "data/processed/schedule/$SEASON/schedule_annotated.csv" ]; then
    echo "❌ Error: Annotated schedule not found. Check playoff annotation."
    exit 1
fi

echo "✅ Playoff annotation completed"

# Phase 3: Data Validation
echo ""
echo "🔍 Phase 3: Data Validation"
echo "----------------------------"
echo "Validating regular season data..."
python src/schedule_validator.py --season $SEASON --week 1 --force-refresh

echo "Validating playoff data..."
python src/schedule_validator.py --season $SEASON --week 15 --force-refresh

echo "✅ Data validation completed"

# Phase 4: Analysis
echo ""
echo "📊 Phase 4: Analysis"
echo "--------------------"
echo "Generating team manager analysis..."
python src/cli.py analyze team-managers --seasons $SEASON

echo "Generating enhanced analysis..."
python src/cli.py analyze enhanced --seasons $SEASON

echo "✅ Analysis completed"

# Phase 5: Testing
echo ""
echo "🧪 Phase 5: Validation Testing"
echo "------------------------------"
echo "Running comprehensive tests..."
python src/cli.py test full

echo "✅ Testing completed"

# Phase 6: Summary Report
echo ""
echo "📋 Phase 6: Summary Report"
echo "---------------------------"

# Count files created
SCHEDULE_FILES=$(find data/processed/schedule/$SEASON -name "*.csv" -o -name "*.json" | wc -l)
RAW_FILES=$(find data/raw/$SEASON -name "*.json" | wc -l)

echo "Files created:"
echo "  - Processed schedule files: $SCHEDULE_FILES"
echo "  - Raw team data files: $RAW_FILES"

# Show playoff summary
if [ -f "data/processed/schedule/$SEASON/schedule_annotated.csv" ]; then
    echo ""
    echo "Playoff Summary:"
    python -c "
import pandas as pd
schedule = pd.read_csv('data/processed/schedule/$SEASON/schedule_annotated.csv')
playoff_games = schedule[schedule['is_playoff']]
if len(playoff_games) > 0:
    print(f'  - Playoff games: {len(playoff_games)}')
    print(f'  - Championship game: {len(playoff_games[playoff_games[\"playoff_round\"] == \"championship\"])}')
    print(f'  - Winners bracket: {len(playoff_games[playoff_games[\"bracket\"] == \"winners\"])}')
    print(f'  - Consolation bracket: {len(playoff_games[playoff_games[\"bracket\"] == \"consolation\"])}')
else:
    print('  - No playoff games found')
"
fi

echo ""
echo "🎉 Complete pipeline finished for season $SEASON!"
echo ""
echo "📁 Output files:"
echo "  - Schedule: data/processed/schedule/$SEASON/schedule_annotated.csv"
echo "  - Playoff brackets: data/processed/schedule/$SEASON/playoff_brackets.json"
echo "  - Manager data: data/processed/team_managers.json"
echo "  - Enhanced analysis: data/processed/enhanced_analysis.json"
echo ""
echo "🔍 Next steps:"
echo "  - Review annotated schedule for playoff accuracy"
echo "  - Run specific validations: python src/schedule_validator.py --season $SEASON --week 15"
echo "  - Generate visualizations from the processed data" 