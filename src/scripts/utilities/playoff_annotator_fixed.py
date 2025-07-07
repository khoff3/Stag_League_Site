#!/usr/bin/env python3
"""
Playoff Annotator (Fixed for 2011)

This script annotates schedule games with playoff status and rounds by mapping
game IDs from playoff brackets to the schedule data.

Usage:
    python src/playoff_annotator_fixed.py --season 2011
"""

import argparse
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PlayoffAnnotator:
    """Annotates schedule games with playoff status and rounds."""
    
    def __init__(self, data_dir: str = "data/processed/schedule"):
        self.data_dir = Path(data_dir)
        
    def load_schedule(self, season: int) -> pd.DataFrame:
        """Load schedule data for a given season."""
        schedule_path = self.data_dir / str(season) / "schedule.csv"
        if not schedule_path.exists():
            raise FileNotFoundError(f"Schedule file not found: {schedule_path}")
        
        logger.info(f"Loading schedule from {schedule_path}")
        schedule = pd.read_csv(schedule_path)
        logger.info(f"Loaded {len(schedule)} games for season {season}")
        return schedule
    
    def load_playoff_brackets(self, season: int) -> Dict:
        """Load playoff brackets data for a given season."""
        # Try the complete bracket file first (for 2011)
        brackets_path = self.data_dir / str(season) / "playoff_bracket_complete.json"
        if not brackets_path.exists():
            # Fallback to the original brackets file
            brackets_path = self.data_dir / str(season) / "playoff_brackets.json"
            if not brackets_path.exists():
                raise FileNotFoundError(f"Playoff brackets file not found: {brackets_path}")
        
        logger.info(f"Loading playoff brackets from {brackets_path}")
        with open(brackets_path, 'r') as f:
            brackets = json.load(f)
        logger.info("Playoff brackets loaded successfully")
        return brackets
    
    def extract_playoff_games(self, brackets: Dict) -> Dict[str, Dict]:
        """Extract all playoff games and their metadata from brackets."""
        playoff_games = {}
        
        # Check if this is the new complete bracket structure (2011)
        if 'semifinals' in brackets and 'final' in brackets:
            # New structure: semifinals, final, third_place
            logger.info("Using complete bracket structure")
            
            # Semifinals (Week 15)
            for i, semifinal in enumerate(brackets['semifinals']):
                game_id = f"201115{100 + i}"  # Generate game ID for semifinals
                playoff_games[game_id] = {
                    'playoff_round': 'semifinal',
                    'bracket': 'winners',
                    'round_name': f'Semifinal {i+1}',
                    'is_playoff': True
                }
            
            # Championship game (Week 16)
            if 'final' in brackets and brackets['final']:
                game_id = "20111603"  # Championship game ID
                playoff_games[game_id] = {
                    'playoff_round': 'championship',
                    'bracket': 'winners',
                    'round_name': 'Championship',
                    'is_playoff': True
                }
            
            # Third place game (Week 16)
            if 'third_place' in brackets and brackets['third_place']:
                game_id = "20111604"  # Third place game ID
                playoff_games[game_id] = {
                    'playoff_round': 'third_place',
                    'bracket': 'winners',
                    'round_name': 'Third Place',
                    'is_playoff': True
                }
            
            # Consolation games (Week 16)
            game_id = "20111601"  # Toilet bowl game 1
            playoff_games[game_id] = {
                'playoff_round': 'toilet_bowl',
                'bracket': 'consolation',
                'round_name': 'Toilet Bowl',
                'is_playoff': True
            }
            
            game_id = "20111602"  # Toilet bowl game 2
            playoff_games[game_id] = {
                'playoff_round': 'toilet_bowl',
                'bracket': 'consolation',
                'round_name': 'Toilet Bowl',
                'is_playoff': True
            }
            
        else:
            # Original structure: winners_bracket, consolation_bracket
            logger.info("Using original bracket structure")
            
            # Winners bracket games
            if 'winners_bracket' in brackets:
                # Round 1 games
                if 'round_1' in brackets['winners_bracket']:
                    for game in brackets['winners_bracket']['round_1']:
                        playoff_games[game['game_id']] = {
                            'playoff_round': 'winners_round_1',
                            'bracket': 'winners',
                            'round_name': 'Winners Round 1',
                            'is_playoff': True
                        }
                
                # Championship week games
                if 'championship_week' in brackets['winners_bracket']:
                    championship_week = brackets['winners_bracket']['championship_week']
                    
                    # Championship game
                    if 'championship' in championship_week:
                        for game in championship_week['championship']:
                            playoff_games[game['game_id']] = {
                                'playoff_round': 'championship',
                                'bracket': 'winners',
                                'round_name': 'Championship',
                                'is_playoff': True
                            }
                    
                    # Third place game
                    if 'third_place' in championship_week:
                        for game in championship_week['third_place']:
                            playoff_games[game['game_id']] = {
                                'playoff_round': 'third_place',
                                'bracket': 'winners',
                                'round_name': 'Third Place',
                                'is_playoff': True
                            }
            
            # Consolation bracket games
            if 'consolation_bracket' in brackets:
                # Round 1 games
                if 'round_1' in brackets['consolation_bracket']:
                    for game in brackets['consolation_bracket']['round_1']:
                        playoff_games[game['game_id']] = {
                            'playoff_round': 'consolation_round_1',
                            'bracket': 'consolation',
                            'round_name': 'Consolation Round 1',
                            'is_playoff': True
                        }
                
                # Toilet bowl games
                if 'toilet_bowl' in brackets['consolation_bracket']:
                    for game in brackets['consolation_bracket']['toilet_bowl']:
                        playoff_games[game['game_id']] = {
                            'playoff_round': 'toilet_bowl',
                            'bracket': 'consolation',
                            'round_name': 'Toilet Bowl',
                            'is_playoff': True
                        }
        
        logger.info(f"Extracted {len(playoff_games)} playoff games")
        return playoff_games
    
    def annotate_schedule(self, schedule: pd.DataFrame, playoff_games: Dict[str, Dict], brackets: Dict) -> pd.DataFrame:
        """Annotate schedule with playoff information, including mediocre and toilet bowls."""
        # Initialize playoff columns
        schedule['is_playoff'] = False
        schedule['playoff_round'] = ''
        schedule['bracket'] = ''
        schedule['playoff_round_name'] = ''
        
        # Annotate playoff games from bracket
        annotated_count = 0
        for game_id, playoff_info in playoff_games.items():
            try:
                game_id_int = int(game_id)
                mask = schedule['game_id'] == game_id_int
                if mask.any():
                    schedule.loc[mask, 'is_playoff'] = playoff_info['is_playoff']
                    schedule.loc[mask, 'playoff_round'] = playoff_info['playoff_round']
                    schedule.loc[mask, 'bracket'] = playoff_info['bracket']
                    schedule.loc[mask, 'playoff_round_name'] = playoff_info['round_name']
                    annotated_count += 1
            except ValueError:
                logger.warning(f"Could not convert game_id {game_id} to int")
        
        # --- PATCH: Override middle team games from toilet_bowl to mediocre_bowl ---
        # Get middle team IDs from bracket
        middle_team_ids = set()
        if 'middle_teams' in brackets:
            middle_team_ids = {team['team_id'] for team in brackets['middle_teams']}
        elif 'seeds' in brackets and 'middle_teams' in brackets['seeds']:
            middle_team_ids = {team['team_id'] for team in brackets['seeds']['middle_teams']}
        
        print(f"DEBUG: Middle team IDs from bracket: {middle_team_ids}")
        
        # Override Week 16 games that are marked as toilet_bowl but involve middle teams
        for idx, row in schedule.iterrows():
            if int(row['week']) == 16 and row['playoff_round'] == 'toilet_bowl':
                home_id = str(row['home_team_id'])
                away_id = str(row['away_team_id'])
                print(f"DEBUG: Checking toilet bowl game {home_id} vs {away_id}")
                print(f"DEBUG: Home in middle teams: {home_id in middle_team_ids}")
                print(f"DEBUG: Away in middle teams: {away_id in middle_team_ids}")
                
                # If both teams are middle teams, change to mediocre bowl
                if home_id in middle_team_ids and away_id in middle_team_ids:
                    print(f"DEBUG: Overriding toilet bowl to mediocre bowl: {home_id} vs {away_id}")
                    schedule.at[idx, 'playoff_round'] = 'mediocre_bowl'
                    schedule.at[idx, 'bracket'] = 'middle'
                    schedule.at[idx, 'playoff_round_name'] = 'Mediocre Bowl'
        
        # --- PATCH: Annotate Week 15 and 16 mediocre and toilet bowls by team IDs ---
        # Get consolation team IDs from bracket
        consolation_team_ids = set()
        if 'seeds' in brackets and 'consolation_bracket' in brackets['seeds']:
            consolation_team_ids = {team['team_id'] for team in brackets['seeds']['consolation_bracket']}
        
        print(f"DEBUG: Consolation team IDs from bracket: {consolation_team_ids}")
        
        # Annotate Week 15 and 16 games that aren't already playoff games
        for idx, row in schedule.iterrows():
            week = int(row['week'])
            if week in [14, 15, 16] and not row['is_playoff']:
                home_id = str(row['home_team_id'])
                away_id = str(row['away_team_id'])
                print(f"DEBUG: Week {week} non-playoff game {home_id} vs {away_id}")
                print(f"DEBUG: Home in middle teams: {home_id in middle_team_ids}")
                print(f"DEBUG: Away in middle teams: {away_id in middle_team_ids}")
                print(f"DEBUG: Home in consolation teams: {home_id in consolation_team_ids}")
                print(f"DEBUG: Away in consolation teams: {away_id in consolation_team_ids}")
                
                # Mediocre bowl: both teams are middle teams (check this first)
                if home_id in middle_team_ids and away_id in middle_team_ids:
                    print(f"DEBUG: Marking as mediocre bowl: {home_id} vs {away_id}")
                    schedule.at[idx, 'is_playoff'] = True
                    schedule.at[idx, 'playoff_round'] = 'mediocre_bowl'
                    schedule.at[idx, 'bracket'] = 'middle'
                    schedule.at[idx, 'playoff_round_name'] = 'Mediocre Bowl'
                # Toilet bowl: both teams are consolation teams
                elif home_id in consolation_team_ids and away_id in consolation_team_ids:
                    print(f"DEBUG: Marking as toilet bowl: {home_id} vs {away_id}")
                    schedule.at[idx, 'is_playoff'] = True
                    schedule.at[idx, 'playoff_round'] = 'toilet_bowl'
                    schedule.at[idx, 'bracket'] = 'consolation'
                    schedule.at[idx, 'playoff_round_name'] = 'Toilet Bowl'
                # Otherwise, leave as is
        
        return schedule
    
    def get_playoff_summary(self, schedule: pd.DataFrame) -> Dict:
        """Generate summary of playoff annotation."""
        total_games = len(schedule)
        playoff_games = len(schedule[schedule['is_playoff']])
        regular_season_games = total_games - playoff_games
        
        playoff_rounds = {}
        if playoff_games > 0:
            playoff_rounds = schedule[schedule['is_playoff']]['playoff_round_name'].value_counts().to_dict()
        
        return {
            'total_games': total_games,
            'playoff_games': playoff_games,
            'regular_season_games': regular_season_games,
            'playoff_rounds': playoff_rounds
        }
    
    def annotate_season(self, season: int, output_path: Optional[str] = None) -> pd.DataFrame:
        """Annotate schedule for a given season."""
        # Load data
        schedule = self.load_schedule(season)
        brackets = self.load_playoff_brackets(season)
        
        # Extract playoff games
        playoff_games = self.extract_playoff_games(brackets)
        
        # Annotate schedule
        annotated_schedule = self.annotate_schedule(schedule, playoff_games, brackets)
        
        # Generate summary
        summary = self.get_playoff_summary(annotated_schedule)
        logger.info("Playoff annotation summary:")
        for key, value in summary.items():
            if key == 'playoff_rounds':
                logger.info(f"  {key}:")
                for round_name, count in value.items():
                    logger.info(f"    {round_name}: {count} games")
            else:
                logger.info(f"  {key}: {value}")
        
        # Save annotated schedule
        if output_path:
            output_file = Path(output_path)
            annotated_schedule.to_csv(output_file, index=False)
            logger.info(f"Annotated schedule saved to {output_file}")
        else:
            # Save to default location
            output_file = self.data_dir / str(season) / "schedule_annotated.csv"
            annotated_schedule.to_csv(output_file, index=False)
            logger.info(f"Annotated schedule saved to {output_file}")
        
        # Show sample playoff games
        playoff_games_df = annotated_schedule[annotated_schedule['is_playoff']]
        if len(playoff_games_df) > 0:
            logger.info("\nSample playoff games:")
            sample_cols = ['game_id', 'week', 'home_team', 'away_team', 'playoff_round_name']
            logger.info(playoff_games_df[sample_cols].head().to_string(index=False))
        
        logger.info("Playoff annotation completed successfully!")
        return annotated_schedule


def main():
    parser = argparse.ArgumentParser(description="Annotate schedule with playoff information")
    parser.add_argument("--season", type=int, required=True, help="Season to annotate")
    parser.add_argument("--output", type=str, help="Output file path")
    
    args = parser.parse_args()
    
    annotator = PlayoffAnnotator()
    annotator.annotate_season(args.season, args.output)


if __name__ == "__main__":
    main() 