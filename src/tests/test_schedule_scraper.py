#!/usr/bin/env python3
"""
Test script to validate the NFL schedule scraper.
Run this to test individual components before full season scraping.
"""

import sys
from pathlib import Path
import json
from ingest.nfl.schedule import NFLScheduleIngest

def test_single_week_extraction():
    """Test extracting data for a single week."""
    print("\nTesting Single Week Extraction...")
    print("=" * 40)
    
    try:
        scraper = NFLScheduleIngest()
        
        # Test with 2011 Week 1
        data = scraper.fetch_weekly_schedule(2011, 1, force_refresh=True)
        
        print(f"Extraction successful!")
        print(f"Games found: {len(data.get('games', []))}")
        
        # Show sample game
        if data.get('games'):
            game = data['games'][0]
            print(f"\nSample game:")
            print(f"  {game['away_team']} @ {game['home_team']}")
            print(f"  Score: {game['away_points']} - {game['home_points']}")
            print(f"  Records: {game['away_record']} vs {game['home_record']}")
            print(f"  Ranks: #{game['away_rank']} vs #{game['home_rank']}")
        
        return True
        
    except Exception as e:
        print(f"Error during extraction: {str(e)}")
        return False

def test_team_records():
    """Test team record tracking functionality."""
    print("\nTesting Team Records...")
    print("=" * 40)
    
    try:
        scraper = NFLScheduleIngest()
        
        # Test record updates
        scraper._reset_team_records()
        
        # Simulate some games
        test_games = [
            {'home_team_id': '1', 'home_points': 100, 'away_team_id': '2', 'away_points': 90},
            {'home_team_id': '1', 'home_points': 80, 'away_team_id': '3', 'away_points': 85},
            {'home_team_id': '2', 'home_points': 95, 'away_team_id': '3', 'away_points': 95}
        ]
        
        for game in test_games:
            scraper._update_team_record(
                game['home_team_id'],
                game['home_points'],
                game['away_points']
            )
            scraper._update_team_record(
                game['away_team_id'],
                game['away_points'],
                game['home_points']
            )
        
        # Check records
        print("Team Records:")
        for team_id, record in scraper.team_records.items():
            print(f"  Team {team_id}: {record['wins']}-{record['losses']}-{record['ties']}")
        
        return True
        
    except Exception as e:
        print(f"Error during record testing: {str(e)}")
        return False

def test_multiple_weeks_extraction():
    """Test extracting data for multiple weeks in a season."""
    print("\nTesting Multiple Weeks Extraction...")
    print("=" * 40)
    try:
        scraper = NFLScheduleIngest()
        season = 2011
        week_range = range(1, 4)  # Change to a larger range if desired
        all_success = True
        for week in week_range:
            print(f"\nFetching week {week}...")
            try:
                data = scraper.fetch_weekly_schedule(season, week, force_refresh=True)
                games = data.get('games', [])
                print(f"  Week {week}: {len(games)} games found.")
                if games:
                    game = games[0]
                    print(f"    Sample: {game['away_team']} @ {game['home_team']} | {game['away_points']} - {game['home_points']}")
            except Exception as e:
                print(f"  Error fetching week {week}: {e}")
                all_success = False
        return all_success
    except Exception as e:
        print(f"Error during multiple weeks extraction: {str(e)}")
        return False

def main():
    """Run all tests."""
    print("Running NFL Schedule Scraper Tests")
    print("=" * 40)
    
    tests = [
        ("Single Week Extraction", test_single_week_extraction),
        ("Team Records", test_team_records),
        ("Multiple Weeks Extraction", test_multiple_weeks_extraction)
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\nRunning {name} test...")
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"Error in {name} test: {str(e)}")
            results.append((name, False))
    
    print("\nTest Results:")
    print("=" * 40)
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{name}: {status}")

if __name__ == "__main__":
    main() 