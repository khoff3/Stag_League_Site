"""
Command-line interface for the Stag League History project.

This module provides a unified CLI for running ingest and transform operations
as specified in the architecture documentation.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional
import subprocess

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ingest.nfl.schedule import NFLScheduleIngest
from ingest.nfl.team_weeks import NFLTeamWeeksIngest
from ingest.nfl.player_weeks import NFLPlayerWeeksIngest
from team_manager_tracker import TeamManagerTracker
from enhanced_team_analyzer import EnhancedTeamAnalyzer
from scripts.playoff_annotator_fixed import PlayoffAnnotator
from utils.constants import ProjectPhases, DIRECTORIES


def setup_parser() -> argparse.ArgumentParser:
    """Set up the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Stag League History - NFL Fantasy Football Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/cli.py ingest schedule --season 2012 --force-refresh
  python src/cli.py ingest team-weeks --season 2012 --week 1
  python src/cli.py transform --season 2012
  python src/cli.py annotate playoff --season 2012
  python src/cli.py analyze team-managers --seasons 2011 2012
  python src/cli.py analyze enhanced --seasons 2012
  python src/cli.py test quick --season 2013
  python src/cli.py test full
  python src/cli.py status

Testing:
  python test_system.py                    # Full comprehensive test
  python src/scripts/quick_test.py         # Quick validation test
  python src/schedule_validator.py --season 2013 --week 1 --force-refresh
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Ingest command
    ingest_parser = subparsers.add_parser('ingest', help='Data ingestion operations')
    ingest_subparsers = ingest_parser.add_subparsers(dest='ingest_type', help='Ingest type')
    
    # Schedule ingest
    schedule_parser = ingest_subparsers.add_parser('schedule', help='Ingest NFL schedule data')
    schedule_parser.add_argument('--season', type=int, required=True, help='NFL season year')
    schedule_parser.add_argument('--week', type=int, help='Specific week (optional, processes all weeks if not specified)')
    schedule_parser.add_argument('--force-refresh', action='store_true', help='Force refresh cached data')
    
    # Team weeks ingest
    team_parser = ingest_subparsers.add_parser('team-weeks', help='Ingest team weekly data')
    team_parser.add_argument('--season', type=int, required=True, help='NFL season year')
    team_parser.add_argument('--week', type=int, required=True, help='Week number')
    team_parser.add_argument('--team-id', type=str, help='Specific team ID (optional)')
    
    # Player weeks ingest
    player_parser = ingest_subparsers.add_parser('player-weeks', help='Ingest player weekly data')
    player_parser.add_argument('--season', type=int, required=True, help='NFL season year')
    player_parser.add_argument('--week', type=int, required=True, help='Week number')
    player_parser.add_argument('--player-id', type=str, help='Specific player ID (optional)')
    
    # Annotate command
    annotate_parser = subparsers.add_parser('annotate', help='Data annotation operations')
    annotate_subparsers = annotate_parser.add_subparsers(dest='annotate_type', help='Annotation type')
    
    # Playoff annotation
    playoff_parser = annotate_subparsers.add_parser('playoff', help='Annotate schedule with playoff information')
    playoff_parser.add_argument('--season', type=int, required=True, help='NFL season year')
    playoff_parser.add_argument('--output', type=str, help='Output file path (optional)')
    
    # Transform command
    transform_parser = subparsers.add_parser('transform', help='Transform raw data to star schema')
    transform_parser.add_argument('--season', type=int, required=True, help='NFL season year')
    transform_parser.add_argument('--force', action='store_true', help='Force rebuild existing data')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Team and manager analysis operations')
    analyze_subparsers = analyze_parser.add_subparsers(dest='analyze_type', help='Analysis type')
    
    # Team managers analysis
    team_managers_parser = analyze_subparsers.add_parser('team-managers', help='Generate team manager tracking data')
    team_managers_parser.add_argument('--seasons', type=int, nargs='+', required=True, help='NFL seasons to analyze')
    team_managers_parser.add_argument('--output', type=str, help='Output file path (optional)')
    
    # Enhanced analysis
    enhanced_parser = analyze_subparsers.add_parser('enhanced', help='Generate enhanced team analysis with detailed stats')
    enhanced_parser.add_argument('--seasons', type=int, nargs='+', required=True, help='NFL seasons to analyze')
    enhanced_parser.add_argument('--output', type=str, help='Output file path (optional)')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show project status and phase information')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Run system tests')
    test_subparsers = test_parser.add_subparsers(dest='test_type', help='Test type')
    
    # Quick test
    quick_test_parser = test_subparsers.add_parser('quick', help='Run quick validation test')
    quick_test_parser.add_argument('--season', type=int, default=2013, help='Season to test (default: 2013)')
    
    # Full test
    full_test_parser = test_subparsers.add_parser('full', help='Run full comprehensive test')
    
    return parser


