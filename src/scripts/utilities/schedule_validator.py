#!/usr/bin/env python3
"""
Schedule Validator

This module cross-validates schedule scores using granular player data from the v2 optimized API client.
It maintains the schedule scraper as independent but uses player-level data to verify accuracy.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from ingest.nfl.schedule import NFLScheduleIngest
from ingest.nfl.api_client_v2_optimized import NFLFantasyMultiTableScraper


class ScheduleValidator:
    """Validates schedule scores using granular player data."""
    
    def __init__(self, tolerance: float = 0.1):
        """
        Initialize the schedule validator.
        
        Args:
            tolerance: Maximum allowed difference between schedule and reconstructed scores
        """
        self.tolerance = tolerance
        self.schedule_scraper = NFLScheduleIngest()
        self.v2_scraper = NFLFantasyMultiTableScraper()
        
        # League ID mapping
        self.league_ids = {
            "2011": "400491",  # Original league
            "2012+": "864504"  # New league starting 2012
        }
    
    def _get_league_id(self, season: str) -> str:
        """Get the correct league ID for a season."""
        if season == "2011":
            return self.league_ids["2011"]
        else:
            return self.league_ids["2012+"]
    
    def validate_week_scores(self, season: int, week: int, force_refresh: bool = False) -> Dict:
        """
        Validate schedule scores for a specific week using granular player data.
        
        Args:
            season: NFL season year
            week: Week number
            force_refresh: Whether to force refresh cached data
            
        Returns:
            Dict containing validation results
        """
        print(f"\n=== Validating Week {week} Scores (Season {season}) ===")
        
        league_id = self._get_league_id(str(season))
        
        # Step 1: Get schedule data
        print("1. Fetching schedule data...")
        schedule_data = self.schedule_scraper.fetch_weekly_schedule(season, week, force_refresh)
        schedule_games = schedule_data.get('games', [])
        
        if not schedule_games:
            print("❌ No schedule games found")
            return {"error": "No schedule games found"}
        
        print(f"   Found {len(schedule_games)} games in schedule")
        
        # Step 2: Extract team IDs from schedule data
        print("2. Extracting team IDs from schedule data...")
        team_ids = set()
        for game in schedule_games:
            home_team_id = game.get('home_team_id')
            away_team_id = game.get('away_team_id')
            if home_team_id:
                team_ids.add(home_team_id)
            if away_team_id:
                team_ids.add(away_team_id)
        
        team_ids = sorted(list(team_ids))
        
        if not team_ids:
            print("❌ No team IDs found in schedule data")
            return {"error": "No team IDs found in schedule data"}
        
        print(f"   Found {len(team_ids)} teams: {team_ids}")
        
        # Step 3: Get granular player data for all teams
        print("3. Fetching granular player data...")
        
        # Use the team IDs from schedule data and fetch player data directly
        player_data = {}
        for team_id in team_ids:
            print(f"   Fetching data for Team {team_id}...")
            team_data = self.v2_scraper.get_team_data(
                league_id, team_id, season, week, force_refresh
            )
            if team_data:
                player_data[team_id] = team_data
            else:
                print(f"   ⚠️  No data found for Team {team_id}")
        
        if not player_data:
            print("❌ No player data found")
            return {"error": "No player data found"}
        
        print(f"   Retrieved data for {len(player_data)} teams")
        
        # Step 4: Cross-validate scores
        print("4. Cross-validating scores...")
        validation_results = []
        
        for game in schedule_games:
            home_team_id = game.get('home_team_id')
            away_team_id = game.get('away_team_id')
            home_schedule_score = game.get('home_points', 0)
            away_schedule_score = game.get('away_points', 0)
            
            # Validate home team
            home_validation = self._validate_team_score(
                home_team_id, home_schedule_score, player_data, "home"
            )
            
            # Validate away team
            away_validation = self._validate_team_score(
                away_team_id, away_schedule_score, player_data, "away"
            )
            
            validation_results.append({
                "game_id": game.get('game_id'),
                "week": week,
                "home_team": game.get('home_team'),
                "away_team": game.get('away_team'),
                "home_validation": home_validation,
                "away_validation": away_validation,
                "overall_valid": home_validation["valid"] and away_validation["valid"]
            })
        
        # Step 5: Generate summary
        valid_games = sum(1 for result in validation_results if result["overall_valid"])
        total_games = len(validation_results)
        
        summary = {
            "season": season,
            "week": week,
            "total_games": total_games,
            "valid_games": valid_games,
            "invalid_games": total_games - valid_games,
            "validation_rate": valid_games / total_games if total_games > 0 else 0,
            "tolerance": self.tolerance,
            "results": validation_results
        }
        
        # Step 6: Print results
        self._print_validation_summary(summary)
        
        return summary
    
    def _validate_team_score(self, team_id: str, schedule_score: float, 
                           player_data: Dict, team_type: str) -> Dict:
        """
        Validate a single team's score.
        
        Args:
            team_id: Team ID
            schedule_score: Score from schedule scraper
            player_data: Player data from v2 API
            team_type: "home" or "away"
            
        Returns:
            Dict containing validation results
        """
        if team_id not in player_data:
            return {
                "valid": False,
                "error": f"No player data found for team {team_id}",
                "schedule_score": schedule_score,
                "reconstructed_score": None,
                "difference": None
            }
        
        # Sum ONLY starter fantasy points (exclude bench players)
        players = player_data[team_id].get('players', [])
        starter_points = 0.0
        starter_count = 0
        bench_count = 0
        
        for player in players:
            # Check if player is a starter using the is_starter field
            is_starter = player.get('is_starter', True)  # Default to True for backward compatibility
            
            # Also check position as fallback
            position = player.get('position', '').upper()
            if position == 'BN':
                is_starter = False
            
            fantasy_points = player.get('fantasy_points', 0.0)
            
            if is_starter:
                starter_points += fantasy_points
                starter_count += 1
            else:
                bench_count += 1
        
        # Calculate difference
        difference = abs(schedule_score - starter_points)
        valid = difference <= self.tolerance
        
        return {
            "valid": valid,
            "schedule_score": schedule_score,
            "reconstructed_score": starter_points,
            "difference": difference,
            "starter_count": starter_count,
            "bench_count": bench_count,
            "total_player_count": len(players),
            "team_id": team_id
        }
    
    def _print_validation_summary(self, summary: Dict) -> None:
        """Print validation summary."""
        print(f"\n=== Validation Summary ===")
        print(f"Season: {summary['season']}")
        print(f"Week: {summary['week']}")
        print(f"Total Games: {summary['total_games']}")
        print(f"Valid Games: {summary['valid_games']}")
        print(f"Invalid Games: {summary['invalid_games']}")
        print(f"Validation Rate: {summary['validation_rate']:.1%}")
        print(f"Tolerance: ±{summary['tolerance']} points")
        
        # Print detailed results for invalid games
        invalid_results = [r for r in summary['results'] if not r['overall_valid']]
        if invalid_results:
            print(f"\n❌ Invalid Games ({len(invalid_results)}):")
            for result in invalid_results:
                print(f"  Game: {result['home_team']} vs {result['away_team']}")
                
                if not result['home_validation']['valid']:
                    home_val = result['home_validation']
                    print(f"    Home Team ({result['home_team']}):")
                    print(f"      Schedule: {home_val['schedule_score']}")
                    print(f"      Reconstructed: {home_val['reconstructed_score']}")
                    print(f"      Difference: {home_val['difference']:.2f}")
                    print(f"      Players: {home_val['starter_count']} starters, {home_val['bench_count']} bench")
                
                if not result['away_validation']['valid']:
                    away_val = result['away_validation']
                    print(f"    Away Team ({result['away_team']}):")
                    print(f"      Schedule: {away_val['schedule_score']}")
                    print(f"      Reconstructed: {away_val['reconstructed_score']}")
                    print(f"      Difference: {away_val['difference']:.2f}")
                    print(f"      Players: {away_val['starter_count']} starters, {away_val['bench_count']} bench")
        else:
            print(f"\n✅ All games validated successfully!")
    
    def save_validation_results(self, results: Dict, season: int, week: int) -> None:
        """Save validation results to file."""
        output_dir = Path("data/processed/validation")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"validation_{season}_week_{week:02d}.json"
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"📁 Validation results saved to: {output_file}")
    
    def close(self):
        """Clean up resources."""
        self.schedule_scraper.close()


def main():
    """Main function to run schedule validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate schedule scores using granular player data")
    parser.add_argument('--season', type=int, required=True, help='NFL season year')
    parser.add_argument('--week', type=int, required=True, help='Week number')
    parser.add_argument('--tolerance', type=float, default=0.1, help='Score tolerance (default: 0.1)')
    parser.add_argument('--force-refresh', action='store_true', help='Force refresh cached data')
    parser.add_argument('--save', action='store_true', help='Save validation results to file')
    
    args = parser.parse_args()
    
    validator = ScheduleValidator(tolerance=args.tolerance)
    
    try:
        results = validator.validate_week_scores(args.season, args.week, args.force_refresh)
        
        if args.save and 'error' not in results:
            validator.save_validation_results(results, args.season, args.week)
    
    finally:
        validator.close()


if __name__ == "__main__":
    main() 