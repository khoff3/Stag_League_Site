#!/usr/bin/env python3
"""
Data Join Example: Raw Player Scores + Playoff Schedule

This script demonstrates how to join the raw player scores (from validation)
with the playoff-annotated schedule data for comprehensive analysis.

Key Concepts:
1. Raw player data: data/raw/{season}/week_{week}/team_{id}.json
2. Annotated schedule: data/processed/schedule/{season}/schedule_annotated.csv
3. Join keys: season, week, team_id
4. Validation: Compare reconstructed vs. schedule scores
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class DataJoinExample:
    """Demonstrates joining raw player scores with playoff schedule data."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
    
    def load_annotated_schedule(self, season: int) -> pd.DataFrame:
        """Load playoff-annotated schedule."""
        schedule_path = self.data_dir / "processed" / "schedule" / str(season) / "schedule_annotated.csv"
        if not schedule_path.exists():
            raise FileNotFoundError(f"Annotated schedule not found: {schedule_path}")
        
        schedule = pd.read_csv(schedule_path)
        print(f"📊 Loaded {len(schedule)} games from annotated schedule")
        return schedule
    
    def load_raw_player_data(self, season: int, week: int, team_id: str) -> Optional[Dict]:
        """Load raw player data for a team/week."""
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
            lineup_status = player.get('lineup_status', 'starter')
            position = player.get('position', '')
            
            # Consider BN (bench) as non-starter
            if lineup_status == 'starter' and position != 'BN':
                starters.append(player)
        
        return starters
    
    def calculate_team_score(self, starters: List[Dict]) -> float:
        """Calculate team score from starter fantasy points."""
        return sum(player.get('fantasy_points', 0) for player in starters)
    
    def demonstrate_data_join(self, season: int, week: int) -> Dict:
        """
        Demonstrate the complete data joining process.
        
        This shows how to:
        1. Load playoff-annotated schedule
        2. Load raw player data
        3. Join them using common keys
        4. Validate and analyze the joined data
        """
        print(f"\n🔗 Data Join Demonstration (Season {season}, Week {week})")
        print("=" * 60)
        
        # Step 1: Load annotated schedule
        print("\n1️⃣ Loading playoff-annotated schedule...")
        schedule = self.load_annotated_schedule(season)
        
        # Filter for the specific week
        week_games = schedule[schedule['week'] == week]
        playoff_games = week_games[week_games['is_playoff'] == True]
        
        print(f"   Week {week} games: {len(week_games)} total, {len(playoff_games)} playoff")
        
        # Step 2: Load raw player data for each team
        print("\n2️⃣ Loading raw player data...")
        team_data = {}
        for _, game in week_games.iterrows():
            home_team_id = game['home_team_id']
            away_team_id = game['away_team_id']
            
            # Load home team data
            if home_team_id not in team_data:
                home_data = self.load_raw_player_data(season, week, home_team_id)
                if home_data:
                    team_data[home_team_id] = home_data
                    print(f"   ✅ Loaded Team {home_team_id} ({game['home_team']})")
                else:
                    print(f"   ❌ Missing data for Team {home_team_id}")
            
            # Load away team data
            if away_team_id not in team_data:
                away_data = self.load_raw_player_data(season, week, away_team_id)
                if away_data:
                    team_data[away_team_id] = away_data
                    print(f"   ✅ Loaded Team {away_team_id} ({game['away_team']})")
                else:
                    print(f"   ❌ Missing data for Team {away_team_id}")
        
        # Step 3: Join and analyze data
        print("\n3️⃣ Joining and analyzing data...")
        join_results = []
        
        for _, game in week_games.iterrows():
            game_id = game['game_id']
            home_team_id = game['home_team_id']
            away_team_id = game['away_team_id']
            
            # Get raw player data for both teams
            home_raw_data = team_data.get(home_team_id)
            away_raw_data = team_data.get(away_team_id)
            
            if not home_raw_data or not away_raw_data:
                print(f"   ⚠️  Missing raw data for game {game_id}")
                continue
            
            # Extract starters and calculate scores
            home_starters = self.get_team_starters(home_raw_data)
            away_starters = self.get_team_starters(away_raw_data)
            
            home_reconstructed_score = self.calculate_team_score(home_starters)
            away_reconstructed_score = self.calculate_team_score(away_starters)
            
            # Get schedule scores
            home_schedule_score = game['home_points']
            away_schedule_score = game['away_points']
            
            # Calculate differences
            home_diff = abs(home_reconstructed_score - home_schedule_score)
            away_diff = abs(away_reconstructed_score - away_schedule_score)
            
            # Join result
            join_result = {
                "game_id": game_id,
                "week": week,
                "is_playoff": game['is_playoff'],
                "playoff_round": game.get('playoff_round_name', ''),
                "bracket": game.get('bracket', ''),
                
                # Schedule data (from annotated schedule)
                "schedule_scores": {
                    "home": home_schedule_score,
                    "away": away_schedule_score
                },
                
                # Raw player data (from team JSON files)
                "raw_player_data": {
                    "home_starters": len(home_starters),
                    "away_starters": len(away_starters),
                    "home_reconstructed_score": home_reconstructed_score,
                    "away_reconstructed_score": away_reconstructed_score
                },
                
                # Validation results
                "validation": {
                    "home_diff": home_diff,
                    "away_diff": away_diff,
                    "home_valid": home_diff < 0.1,
                    "away_valid": away_diff < 0.1,
                    "both_valid": home_diff < 0.1 and away_diff < 0.1
                },
                
                # Team names for display
                "home_team": game['home_team'],
                "away_team": game['away_team']
            }
            
            join_results.append(join_result)
            
            # Print game analysis
            print(f"\n   📋 Game {game_id}: {game['home_team']} vs {game['away_team']}")
            if game['is_playoff']:
                print(f"      🏆 Playoff: {game.get('playoff_round_name', 'Unknown')} | {game.get('bracket', 'Unknown')}")
            
            print(f"      📊 Schedule: {home_schedule_score:.1f} - {away_schedule_score:.1f}")
            print(f"      🔧 Reconstructed: {home_reconstructed_score:.1f} - {away_reconstructed_score:.1f}")
            print(f"      ✅ Validation: {'PASS' if join_result['validation']['both_valid'] else 'FAIL'}")
            
            if not join_result['validation']['both_valid']:
                print(f"      ⚠️  Differences: Home {home_diff:.1f}, Away {away_diff:.1f}")
        
        # Step 4: Generate summary
        print("\n4️⃣ Generating join summary...")
        total_games = len(join_results)
        playoff_games = [r for r in join_results if r['is_playoff']]
        valid_games = [r for r in join_results if r['validation']['both_valid']]
        
        summary = {
            "season": season,
            "week": week,
            "total_games": total_games,
            "playoff_games": len(playoff_games),
            "valid_games": len(valid_games),
            "validation_rate": len(valid_games) / total_games if total_games > 0 else 0,
            "join_results": join_results
        }
        
        print(f"\n📈 Join Summary:")
        print(f"   Total games: {total_games}")
        print(f"   Playoff games: {len(playoff_games)}")
        print(f"   Valid games: {len(valid_games)}/{total_games}")
        print(f"   Validation rate: {summary['validation_rate']*100:.1f}%")
        
        return summary
    
    def analyze_validation_discrepancies(self, join_results: List[Dict]) -> Dict:
        """Analyze validation discrepancies to understand differences."""
        print(f"\n🔍 Analyzing Validation Discrepancies")
        print("=" * 50)
        
        failed_games = [r for r in join_results if not r['validation']['both_valid']]
        
        if not failed_games:
            print("✅ No validation discrepancies found!")
            return {"discrepancies": []}
        
        print(f"Found {len(failed_games)} games with validation discrepancies:")
        
        discrepancy_analysis = []
        for game in failed_games:
            home_diff = game['validation']['home_diff']
            away_diff = game['validation']['away_diff']
            
            print(f"\n   🎯 Game {game['game_id']}: {game['home_team']} vs {game['away_team']}")
            print(f"      Schedule: {game['schedule_scores']['home']:.1f} - {game['schedule_scores']['away']:.1f}")
            print(f"      Reconstructed: {game['raw_player_data']['home_reconstructed_score']:.1f} - {game['raw_player_data']['away_reconstructed_score']:.1f}")
            print(f"      Differences: Home {home_diff:.1f}, Away {away_diff:.1f}")
            
            if game['is_playoff']:
                print(f"      🏆 Playoff: {game['playoff_round']}")
            
            # Analyze potential causes
            causes = []
            if home_diff > 1.0:
                causes.append("Large home team difference")
            if away_diff > 1.0:
                causes.append("Large away team difference")
            if home_diff > 0.5 and away_diff > 0.5:
                causes.append("Both teams have significant differences")
            
            discrepancy_analysis.append({
                "game_id": game['game_id'],
                "home_diff": home_diff,
                "away_diff": away_diff,
                "is_playoff": game['is_playoff'],
                "potential_causes": causes
            })
        
        return {"discrepancies": discrepancy_analysis}
    
    def export_join_results(self, summary: Dict, output_path: str) -> None:
        """Export join results to JSON."""
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\n📁 Join results exported to: {output_path}")
    
    def create_join_dataframe(self, join_results: List[Dict]) -> pd.DataFrame:
        """Create a pandas DataFrame from join results."""
        # Flatten the nested structure for DataFrame
        flattened_data = []
        
        for result in join_results:
            row = {
                "game_id": result["game_id"],
                "week": result["week"],
                "is_playoff": result["is_playoff"],
                "playoff_round": result["playoff_round"],
                "bracket": result["bracket"],
                "home_team": result["home_team"],
                "away_team": result["away_team"],
                "home_schedule_score": result["schedule_scores"]["home"],
                "away_schedule_score": result["schedule_scores"]["away"],
                "home_reconstructed_score": result["raw_player_data"]["home_reconstructed_score"],
                "away_reconstructed_score": result["raw_player_data"]["away_reconstructed_score"],
                "home_starters": result["raw_player_data"]["home_starters"],
                "away_starters": result["raw_player_data"]["away_starters"],
                "home_diff": result["validation"]["home_diff"],
                "away_diff": result["validation"]["away_diff"],
                "both_valid": result["validation"]["both_valid"]
            }
            flattened_data.append(row)
        
        df = pd.DataFrame(flattened_data)
        return df