def run_schedule_ingest(args) -> None:
    """Run NFL schedule ingestion."""
    print(f"\n=== NFL Schedule Ingest (Season {args.season}) ===")
    
    scraper = NFLScheduleIngest()
    try:
        if args.week:
            # Process specific week
            print(f"Processing Week {args.week}...")
            data = scraper.fetch_weekly_schedule(args.season, args.week, args.force_refresh)
            print(f"Extracted {len(data.get('games', []))} games for Week {args.week}")
        else:
            # Process entire season
            print(f"Processing entire season {args.season}...")
            scraper.fetch_and_process_season(args.season)
            print(f"Completed processing season {args.season}")
    except Exception as e:
        print(f"Error during schedule ingest: {e}")
        raise
    finally:
        scraper.close()


def run_team_weeks_ingest(args) -> None:
    """Run NFL team weeks ingestion."""
    print(f"\n=== NFL Team Weeks Ingest (Season {args.season}, Week {args.week}) ===")
    
    # TODO: Implement team weeks ingest
    print("Team weeks ingest not yet implemented")
    print("This will extract team performance data from schedule data")


def run_player_weeks_ingest(args) -> None:
    """Run NFL player weeks ingestion."""
    print(f"\n=== NFL Player Weeks Ingest (Season {args.season}, Week {args.week}) ===")
    
    # TODO: Implement player weeks ingest
    print("Player weeks ingest not yet implemented")
    print("This will extract player performance data from roster information")


def run_transform(args) -> None:
    """Run data transformation to star schema."""
    print(f"\n=== Data Transform (Season {args.season}) ===")
    
    # TODO: Implement transform
    print("Transform not yet implemented")
    print("This will build the star schema database from raw data")


def run_team_managers_analysis(args) -> None:
    """Run team manager analysis."""
    print(f"\n=== Team Manager Analysis (Seasons: {args.seasons}) ===")
    
    tracker = TeamManagerTracker()
    
    # Generate dataset
    dataset = tracker.generate_team_manager_data(args.seasons)
    
    # Save to file
    if args.output:
        tracker.save_team_manager_data(dataset, args.output)
    else:
        tracker.save_team_manager_data(dataset)
    
    # Print summary
    tracker.print_manager_summary(dataset)
    
    print(f"\n✅ Team manager analysis complete!")
    if args.output:
        print(f"📁 Data saved to: {args.output}")
    else:
        print(f"📁 Data saved to: {tracker.managers_file}")


def run_enhanced_analysis(args) -> None:
    """Run enhanced team analysis."""
    print(f"\n=== Enhanced Team Analysis (Seasons: {args.seasons}) ===")
    print("This will analyze detailed player stats and team performance metrics.")
    print("Note: This may take some time as it scrapes detailed weekly data.")
    
    analyzer = EnhancedTeamAnalyzer()
    
    # Generate enhanced data
    enhanced_data = analyzer.enhance_manager_data(args.seasons)
    
    # Save to file
    if args.output:
        analyzer.save_enhanced_data(enhanced_data, args.output)
    else:
        analyzer.save_enhanced_data(enhanced_data)
    
    # Print summary
    analyzer.print_enhanced_summary(enhanced_data)
    
    print(f"\n✅ Enhanced team analysis complete!")
    if args.output:
        print(f"📁 Data saved to: {args.output}")
    else:
        print(f"📁 Data saved to: {analyzer.enhanced_data_file}")


