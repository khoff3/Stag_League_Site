#!/usr/bin/env python3
"""
Comprehensive Manager Tracker

This script builds a complete manager history by combining:
1. Manager mapping data from CSV files
2. Draft data to see manager preferences
3. Schedule data for performance tracking
4. Playoff results for championship history
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
import logging
import pandas as pd

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComprehensiveManagerTracker:
    """Tracks managers comprehensively across all data sources."""
    
    def __init__(self, data_dir: str = "data"):
        """Initialize the tracker."""
        self.data_dir = Path(data_dir)
        self.processed_dir = self.data_dir / "processed"
        self.output_file = self.processed_dir / "comprehensive_manager_history.json"
        
        # League configuration
        self.league_config = {
            "2011": {"league_id": "400491", "league_name": "Stag League (Original)"},
            "2012+": {"league_id": "864504", "league_name": "Stag League (Current)"}
        }
        
    def get_league_id(self, season: str) -> str:
        """Get the appropriate league ID for a given season."""
        return self.league_config.get(season, self.league_config["2012+"])["league_id"]
    
    def load_manager_mapping(self, season: int) -> Dict[str, Dict]:
        """Load manager mapping CSV for a season."""
        mapping_file = self.processed_dir / "schedule" / str(season) / "manager_mapping.csv"
        
        if not mapping_file.exists():
            logger.warning(f"No manager mapping found for season {season}")
            return {}
        
        managers = {}
        with open(mapping_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                team_id = row['team_id']
                managers[team_id] = {
                    "team_id": team_id,
                    "team_name": row['team_name'],
                    "manager_name": row['manager_name'],
                    "user_id": row.get('user_id', ''),
                    "waiver_priority": row.get('waiver_priority', ''),
                    "moves": row.get('moves', ''),
                    "trades": row.get('trades', ''),
                    "last_activity": row.get('last_activity', ''),
                    "season": season
                }
        
        logger.info(f"Loaded {len(managers)} managers for season {season}")
        return managers
    
    def load_draft_data(self, season: int) -> Dict[str, List]:
        """Load draft data for a season."""
        # Try the main data directory first
        draft_file = self.processed_dir / "drafts" / str(season) / "draft_results.csv"
        if not draft_file.exists():
            # Try the NFL ingest directory
            draft_file = self.data_dir / "src" / "ingest" / "nfl" / "data" / "processed" / "drafts" / str(season) / "draft_results.csv"
        
        if not draft_file.exists():
            logger.warning(f"No draft data found for season {season}")
            return {}
        
        draft_data = {}
        df = pd.read_csv(draft_file)
        
        # Group by fantasy team
        for team_id in df['fantasy_team_id'].unique():
            team_picks = df[df['fantasy_team_id'] == team_id]
            draft_data[str(team_id)] = team_picks.to_dict('records')
        
        logger.info(f"Loaded draft data for {len(draft_data)} teams in season {season}")
        return draft_data
    
    def load_schedule_data(self, season: int) -> List[Dict]:
        """Load schedule data for a season."""
        schedule_file = self.processed_dir / "schedule" / str(season) / "schedule.csv"
        
        if not schedule_file.exists():
            logger.warning(f"No schedule data found for season {season}")
            return []
        
        games = []
        with open(schedule_file, 'r') as f:
            reader = csv.DictReader(f)
            games = list(reader)
        
        logger.info(f"Loaded {len(games)} games for season {season}")
        return games
    
    def load_playoff_data(self, season: int) -> Dict:
        """Load playoff data for a season."""
        playoff_file = self.processed_dir / "schedule" / str(season) / "postseason_standings.json"
        
        if not playoff_file.exists():
            logger.warning(f"No playoff data found for season {season}")
            return {}
        
        with open(playoff_file, 'r') as f:
            playoff_data = json.load(f)
        
        return playoff_data
    
    def calculate_team_performance(self, games: List[Dict], team_id: str) -> Dict:
        """Calculate team performance from schedule data."""
        team_games = []
        
        for game in games:
            if game['home_team_id'] == team_id or game['away_team_id'] == team_id:
                team_games.append(game)
        
        if not team_games:
            return {}
        
        # Calculate regular season stats (weeks 1-14)
        regular_season_games = [g for g in team_games if int(g['week']) <= 14]
        
        wins = 0
        losses = 0
        ties = 0
        points_for = 0.0
        points_against = 0.0
        
        for game in regular_season_games:
            if game['home_team_id'] == team_id:
                team_points = float(game['home_points'])
                opponent_points = float(game['away_points'])
            else:
                team_points = float(game['away_points'])
                opponent_points = float(game['home_points'])
            
            points_for += team_points
            points_against += opponent_points
            
            if team_points > opponent_points:
                wins += 1
            elif team_points < opponent_points:
                losses += 1
            else:
                ties += 1
        
        return {
            "regular_season": {
                "games_played": len(regular_season_games),
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "record": f"{wins}-{losses}-{ties}",
                "win_percentage": wins / len(regular_season_games) if regular_season_games else 0.0,
                "points_for": round(points_for, 2),
                "points_against": round(points_against, 2),
                "point_differential": round(points_for - points_against, 2),
                "average_points_for": round(points_for / len(regular_season_games), 2) if regular_season_games else 0.0,
                "average_points_against": round(points_against / len(regular_season_games), 2) if regular_season_games else 0.0
            }
        }
    
    def analyze_draft_preferences(self, draft_data: List[Dict]) -> Dict:
        """Analyze draft preferences from draft data."""
        if not draft_data:
            return {}
        
        # Count positions drafted
        position_counts = {}
        total_spent = 0
        auction_picks = 0
        snake_picks = 0
        
        for pick in draft_data:
            position = pick.get('position', '')
            if position:
                position_counts[position] = position_counts.get(position, 0) + 1
            
            # Track auction vs snake
            if 'auction_cost' in pick and pd.notna(pick['auction_cost']):
                auction_picks += 1
                total_spent += pick['auction_cost']
            else:
                snake_picks += 1
        
        return {
            "position_preferences": position_counts,
            "draft_type": "auction" if auction_picks > snake_picks else "snake",
            "total_auction_spent": total_spent if auction_picks > 0 else 0,
            "auction_picks": auction_picks,
            "snake_picks": snake_picks,
            "total_picks": len(draft_data)
        }
    
    def get_playoff_result(self, playoff_data: Dict, team_id: str) -> Optional[Dict]:
        """Get playoff result for a team."""
        for standing in playoff_data:
            if standing["team_id"] == team_id:
                return {
                    "final_place": standing["place"],
                    "final_label": standing["label"],
                    "playoff_points": standing.get("points", 0.0)
                }
        return None
    
    def process_season(self, season: int) -> Dict:
        """Process a complete season and combine all data sources."""
        logger.info(f"Processing season {season}")
        
        # Load all data sources
        managers = self.load_manager_mapping(season)
        draft_data = self.load_draft_data(season)
        games = self.load_schedule_data(season)
        playoff_data = self.load_playoff_data(season)
        
        if not managers:
            return {}
        
        season_data = {
            "season": season,
            "league_id": self.get_league_id(str(season)),
            "league_name": self.league_config.get(str(season), self.league_config["2012+"])["league_name"],
            "teams": {}
        }
        
        # Combine data for each team
        for team_id, manager_info in managers.items():
            team_data = {
                "team_id": team_id,
                "team_name": manager_info["team_name"],
                "manager_name": manager_info["manager_name"],
                "user_id": manager_info["user_id"],
                "waiver_priority": manager_info["waiver_priority"],
                "moves": manager_info["moves"],
                "trades": manager_info["trades"],
                "last_activity": manager_info["last_activity"],
                "performance": self.calculate_team_performance(games, team_id),
                "draft_analysis": self.analyze_draft_preferences(draft_data.get(team_id, [])),
                "playoff_result": self.get_playoff_result(playoff_data, team_id)
            }
            
            season_data["teams"][team_id] = team_data
        
        return season_data
    
    def build_manager_profiles(self, seasons_data: Dict[int, Dict]) -> Dict[str, Dict]:
        """Build comprehensive manager profiles across all seasons."""
        manager_profiles = {}
        
        for season, season_data in seasons_data.items():
            for team_id, team_data in season_data["teams"].items():
                manager_name = team_data["manager_name"]
                
                if manager_name not in manager_profiles:
                    manager_profiles[manager_name] = {
                        "manager_name": manager_name,
                        "user_id": team_data["user_id"],
                        "seasons": {},
                        "career_stats": {
                            "total_seasons": 0,
                            "total_games": 0,
                            "total_wins": 0,
                            "total_losses": 0,
                            "total_ties": 0,
                            "total_points_for": 0.0,
                            "total_points_against": 0.0,
                            "playoff_appearances": 0,
                            "championships": 0,
                            "runner_ups": 0,
                            "third_place_finishes": 0,
                            "best_finish": None,
                            "worst_finish": None,
                            "total_auction_spent": 0,
                            "total_draft_picks": 0,
                            "favorite_positions": {}
                        }
                    }
                
                # Add season data
                manager_profiles[manager_name]["seasons"][season] = {
                    "team_id": team_id,
                    "team_name": team_data["team_name"],
                    "league_id": season_data["league_id"],
                    "league_name": season_data["league_name"],
                    "performance": team_data["performance"],
                    "draft_analysis": team_data["draft_analysis"],
                    "playoff_result": team_data["playoff_result"],
                    "waiver_priority": team_data["waiver_priority"],
                    "moves": team_data["moves"],
                    "trades": team_data["trades"],
                    "last_activity": team_data["last_activity"]
                }
                
                # Update career stats
                career = manager_profiles[manager_name]["career_stats"]
                performance = team_data["performance"].get("regular_season", {})
                draft_analysis = team_data["draft_analysis"]
                
                career["total_seasons"] += 1
                career["total_games"] += performance.get("games_played", 0)
                career["total_wins"] += performance.get("wins", 0)
                career["total_losses"] += performance.get("losses", 0)
                career["total_ties"] += performance.get("ties", 0)
                career["total_points_for"] += performance.get("points_for", 0.0)
                career["total_points_against"] += performance.get("points_against", 0.0)
                career["total_auction_spent"] += draft_analysis.get("total_auction_spent", 0)
                career["total_draft_picks"] += draft_analysis.get("total_picks", 0)
                
                # Update position preferences
                for pos, count in draft_analysis.get("position_preferences", {}).items():
                    career["favorite_positions"][pos] = career["favorite_positions"].get(pos, 0) + count
                
                # Playoff stats
                if team_data["playoff_result"]:
                    place = team_data["playoff_result"]["final_place"]
                    
                    # Only count as playoff appearance if in top 6 (typical playoff cutoff for 12-team league)
                    if place <= 6:
                        career["playoff_appearances"] += 1
                    
                    if place == 1:
                        career["championships"] += 1
                    elif place == 2:
                        career["runner_ups"] += 1
                    elif place == 3:
                        career["third_place_finishes"] += 1
                    
                    # Track best/worst finishes
                    if career["best_finish"] is None or place < career["best_finish"]:
                        career["best_finish"] = place
                    if career["worst_finish"] is None or place > career["worst_finish"]:
                        career["worst_finish"] = place
        
        # Calculate averages and percentages
        for manager_name, profile in manager_profiles.items():
            career = profile["career_stats"]
            
            if career["total_games"] > 0:
                career["win_percentage"] = round(career["total_wins"] / career["total_games"], 3)
                career["average_points_for"] = round(career["total_points_for"] / career["total_games"], 2)
                career["average_points_against"] = round(career["total_points_against"] / career["total_games"], 2)
                career["average_point_differential"] = round(
                    (career["total_points_for"] - career["total_points_against"]) / career["total_games"], 2
                )
            
            if career["total_seasons"] > 0:
                career["average_season_points"] = round(career["total_points_for"] / career["total_seasons"], 2)
                career["playoff_percentage"] = round(career["playoff_appearances"] / career["total_seasons"], 3)
                career["average_auction_spent"] = round(career["total_auction_spent"] / career["total_seasons"], 2)
                career["average_draft_picks"] = round(career["total_draft_picks"] / career["total_seasons"], 2)
            
            # Sort favorite positions
            career["favorite_positions"] = dict(
                sorted(career["favorite_positions"].items(), key=lambda x: x[1], reverse=True)
            )
        
        return manager_profiles
    
    def generate_comprehensive_data(self, seasons: List[int]) -> Dict:
        """Generate comprehensive manager data for specified seasons."""
        logger.info(f"Generating comprehensive manager data for seasons: {seasons}")
        
        # Process each season
        seasons_data = {}
        for season in seasons:
            seasons_data[season] = self.process_season(season)
        
        # Build manager profiles
        manager_profiles = self.build_manager_profiles(seasons_data)
        
        # Create final dataset
        dataset = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "seasons_processed": seasons,
                "total_managers": len(manager_profiles),
                "total_teams": sum(len(season_data["teams"]) for season_data in seasons_data.values()),
                "data_sources": ["manager_mapping", "draft_data", "schedule_data", "playoff_data"]
            },
            "league_config": self.league_config,
            "seasons": seasons_data,
            "managers": manager_profiles
        }
        
        return dataset
    
    def save_comprehensive_data(self, dataset: Dict) -> None:
        """Save comprehensive manager data to JSON file."""
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.output_file, 'w') as f:
            json.dump(dataset, f, indent=2)
        
        logger.info(f"Comprehensive manager data saved to {self.output_file}")
    
    def print_comprehensive_summary(self, dataset: Dict) -> None:
        """Print a comprehensive summary of manager data."""
        managers = dataset["managers"]
        
        print(f"\n=== Comprehensive Manager Summary ===")
        print(f"Total Managers: {len(managers)}")
        print(f"Seasons Processed: {dataset['metadata']['seasons_processed']}")
        print(f"Total Teams: {dataset['metadata']['total_teams']}")
        print(f"Data Sources: {', '.join(dataset['metadata']['data_sources'])}")
        
        print(f"\n=== Manager Career Stats ===")
        for manager_name, profile in sorted(managers.items()):
            career = profile["career_stats"]
            print(f"\n{manager_name}:")
            print(f"  Seasons: {career['total_seasons']}")
            print(f"  Record: {career['total_wins']}-{career['total_losses']}-{career['total_ties']} ({career.get('win_percentage', 0):.3f})")
            print(f"  Championships: {career['championships']}")
            print(f"  Playoff Appearances: {career['playoff_appearances']}")
            print(f"  Avg Points/Game: {career.get('average_points_for', 0):.1f}")
            print(f"  Best Finish: {career.get('best_finish', 'N/A')}")
            print(f"  Total Auction Spent: ${career.get('total_auction_spent', 0):,}")
            print(f"  Favorite Position: {list(career.get('favorite_positions', {}).keys())[:3]}")


def main():
    """Main function to generate comprehensive manager data."""
    tracker = ComprehensiveManagerTracker()
    
    # Process all available seasons (2011-2022)
    seasons = list(range(2011, 2023))
    
    # Generate dataset
    dataset = tracker.generate_comprehensive_data(seasons)
    
    # Save to file
    tracker.save_comprehensive_data(dataset)
    
    # Print summary
    tracker.print_comprehensive_summary(dataset)
    
    print(f"\n✅ Comprehensive manager data generation complete!")
    print(f"📁 Data saved to: {tracker.output_file}")


if __name__ == "__main__":
    main() 