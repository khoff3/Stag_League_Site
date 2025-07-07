#!/usr/bin/env python3
"""
Generic Playoff Schedule Constructor

This module constructs playoff schedules for any season by:
1. Defining bracket structures
2. Pulling team scores for each matchup
3. Building complete playoff schedules

Supports different league sizes and playoff formats.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from src.ingest.nfl.api_client_v2_optimized import NFLFantasyMultiTableScraper

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PlayoffGame:
    """Represents a single playoff game."""
    home_team_id: str
    away_team_id: str
    home_points: float
    away_points: float
    winner_id: str
    week: int
    round_name: str
    game_type: str  # 'semifinal', 'final', 'third_place', 'consolation', etc.


@dataclass
class PlayoffBracket:
    """Represents a complete playoff bracket."""
    season: int
    league_id: str
    seeds: List[Dict]
    semifinals: List[Optional[PlayoffGame]]
    final: Optional[PlayoffGame]
    third_place: Optional[PlayoffGame]
    consolation_games: List[PlayoffGame]
    championship_week: int
    consolation_week: int


class PlayoffScheduleConstructor:
    """Constructs playoff schedules for any season."""
    
    def __init__(self, league_id: str = "864504"):
        self.league_id = league_id
        self.api_client = NFLFantasyMultiTableScraper()
        
    def get_playoff_structure(self, num_playoff_teams: int) -> Dict:
        """Get playoff structure based on number of playoff teams."""
        if num_playoff_teams == 4:
            # 10-team league: top 4 teams in playoffs
            return {
                "championship_size": 4,
                "consolation_size": 6,
                "semifinals": [
                    {"home": 1, "away": 4},
                    {"home": 2, "away": 3}
                ],
                "championship_week": 15,
                "final_week": 16
            }
        elif num_playoff_teams == 6:
            # 12-team league: top 6 teams in playoffs
            return {
                "championship_size": 6,
                "consolation_size": 6,
                "semifinals": [
                    {"home": 1, "away": 6},
                    {"home": 2, "away": 5},
                    {"home": 3, "away": 4}
                ],
                "championship_week": 15,
                "final_week": 16
            }
        else:
            raise ValueError(f"Unsupported number of playoff teams: {num_playoff_teams}")
    
    def get_team_score(self, team_id: str, season: int, week: int) -> Optional[float]:
        """Fetch a single team's score for a specific week."""
        try:
            team_data = self.api_client.get_team_data(self.league_id, team_id, season, week)
            if team_data and team_data.get("team_stats"):
                return team_data["team_stats"].get("total_points", 0)
        except Exception as e:
            logger.warning(f"Could not fetch score for team {team_id}, week {week}: {e}")
        return None
    
    def create_playoff_game(self, home_id: str, away_id: str, season: int, week: int, 
                           round_name: str, game_type: str) -> Optional[PlayoffGame]:
        """Create a playoff game by fetching scores for both teams."""
        home_score = self.get_team_score(home_id, season, week)
        away_score = self.get_team_score(away_id, season, week)
        
        if home_score is None or away_score is None:
            logger.warning(f"Missing scores for {home_id} vs {away_id} in week {week}")
            return None
        
        winner_id = home_id if home_score > away_score else away_id
        
        return PlayoffGame(
            home_team_id=home_id,
            away_team_id=away_id,
            home_points=home_score,
            away_points=away_score,
            winner_id=winner_id,
            week=week,
            round_name=round_name,
            game_type=game_type
        )
    
    def create_playoff_game_with_scores(self, home_id: str, away_id: str, home_score: float, 
                                       away_score: float, week: int, round_name: str, 
                                       game_type: str) -> PlayoffGame:
        """Create a playoff game with provided scores."""
        winner_id = home_id if home_score > away_score else away_id
        
        return PlayoffGame(
            home_team_id=home_id,
            away_team_id=away_id,
            home_points=home_score,
            away_points=away_score,
            winner_id=winner_id,
            week=week,
            round_name=round_name,
            game_type=game_type
        )
    
    def build_championship_bracket(self, seeds: List[Dict], season: int, 
                                  structure: Dict) -> PlayoffBracket:
        """Build the championship bracket for a season."""
        logger.info(f"Building championship bracket for season {season}")
        
        # Create seed mapping
        seed_map = {seed['seed']: seed['team_id'] for seed in seeds}
        
        # Build semifinals
        semifinals = []
        for i, matchup in enumerate(structure['semifinals']):
            home_id = seed_map[matchup['home']]
            away_id = seed_map[matchup['away']]
            
            game = self.create_playoff_game(
                home_id, away_id, season, structure['championship_week'],
                f"Semifinal {i+1}", "semifinal"
            )
            semifinals.append(game)
            
            if game:
                logger.info(f"Semifinal {i+1}: {home_id} ({game.home_points:.2f}) vs {away_id} ({game.away_points:.2f})")
                logger.info(f"  Winner: {game.winner_id}")
        
        # Build final and third place
        final = None
        third_place = None
        
        if len(semifinals) >= 2 and semifinals[0] and semifinals[1]:
            # Final
            finalist1_id = semifinals[0].winner_id
            finalist2_id = semifinals[1].winner_id
            
            final = self.create_playoff_game(
                finalist1_id, finalist2_id, season, structure['final_week'],
                "Championship", "final"
            )
            
            if final:
                logger.info(f"Final: {finalist1_id} ({final.home_points:.2f}) vs {finalist2_id} ({final.away_points:.2f})")
                logger.info(f"  Champion: {final.winner_id}")
            
            # Third place
            loser1_id = semifinals[0].away_team_id if semifinals[0].winner_id == semifinals[0].home_team_id else semifinals[0].home_team_id
            loser2_id = semifinals[1].away_team_id if semifinals[1].winner_id == semifinals[1].home_team_id else semifinals[1].home_team_id
            
            third_place = self.create_playoff_game(
                loser1_id, loser2_id, season, structure['final_week'],
                "Third Place", "third_place"
            )
            
            if third_place:
                logger.info(f"Third Place: {loser1_id} ({third_place.home_points:.2f}) vs {loser2_id} ({third_place.away_points:.2f})")
                logger.info(f"  Third Place: {third_place.winner_id}")
        
        return PlayoffBracket(
            season=season,
            league_id=self.league_id,
            seeds=seeds,
            semifinals=semifinals,
            final=final,
            third_place=third_place,
            consolation_games=[],  # TODO: Add consolation bracket support
            championship_week=structure['championship_week'],
            consolation_week=structure['final_week']
        )
    
    def build_championship_bracket_with_scores(self, seeds: List[Dict], season: int, 
                                              structure: Dict, week15_scores: Dict[str, float],
                                              week16_scores: Optional[Dict[str, float]] = None) -> PlayoffBracket:
        """Build the championship bracket using provided scores."""
        logger.info(f"Building championship bracket for season {season} with provided scores")
        
        # Create seed mapping
        seed_map = {seed['seed']: seed['team_id'] for seed in seeds}
        
        # Build semifinals using provided scores
        semifinals = []
        for i, matchup in enumerate(structure['semifinals']):
            home_id = seed_map[matchup['home']]
            away_id = seed_map[matchup['away']]
            
            if home_id in week15_scores and away_id in week15_scores:
                game = self.create_playoff_game_with_scores(
                    home_id, away_id, week15_scores[home_id], week15_scores[away_id],
                    structure['championship_week'], f"Semifinal {i+1}", "semifinal"
                )
                semifinals.append(game)
                
                logger.info(f"Semifinal {i+1}: {home_id} ({game.home_points:.2f}) vs {away_id} ({game.away_points:.2f})")
                logger.info(f"  Winner: {game.winner_id}")
            else:
                logger.warning(f"Missing scores for {home_id} vs {away_id}")
                semifinals.append(None)
        
        # Build final and third place if we have Week 16 scores
        final = None
        third_place = None
        
        if week16_scores and len(semifinals) >= 2 and semifinals[0] and semifinals[1]:
            # Final
            finalist1_id = semifinals[0].winner_id
            finalist2_id = semifinals[1].winner_id
            
            if finalist1_id in week16_scores and finalist2_id in week16_scores:
                final = self.create_playoff_game_with_scores(
                    finalist1_id, finalist2_id, week16_scores[finalist1_id], week16_scores[finalist2_id],
                    structure['final_week'], "Championship", "final"
                )
                
                logger.info(f"Final: {finalist1_id} ({final.home_points:.2f}) vs {finalist2_id} ({final.away_points:.2f})")
                logger.info(f"  Champion: {final.winner_id}")
            
            # Third place
            loser1_id = semifinals[0].away_team_id if semifinals[0].winner_id == semifinals[0].home_team_id else semifinals[0].home_team_id
            loser2_id = semifinals[1].away_team_id if semifinals[1].winner_id == semifinals[1].home_team_id else semifinals[1].home_team_id
            
            if loser1_id in week16_scores and loser2_id in week16_scores:
                third_place = self.create_playoff_game_with_scores(
                    loser1_id, loser2_id, week16_scores[loser1_id], week16_scores[loser2_id],
                    structure['final_week'], "Third Place", "third_place"
                )
                
                logger.info(f"Third Place: {loser1_id} ({third_place.home_points:.2f}) vs {loser2_id} ({third_place.away_points:.2f})")
                logger.info(f"  Third Place: {third_place.winner_id}")
        
        return PlayoffBracket(
            season=season,
            league_id=self.league_id,
            seeds=seeds,
            semifinals=semifinals,
            final=final,
            third_place=third_place,
            consolation_games=[],
            championship_week=structure['championship_week'],
            consolation_week=structure['final_week']
        )
    
    def save_bracket(self, bracket: PlayoffBracket, output_path: Optional[str] = None) -> str:
        """Save bracket to JSON file."""
        if output_path is None:
            output_path = f"data/processed/schedule/{bracket.season}/playoff_bracket_constructed.json"
        
        # Convert to dict for JSON serialization
        bracket_dict = {
            "season": bracket.season,
            "league_id": bracket.league_id,
            "seeds": bracket.seeds,
            "semifinals": [
                {
                    "home_team_id": game.home_team_id,
                    "away_team_id": game.away_team_id,
                    "home_points": game.home_points,
                    "away_points": game.away_points,
                    "winner_id": game.winner_id,
                    "week": game.week,
                    "round_name": game.round_name,
                    "game_type": game.game_type
                } if game else None
                for game in bracket.semifinals
            ],
            "final": {
                "home_team_id": bracket.final.home_team_id,
                "away_team_id": bracket.final.away_team_id,
                "home_points": bracket.final.home_points,
                "away_points": bracket.final.away_points,
                "winner_id": bracket.final.winner_id,
                "week": bracket.final.week,
                "round_name": bracket.final.round_name,
                "game_type": bracket.final.game_type
            } if bracket.final else None,
            "third_place": {
                "home_team_id": bracket.third_place.home_team_id,
                "away_team_id": bracket.third_place.away_team_id,
                "home_points": bracket.third_place.home_points,
                "away_points": bracket.third_place.away_points,
                "winner_id": bracket.third_place.winner_id,
                "week": bracket.third_place.week,
                "round_name": bracket.third_place.round_name,
                "game_type": bracket.third_place.game_type
            } if bracket.third_place else None,
            "consolation_games": [],
            "championship_week": bracket.championship_week,
            "consolation_week": bracket.consolation_week
        }
        
        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(bracket_dict, f, indent=2)
        
        logger.info(f"Bracket saved to {output_path}")
        return output_path
    
    def print_bracket_summary(self, bracket: PlayoffBracket):
        """Print a summary of the playoff bracket."""
        print(f"\n🏆 {bracket.season} PLAYOFF BRACKET SUMMARY")
        print("=" * 60)
        
        # Print seeds
        print("Playoff Seeds:")
        for seed in bracket.seeds:
            print(f"  {seed['seed']}. {seed['team_name']} (Team {seed['team_id']})")
        
        # Print semifinals
        print(f"\nWeek {bracket.championship_week} - Semifinals:")
        for i, game in enumerate(bracket.semifinals):
            if game:
                home_name = next(seed['team_name'] for seed in bracket.seeds if seed['team_id'] == game.home_team_id)
                away_name = next(seed['team_name'] for seed in bracket.seeds if seed['team_id'] == game.away_team_id)
                winner_name = next(seed['team_name'] for seed in bracket.seeds if seed['team_id'] == game.winner_id)
                print(f"  {game.round_name}: {home_name} ({game.home_points:.2f}) vs {away_name} ({game.away_points:.2f})")
                print(f"    Winner: {winner_name}")
        
        # Print final
        if bracket.final:
            home_name = next(seed['team_name'] for seed in bracket.seeds if seed['team_id'] == bracket.final.home_team_id)
            away_name = next(seed['team_name'] for seed in bracket.seeds if seed['team_id'] == bracket.final.away_team_id)
            champion_name = next(seed['team_name'] for seed in bracket.seeds if seed['team_id'] == bracket.final.winner_id)
            print(f"\nWeek {bracket.consolation_week} - Championship:")
            print(f"  {bracket.final.round_name}: {home_name} ({bracket.final.home_points:.2f}) vs {away_name} ({bracket.final.away_points:.2f})")
            print(f"    🏆 Champion: {champion_name}")
        
        # Print third place
        if bracket.third_place:
            home_name = next(seed['team_name'] for seed in bracket.seeds if seed['team_id'] == bracket.third_place.home_team_id)
            away_name = next(seed['team_name'] for seed in bracket.seeds if seed['team_id'] == bracket.third_place.away_team_id)
            third_name = next(seed['team_name'] for seed in bracket.seeds if seed['team_id'] == bracket.third_place.winner_id)
            print(f"  {bracket.third_place.round_name}: {home_name} ({bracket.third_place.home_points:.2f}) vs {away_name} ({bracket.third_place.away_points:.2f})")
            print(f"    🥉 Third Place: {third_name}")