def run_playoff_annotation(args) -> None:
    """Run playoff annotation for schedule data."""
    print(f"\n=== Playoff Annotation (Season {args.season}) ===")
    print("This will annotate schedule games with playoff status and rounds.")
    
    annotator = PlayoffAnnotator()
    
    try:
        # Annotate the season
        annotated_schedule = annotator.annotate_season(args.season, args.output)
        
        print(f"\n✅ Playoff annotation complete!")
        if args.output:
            print(f"📁 Annotated schedule saved to: {args.output}")
        else:
            print(f"📁 Annotated schedule saved to: data/processed/schedule/{args.season}/schedule_annotated.csv")
        
        # Show summary
        summary = annotator.get_playoff_summary(annotated_schedule)
        print(f"\n📊 Annotation Summary:")
        print(f"  Total games: {summary['total_games']}")
        print(f"  Regular season: {summary['regular_season_games']}")
        print(f"  Playoff games: {summary['playoff_games']}")
        
        if summary['playoff_rounds']:
            print(f"  Playoff rounds:")
            for round_name, count in summary['playoff_rounds'].items():
                print(f"    {round_name}: {count} games")
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Make sure you have run the schedule scraper first:")
        print(f"  python src/cli.py ingest schedule --season {args.season}")
    except Exception as e:
        print(f"❌ Error during playoff annotation: {e}")
        raise


def show_status() -> None:
    """Show project status and phase information."""
    print("\n=== Stag League History Project Status ===")
    
    print("\nProject Phases:")
    for phase in ProjectPhases:
        phase_data = phase.value
        print(f"  {phase_data.status} {phase_data.name}")
        print(f"    Target: {phase_data.target_date.strftime('%Y-%m-%d')}")
        print(f"    Deliverables: {', '.join(phase_data.deliverables)}")
    
    print("\nData Directories:")
    for dir_name, dir_path in DIRECTORIES.items():
        if Path(dir_path).exists():
            print(f"  ✅ {dir_name}: {dir_path}")
        else:
            print(f"  ❌ {dir_name}: {dir_path} (missing)")


def run_quick_test(args) -> None:
    """Run quick validation test."""
    print(f"\n=== Quick Test (Season {args.season}) ===")
    
    try:
        # Import and run quick test
        sys.path.insert(0, str(Path(__file__).parent / "scripts"))
        from quick_test import quick_schedule_test, quick_manager_test
        
        # Run tests
        schedule_ok = quick_schedule_test(args.season)
        manager_ok = quick_manager_test(args.season)
        
        print(f"\n📋 Quick Test Results:")
        print(f"Schedule Data: {'✅ PASSED' if schedule_ok else '❌ FAILED'}")
        print(f"Manager Data: {'✅ PASSED' if manager_ok else '⚠️  SKIPPED'}")
        
        if schedule_ok:
            print("\n🎉 Quick test passed! Ready for full validation.")
        else:
            print("\n⚠️  Quick test failed. Check data availability.")
            
    except ImportError:
        print("❌ Quick test module not found. Run: python src/scripts/quick_test.py")
    except Exception as e:
        print(f"❌ Quick test failed: {e}")


def run_full_test() -> None:
    """Run full comprehensive test."""
    print("\n=== Full Comprehensive Test ===")
    
    try:
        # Run the full test system
        result = subprocess.run(["python", "test_system.py"], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Full test completed successfully!")
            print(result.stdout)
        else:
            print("❌ Full test failed!")
            print(result.stderr)
            
    except FileNotFoundError:
        print("❌ test_system.py not found in project root")
    except Exception as e:
        print(f"❌ Full test failed: {e}")


def main():
    """Main CLI entry point."""
    parser = setup_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'ingest':
            if args.ingest_type == 'schedule':
                run_schedule_ingest(args)
            elif args.ingest_type == 'team-weeks':
                run_team_weeks_ingest(args)
            elif args.ingest_type == 'player-weeks':
                run_player_weeks_ingest(args)
            else:
                print("Please specify an ingest type: schedule, team-weeks, or player-weeks")
        elif args.command == 'transform':
            run_transform(args)
        elif args.command == 'analyze':
            if args.analyze_type == 'team-managers':
                run_team_managers_analysis(args)
            elif args.analyze_type == 'enhanced':
                run_enhanced_analysis(args)
            else:
                print("Please specify an analysis type: team-managers or enhanced")
        elif args.command == 'status':
            show_status()
        elif args.command == 'test':
            if args.test_type == 'quick':
                run_quick_test(args)
            elif args.test_type == 'full':
                run_full_test()
            else:
                print("Please specify a test type: quick or full")
        elif args.command == 'annotate':
            if args.annotate_type == 'playoff':
                run_playoff_annotation(args)
            else:
                print("Please specify an annotation type: playoff")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 