def main():
    """Main function to demonstrate data joining."""
    print("🔗 Data Join Example: Raw Player Scores + Playoff Schedule")
    print("=" * 60)
    
    # Example: Join data for 2012 Week 15 (playoff week)
    season = 2012
    week = 15
    
    analyzer = DataJoinExample()
    
    try:
        # Demonstrate the join process
        join_summary = analyzer.demonstrate_data_join(season, week)
        
        # Analyze discrepancies
        discrepancy_analysis = analyzer.analyze_validation_discrepancies(join_summary['join_results'])
        
        # Create DataFrame
        df = analyzer.create_join_dataframe(join_summary['join_results'])
        print(f"\n📊 DataFrame shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        
        # Show playoff games
        playoff_df = df[df['is_playoff'] == True]
        if len(playoff_df) > 0:
            print(f"\n🏆 Playoff Games Summary:")
            print(playoff_df[['home_team', 'away_team', 'playoff_round', 'both_valid']].to_string(index=False))
        
        # Export results
        output_path = f"data_join_example_{season}_week_{week}.json"
        analyzer.export_join_results(join_summary, output_path)
        
        print(f"\n✅ Data join demonstration completed!")
        print(f"📁 Results saved to: {output_path}")
        
    except Exception as e:
        print(f"❌ Error during data join: {e}")
        raise


if __name__ == "__main__":
    main() 