def construct_playoff_schedule(season: int, seeds: List[Dict], league_id: str = "864504") -> PlayoffBracket:
    """Convenience function to construct a playoff schedule."""
    constructor = PlayoffScheduleConstructor(league_id)
    
    # Determine playoff structure based on number of playoff teams
    num_playoff_teams = len(seeds)
    structure = constructor.get_playoff_structure(num_playoff_teams)
    
    # Build the bracket
    bracket = constructor.build_championship_bracket(seeds, season, structure)
    
    # Save and print summary
    constructor.save_bracket(bracket)
    constructor.print_bracket_summary(bracket)
    
    return bracket


def construct_playoff_schedule_with_scores(season: int, seeds: List[Dict], week15_scores: Dict[str, float],
                                          week16_scores: Optional[Dict[str, float]] = None, 
                                          league_id: str = "864504") -> PlayoffBracket:
    """Convenience function to construct a playoff schedule with provided scores."""
    constructor = PlayoffScheduleConstructor(league_id)
    
    # Determine playoff structure based on number of playoff teams
    num_playoff_teams = len(seeds)
    structure = constructor.get_playoff_structure(num_playoff_teams)
    
    # Build the bracket with provided scores
    bracket = constructor.build_championship_bracket_with_scores(seeds, season, structure, week15_scores, week16_scores)
    
    # Save and print summary
    constructor.save_bracket(bracket)
    constructor.print_bracket_summary(bracket)
    
    return bracket


if __name__ == "__main__":
    # Example usage for 2011
    seeds_2011 = [
        {"seed": 1, "team_id": "2", "team_name": "Granger Danger"},
        {"seed": 2, "team_id": "5", "team_name": "Fencing Beats Football"},
        {"seed": 3, "team_id": "1", "team_name": "The REVolution"},
        {"seed": 4, "team_id": "6", "team_name": "Swagger Badgers"}
    ]
    
    print("=== Testing Playoff Schedule Constructor ===")
    bracket = construct_playoff_schedule(2011, seeds_2011) 