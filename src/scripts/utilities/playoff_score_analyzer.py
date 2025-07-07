#!/usr/bin/env python3
"""
Playoff Score Analyzer

This script demonstrates how to join raw player scores (from validation) 
with playoff-annotated schedule data for comprehensive analysis.

Usage:
    python src/scripts/playoff_score_analyzer.py --season 2012 --week 15
"""

import argparse
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingest.nfl.api_client_v2_optimized import NFLFantasyMultiTableScraper


class PlayoffScoreAnalyzer:
    """Analyzes playoff games by joining raw player scores with schedule data."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.v2_scraper = NFLFantasyMultiTableScraper()
        
    def load_annotated_schedule(self, season: int) -> pd.DataFrame:
        """Load the playoff-annotated schedule."""
        schedule_path = self.data_dir / "processed" / "schedule" / str(season) / "schedule_annotated.csv"
        if not schedule_path.exists():
            raise FileNotFoundError(f"Annotated schedule not found: {schedule_path}")
        
        schedule = pd.read_csv(schedule_path)
        print(f"Loaded {len(schedule)} games from annotated schedule")
        return schedule
    
    def load_raw_player_data(self, season: int, week: int, team_id: str) -> Optional[Dict]:
        """Load raw player data for a specific team/week."""
        raw_path = self.data_dir / "raw" / str(season) / f"week_{week:02d}" / f"team_{team_id}.json"
        if not raw_path.exists():
            return None
        
        with open(raw_path, 'r') as f:
            return json.load(f)
    
    def get_team_starters(self, team_data: Dict) -> List[Dict]:
        """Extract starter players from team data."""
        if not team_data or 'players' not in team_data:
            return []
        
        starters = []
        for player in team_data['players']:
            # Check if player is a starter
            lineup_status = player.get('lineup_status', 'starter')
            position = player.get('position', '')
            
            # Consider BN (bench) as non-starter
            if lineup_status == 'starter' and position != 'BN':
                starters.append(player)
        
        return starters
    
    def calculate_team_score(self, starters: List[Dict]) -> float:
        """Calculate team score from starter fantasy points."""
        return sum(player.get('fantasy_points', 0) for player in starters)
    
    def analyze_playoff_week(self, season: int, week: int, force_refresh: bool = False) -> Dict:
        """
        Analyze a playoff week by joining raw player scores with schedule data.
        
        Args:
            season: NFL season year
            week: Week number
            force_refresh: Whether to force refresh cached data
            
        Returns:
            Dict containing analysis results
        """
        print(f"\n=== Playoff Week Analysis (Season {season}, Week {week}) ===")
        
        # Step 1: Load annotated schedule
        schedule = self.load_annotated_schedule(season)
        
        # Step 2: Filter for playoff games in this week
        playoff_games = schedule[
            (schedule['week'] == week) & 
            (schedule['is_playoff'] == True)
        ]
        
        if len(playoff_games) == 0:
            print(f"No playoff games found for Week {week}")
            return {"error": f"No playoff games found for Week {week}"}
        
        print(f"Found {len(playoff_games)} playoff games in Week {week}")
        
        # Step 3: Analyze each playoff game
        analysis_results = []
        
        for _, game in playoff_games.iterrows():
            game_analysis = self._analyze_playoff_game(game, season, week, force_refresh)
            analysis_results.append(game_analysis)
        
        # Step 4: Generate summary
        summary = {
            "season": season,
            "week": week,
            "total_playoff_games": len(playoff_games),
            "games_analyzed": len(analysis_results),
            "analysis_results": analysis_results
        }
        
        # Step 5: Print results
        self._print_analysis_summary(summary)
        
        return summary
    
    def _analyze_playoff_game(self, game: pd.Series, season: int, week: int, 
                            force_refresh: bool) -> Dict:
        """Analyze a single playoff game."""
        game_id = game['game_id']
        home_team_id = game['home_team_id']
        away_team_id = game['away_team_id']
        
        print(f"\n--- Analyzing Game {game_id} ---")
        print(f"  {game['home_team']} vs {game['away_team']}")
        print(f"  Round: {game['playoff_round_name']} | Bracket: {game['bracket']}")
        
        # Load raw player data for both teams
        home_data = self.load_raw_player_data(season, week, home_team_id)
        away_data = self.load_raw_player_data(season, week, away_team_id)
        
        if not home_data or not away_data:
            print(f"  ⚠️  Missing player data for game {game_id}")
            return {
                "game_id": game_id,
                "error": "Missing player data",
                "schedule_scores": {
                    "home": game['home_points'],
                    "away": game['away_points']
                }
            }
        
        # Extract starters and calculate scores
        home_starters = self.get_team_starters(home_data)
        away_starters = self.get_team_starters(away_data)
        
        home_reconstructed_score = self.calculate_team_score(home_starters)
        away_reconstructed_score = self.calculate_team_score(away_starters)
        
        # Compare with schedule scores
        home_schedule_score = game['home_points']
        away_schedule_score = game['away_points']
        
        home_diff = abs(home_reconstructed_score - home_schedule_score)
        away_diff = abs(away_reconstructed_score - away_schedule_score)
        
        # Determine winner
        schedule_winner = "home" if home_schedule_score > away_schedule_score else "away"
        reconstructed_winner = "home" if home_reconstructed_score > away_reconstructed_score else "away"
        
        # Top performers
        home_top_performers = sorted(home_starters, key=lambda x: x.get('fantasy_points', 0), reverse=True)[:3]
        away_top_performers = sorted(away_starters, key=lambda x: x.get('fantasy_points', 0), reverse=True)[:3]
        
        analysis = {
            "game_id": game_id,
            "playoff_round": game['playoff_round_name'],
            "bracket": game['bracket'],
            "schedule_scores": {
                "home": home_schedule_score,
                "away": away_schedule_score,
                "winner": schedule_winner
            },
            "reconstructed_scores": {
                "home": home_reconstructed_score,
                "away": away_reconstructed_score,
                "winner": reconstructed_winner
            },
            "validation": {
                "home_diff": home_diff,
                "away_diff": away_diff,
                "home_valid": home_diff < 0.1,
                "away_valid": away_diff < 0.1,
                "both_valid": home_diff < 0.1 and away_diff < 0.1
            },
            "player_analysis": {
                "home_starters": len(home_starters),
                "away_starters": len(away_starters),
                "home_top_performers": [
                    {
                        "name": p.get('name', 'Unknown'),
                        "position": p.get('position', 'Unknown'),
                        "fantasy_points": p.get('fantasy_points', 0),
                        "nfl_team": p.get('nfl_team', 'Unknown')
                    }
                    for p in home_top_performers
                ],
                "away_top_performers": [
                    {
                        "name": p.get('name', 'Unknown'),
                        "position": p.get('position', 'Unknown'),
                        "fantasy_points": p.get('fantasy_points', 0),
                        "nfl_team": p.get('nfl_team', 'Unknown')
                    }
                    for p in away_top_performers
                ]
            }
        }
        
        # Print game analysis
        print(f"  Schedule Score: {home_schedule_score:.1f} - {away_schedule_score:.1f}")
        print(f"  Reconstructed: {home_reconstructed_score:.1f} - {away_reconstructed_score:.1f}")
        print(f"  Validation: {'✅' if analysis['validation']['both_valid'] else '❌'}")
        
        if analysis['validation']['both_valid']:
            print(f"  Winner: {game['home_team'] if schedule_winner == 'home' else game['away_team']}")
            print(f"  Top Performer: {home_top_performers[0]['name']} ({home_top_performers[0]['fantasy_points']:.1f} pts)" if home_top_performers else "N/A")
        
        return analysis
    
    def _print_analysis_summary(self, summary: Dict) -> None:
        """Print analysis summary."""
        print(f"\n=== Analysis Summary ===")
        print(f"Season: {summary['season']}")
        print(f"Week: {summary['week']}")
        print(f"Playoff Games: {summary['total_playoff_games']}")
        print(f"Games Analyzed: {summary['games_analyzed']}")
        
        # Count validations
        valid_games = sum(1 for result in summary['analysis_results'] 
                         if result.get('validation', {}).get('both_valid', False))
        
        print(f"Valid Games: {valid_games}/{summary['games_analyzed']}")
        print(f"Validation Rate: {valid_games/summary['games_analyzed']*100:.1f}%" if summary['games_analyzed'] > 0 else "N/A")
        
        # Show championship game if present
        championship_games = [r for r in summary['analysis_results'] 
                            if r.get('playoff_round') == 'Championship']
        
        if championship_games:
            print(f"\n🏆 Championship Game Analysis:")
            champ = championship_games[0]
            print(f"  Winner: {champ['schedule_scores']['winner'].title()}")
            print(f"  Score: {champ['schedule_scores']['home']:.1f} - {champ['schedule_scores']['away']:.1f}")
            print(f"  Top Performer: {champ['player_analysis']['home_top_performers'][0]['name']} ({champ['player_analysis']['home_top_performers'][0]['fantasy_points']:.1f} pts)" if champ['player_analysis']['home_top_performers'] else "N/A")
    
    def export_analysis(self, summary: Dict, output_path: str) -> None:
        """Export analysis results to JSON."""
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\n📁 Analysis exported to: {output_path}")
    
    def generate_playoff_report(self, season: int) -> Dict:
        """Generate a comprehensive playoff report for a season."""
        print(f"\n=== Generating Playoff Report (Season {season}) ===")
        
        # Load annotated schedule
        schedule = self.load_annotated_schedule(season)
        
        # Filter playoff games
        playoff_games = schedule[schedule['is_playoff'] == True]
        
        if len(playoff_games) == 0:
            print("No playoff games found for this season")
            return {"error": "No playoff games found"}
        
        # Analyze each playoff week
        playoff_weeks = sorted(playoff_games['week'].unique())
        weekly_analyses = {}
        
        for week in playoff_weeks:
            print(f"\nAnalyzing Week {week}...")
            weekly_analysis = self.analyze_playoff_week(season, week)
            weekly_analyses[week] = weekly_analysis
        
        # Generate season summary
        season_summary = {
            "season": season,
            "total_playoff_games": len(playoff_games),
            "playoff_weeks": playoff_weeks,
            "weekly_analyses": weekly_analyses,
            "championship_game": None,
            "playoff_bracket_summary": {}
        }
        
        # Find championship game
        championship_games = playoff_games[playoff_games['playoff_round'] == 'championship']
        if len(championship_games) > 0:
            champ_game = championship_games.iloc[0]
            season_summary["championship_game"] = {
                "winner": champ_game['home_team'] if champ_game['home_points'] > champ_game['away_points'] else champ_game['away_team'],
                "score": f"{champ_game['home_points']:.1f} - {champ_game['away_points']:.1f}",
                "week": champ_game['week']
            }
        
        # Bracket summary
        bracket_counts = playoff_games['bracket'].value_counts().to_dict()
        round_counts = playoff_games['playoff_round_name'].value_counts().to_dict()
        
        season_summary["playoff_bracket_summary"] = {
            "brackets": bracket_counts,
            "rounds": round_counts
        }
        
        return season_summary


def main():
    parser = argparse.ArgumentParser(description="Analyze playoff games with raw player scores")
    parser.add_argument("--season", type=int, required=True, help="NFL season year")
    parser.add_argument("--week", type=int, help="Specific week (optional, analyzes all playoff weeks if not specified)")
    parser.add_argument("--force-refresh", action="store_true", help="Force refresh cached data")
    parser.add_argument("--output", type=str, help="Output file path for analysis results")
    
    args = parser.parse_args()
    
    analyzer = PlayoffScoreAnalyzer()
    
    try:
        if args.week:
            # Analyze specific week
            results = analyzer.analyze_playoff_week(args.season, args.week, args.force_refresh)
        else:
            # Generate full season report
            results = analyzer.generate_playoff_report(args.season)
        
        # Export results if output path specified
        if args.output:
            analyzer.export_analysis(results, args.output)
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        raise


if __name__ == "__main__":
    main() 