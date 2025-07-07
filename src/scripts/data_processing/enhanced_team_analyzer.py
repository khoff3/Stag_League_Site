#!/usr/bin/env python3
"""
Enhanced Team Analyzer

This module integrates the team manager tracker with the API client v2 to pull
detailed player stats and score breakdowns for comprehensive team analysis.
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Import our modules
from team_manager_tracker import TeamManagerTracker
from ingest.nfl.api_client_v2 import NFLFantasyGameStatsScraper

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedTeamAnalyzer:
    """Enhanced team analyzer with detailed player stats integration."""
    
    def __init__(self, data_dir: str = "data"):
        """Initialize the analyzer."""
        self.data_dir = Path(data_dir)
        self.processed_dir = self.data_dir / "processed"
        self.enhanced_data_file = self.processed_dir / "enhanced_team_analysis.json"
        
        # Initialize components
        self.tracker = TeamManagerTracker(data_dir)
        self.api_client = NFLFantasyGameStatsScraper()
        
        # Performance settings
        self.sample_weeks = [1, 5, 10, 15, 16]  # Sample key weeks instead of all 16
        self.max_workers = 3  # Limit concurrent requests
        self.request_delay = 0.5  # Delay between requests to be respectful
        
    def get_team_weekly_stats(self, league_id: str, season: int, week: int, team_id: str) -> Optional[Dict]:
        """Get detailed weekly stats for a specific team."""
        try:
            # Add delay to be respectful to the server
            time.sleep(self.request_delay)
            
            team_data = self.api_client.get_team_data(league_id, team_id, season, week)
            if not team_data or "players" not in team_data:
                return None
            
            # Calculate team totals
            total_points = sum(player.get("fantasy_points", 0) for player in team_data["players"])
            starters = [p for p in team_data["players"] if p.get("lineup_status") == "starter"]
            bench_players = [p for p in team_data["players"] if p.get("lineup_status") == "bench"]
            
            starter_points = sum(player.get("fantasy_points", 0) for player in starters)
            bench_points = sum(player.get("fantasy_points", 0) for player in bench_players)
            
            # Position breakdown
            position_stats = {}
            for player in team_data["players"]:
                position = player.get("position", "UNK")
                if position not in position_stats:
                    position_stats[position] = {
                        "count": 0,
                        "total_points": 0.0,
                        "players": []
                    }
                
                position_stats[position]["count"] += 1
                position_stats[position]["total_points"] += player.get("fantasy_points", 0)
                position_stats[position]["players"].append({
                    "name": player.get("name", "Unknown"),
                    "points": player.get("fantasy_points", 0),
                    "lineup_status": player.get("lineup_status", "unknown")
                })
            
            return {
                "week": week,
                "team_id": team_id,
                "total_points": round(total_points, 2),
                "starter_points": round(starter_points, 2),
                "bench_points": round(bench_points, 2),
                "bench_contribution": round(bench_points / total_points * 100, 1) if total_points > 0 else 0.0,
                "player_count": len(team_data["players"]),
                "starter_count": len(starters),
                "bench_count": len(bench_players),
                "position_breakdown": position_stats,
                "top_performers": sorted(
                    team_data["players"], 
                    key=lambda x: x.get("fantasy_points", 0), 
                    reverse=True
                )[:5],
                "worst_performers": sorted(
                    team_data["players"], 
                    key=lambda x: x.get("fantasy_points", 0)
                )[:3]
            }
            
        except Exception as e:
            logger.error(f"Error getting stats for team {team_id}, week {week}: {e}")
            return None
    
    def analyze_team_season(self, league_id: str, season: int, team_id: str, team_name: str) -> Dict:
        """Analyze a complete season for a team with detailed weekly breakdowns."""
        logger.info(f"Analyzing {season} season for {team_name} (Team {team_id}) - sampling weeks: {self.sample_weeks}")
        
        season_analysis = {
            "team_id": team_id,
            "team_name": team_name,
            "season": season,
            "league_id": league_id,
            "weekly_breakdowns": {},
            "season_summary": {},
            "performance_metrics": {},
            "sampling_info": {
                "sampled_weeks": self.sample_weeks,
                "total_weeks_in_season": 16
            }
        }
        
        # Analyze only sample weeks for performance
        weekly_stats = []
        
        for week in self.sample_weeks:
            week_stats = self.get_team_weekly_stats(league_id, season, week, team_id)
            if week_stats:
                season_analysis["weekly_breakdowns"][week] = week_stats
                weekly_stats.append(week_stats)
        
        if not weekly_stats:
            logger.warning(f"No weekly stats found for team {team_id} in {season}")
            return season_analysis
        
        # Calculate season summary based on sampled data
        total_points = sum(w["total_points"] for w in weekly_stats)
        total_starter_points = sum(w["starter_points"] for w in weekly_stats)
        total_bench_points = sum(w["bench_points"] for w in weekly_stats)
        
        # Performance metrics
        weekly_points = [w["total_points"] for w in weekly_stats]
        best_week = max(weekly_stats, key=lambda x: x["total_points"])
        worst_week = min(weekly_stats, key=lambda x: x["total_points"])
        
        # Consistency metrics
        avg_points = total_points / len(weekly_stats)
        point_variance = sum((p - avg_points) ** 2 for p in weekly_points) / len(weekly_points)
        consistency_score = 1 - (point_variance / (avg_points ** 2)) if avg_points > 0 else 0
        
        season_analysis["season_summary"] = {
            "sampled_weeks": len(weekly_stats),
            "total_points": round(total_points, 2),
            "average_points_per_week": round(avg_points, 2),
            "total_starter_points": round(total_starter_points, 2),
            "total_bench_points": round(total_bench_points, 2),
            "bench_contribution_percentage": round(total_bench_points / total_points * 100, 1) if total_points > 0 else 0.0,
            "best_week": {
                "week": best_week["week"],
                "points": best_week["total_points"]
            },
            "worst_week": {
                "week": worst_week["week"],
                "points": worst_week["total_points"]
            }
        }
        
        season_analysis["performance_metrics"] = {
            "consistency_score": round(consistency_score, 3),
            "point_variance": round(point_variance, 2),
            "highest_weekly_score": round(best_week["total_points"], 2),
            "lowest_weekly_score": round(worst_week["total_points"], 2),
            "score_range": round(best_week["total_points"] - worst_week["total_points"], 2),
            "weeks_above_average": len([w for w in weekly_stats if w["total_points"] > avg_points]),
            "weeks_below_average": len([w for w in weekly_stats if w["total_points"] < avg_points])
        }
        
        return season_analysis
    
    def enhance_manager_data(self, seasons: List[int]) -> Dict:
        """Enhance team manager data with detailed player stats."""
        logger.info(f"Enhancing team manager data for seasons: {seasons}")
        start_time = time.time()
        
        # Load existing manager data
        manager_data = self.tracker.generate_team_manager_data(seasons)
        
        # Add enhanced analysis
        enhanced_data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "enhancement_type": "detailed_player_stats",
                "seasons_processed": seasons,
                "sampling_weeks": self.sample_weeks,
                "performance_optimized": True
            },
            "original_data": manager_data,
            "enhanced_analysis": {}
        }
        
        # Process each season
        for season in seasons:
            season_data = manager_data["seasons"][season]
            league_id = season_data["league_id"]
            
            enhanced_data["enhanced_analysis"][season] = {
                "season": season,
                "league_id": league_id,
                "teams": {}
            }
            
            # Process teams in parallel for better performance
            team_analyses = {}
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all team analysis tasks
                future_to_team = {}
                for team_id, team_info in season_data["teams"].items():
                    team_name = team_info["team_name"]
                    future = executor.submit(
                        self.analyze_team_season, 
                        league_id, 
                        season, 
                        team_id, 
                        team_name
                    )
                    future_to_team[future] = team_id
                
                # Collect results as they complete
                for future in as_completed(future_to_team):
                    team_id = future_to_team[future]
                    try:
                        team_analysis = future.result()
                        team_analyses[team_id] = team_analysis
                        logger.info(f"Completed analysis for team {team_id}")
                    except Exception as e:
                        logger.error(f"Error analyzing team {team_id}: {e}")
                        team_analyses[team_id] = {"error": str(e)}
            
            enhanced_data["enhanced_analysis"][season]["teams"] = team_analyses
        
        # Generate comparison reports
        enhanced_data["comparison_reports"] = self.generate_manager_comparison_report(enhanced_data)
        
        # Save the enhanced data
        self.save_enhanced_data(enhanced_data)
        
        elapsed_time = time.time() - start_time
        logger.info(f"Enhanced analysis completed in {elapsed_time:.2f} seconds")
        
        return enhanced_data
    
    def generate_manager_comparison_report(self, enhanced_data: Dict) -> Dict:
        """Generate a comparison report across managers."""
        original_data = enhanced_data["original_data"]
        enhanced_analysis = enhanced_data["enhanced_analysis"]
        
        comparison_report = {
            "manager_rankings": {},
            "season_rankings": {},
            "performance_insights": {}
        }
        
        # Rank managers by various metrics
        managers = original_data["managers"]
        
        # Career win percentage ranking
        win_percentage_ranking = sorted(
            managers.items(),
            key=lambda x: x[1]["career_stats"].get("win_percentage", 0),
            reverse=True
        )
        
        # Average points per game ranking
        avg_points_ranking = sorted(
            managers.items(),
            key=lambda x: x[1]["career_stats"].get("average_points_for", 0),
            reverse=True
        )
        
        # Championship ranking
        championship_ranking = sorted(
            managers.items(),
            key=lambda x: x[1]["career_stats"].get("championships", 0),
            reverse=True
        )
        
        comparison_report["manager_rankings"] = {
            "by_win_percentage": [
                {
                    "manager": name,
                    "win_percentage": profile["career_stats"].get("win_percentage", 0),
                    "seasons": profile["career_stats"]["total_seasons"]
                }
                for name, profile in win_percentage_ranking
            ],
            "by_average_points": [
                {
                    "manager": name,
                    "avg_points": profile["career_stats"].get("average_points_for", 0),
                    "seasons": profile["career_stats"]["total_seasons"]
                }
                for name, profile in avg_points_ranking
            ],
            "by_championships": [
                {
                    "manager": name,
                    "championships": profile["career_stats"].get("championships", 0),
                    "total_seasons": profile["career_stats"]["total_seasons"]
                }
                for name, profile in championship_ranking
            ]
        }
        
        # Season-specific rankings
        for season in enhanced_analysis:
            season_teams = enhanced_analysis[season]["teams"]
            
            # Rank by average points per week
            season_avg_points = []
            for team_id, team_analysis in season_teams.items():
                if "season_summary" in team_analysis:
                    season_avg_points.append({
                        "team_id": team_id,
                        "team_name": team_analysis["team_name"],
                        "avg_points": team_analysis["season_summary"]["average_points_per_week"],
                        "consistency": team_analysis["performance_metrics"]["consistency_score"]
                    })
            
            season_avg_points.sort(key=lambda x: x["avg_points"], reverse=True)
            comparison_report["season_rankings"][season] = {
                "by_average_points": season_avg_points
            }
        
        return comparison_report
    
    def save_enhanced_data(self, enhanced_data: Dict) -> None:
        """Save enhanced team analysis data."""
        output_path = Path(self.enhanced_data_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(enhanced_data, f, indent=2)
        
        logger.info(f"Enhanced team analysis saved to {output_path}")
    
    def print_enhanced_summary(self, enhanced_data: Dict) -> None:
        """Print a summary of the enhanced analysis."""
        comparison_report = self.generate_manager_comparison_report(enhanced_data)
        
        print(f"\n=== Enhanced Team Analysis Summary ===")
        print(f"Seasons Processed: {enhanced_data['metadata']['seasons_processed']}")
        
        print(f"\n=== Top Managers by Win Percentage ===")
        for i, ranking in enumerate(comparison_report["manager_rankings"]["by_win_percentage"][:5], 1):
            print(f"{i}. {ranking['manager']}: {ranking['win_percentage']:.3f} ({ranking['seasons']} seasons)")
        
        print(f"\n=== Top Managers by Average Points ===")
        for i, ranking in enumerate(comparison_report["manager_rankings"]["by_average_points"][:5], 1):
            print(f"{i}. {ranking['manager']}: {ranking['avg_points']:.1f} pts/game ({ranking['seasons']} seasons)")
        
        print(f"\n=== Championship Leaders ===")
        for i, ranking in enumerate(comparison_report["manager_rankings"]["by_championships"][:5], 1):
            print(f"{i}. {ranking['manager']}: {ranking['championships']} championships ({ranking['total_seasons']} seasons)")
        
        # Season-specific insights
        for season in enhanced_data["enhanced_analysis"]:
            season_rankings = comparison_report["season_rankings"][season]
            print(f"\n=== {season} Season - Top Scoring Teams ===")
            for i, team in enumerate(season_rankings["by_average_points"][:3], 1):
                print(f"{i}. {team['team_name']}: {team['avg_points']:.1f} pts/week (Consistency: {team['consistency']:.3f})")


def main():
    """Main function to run enhanced team analysis."""
    analyzer = EnhancedTeamAnalyzer()
    
    # Process available seasons
    seasons = [2012]  # Start with 2012 since we have the data
    
    print("=== Enhanced Team Analysis ===")
    print("This will analyze detailed player stats and team performance metrics.")
    print("Note: This may take some time as it scrapes detailed weekly data.")
    
    # Generate enhanced data
    enhanced_data = analyzer.enhance_manager_data(seasons)
    
    # Save to file
    analyzer.save_enhanced_data(enhanced_data)
    
    # Print summary
    analyzer.print_enhanced_summary(enhanced_data)
    
    print(f"\n✅ Enhanced team analysis complete!")
    print(f"📁 Data saved to: {analyzer.enhanced_data_file}")


if __name__ == "__main__":
    main() 