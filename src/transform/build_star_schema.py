"""
Star schema transformation module for the Stag League History project.

This module transforms raw ingested data into a normalized star schema
database as specified in the architecture documentation.
"""

import json
import sqlite3
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class StarSchemaBuilder:
    """Builds and maintains the star schema database from raw data."""
    
    def __init__(self, db_path: str = "data/processed/fantasy.db"):
        """
        Initialize the star schema builder.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database schema
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the database with star schema tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Create dimension tables
            conn.executescript("""
                -- Teams dimension
                CREATE TABLE IF NOT EXISTS dim_team (
                    team_id INTEGER PRIMARY KEY,
                    league_id INTEGER NOT NULL,
                    season INTEGER NOT NULL,
                    franchise_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Players dimension
                CREATE TABLE IF NOT EXISTS dim_player (
                    player_id INTEGER PRIMARY KEY,
                    sleeper_id TEXT UNIQUE,
                    nfl_id TEXT,
                    name TEXT NOT NULL,
                    position TEXT,
                    team TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- League seasons dimension
                CREATE TABLE IF NOT EXISTS dim_league_season (
                    league_season_id INTEGER PRIMARY KEY,
                    league_id INTEGER NOT NULL,
                    season INTEGER NOT NULL,
                    league_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(league_id, season)
                );
                
                -- Fact table for team weekly performance
                CREATE TABLE IF NOT EXISTS fact_team_week (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id INTEGER NOT NULL,
                    league_season_id INTEGER NOT NULL,
                    week INTEGER NOT NULL,
                    season INTEGER NOT NULL,
                    pts_for REAL,
                    pts_against REAL,
                    result TEXT CHECK(result IN ('W', 'L', 'T')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES dim_team(team_id),
                    FOREIGN KEY (league_season_id) REFERENCES dim_league_season(league_season_id),
                    UNIQUE(team_id, week, season)
                );
                
                -- Fact table for player weekly performance
                CREATE TABLE IF NOT EXISTS fact_player_week (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER NOT NULL,
                    team_id INTEGER NOT NULL,
                    week INTEGER NOT NULL,
                    season INTEGER NOT NULL,
                    fantasy_points REAL,
                    lineup_slot TEXT,
                    raw_stats TEXT,  -- JSON string
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (player_id) REFERENCES dim_player(player_id),
                    FOREIGN KEY (team_id) REFERENCES dim_team(team_id),
                    UNIQUE(player_id, team_id, week, season)
                );
                
                -- Fact table for draft picks
                CREATE TABLE IF NOT EXISTS fact_draft_pick (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    league_id INTEGER NOT NULL,
                    season INTEGER NOT NULL,
                    player_id INTEGER NOT NULL,
                    team_id INTEGER NOT NULL,
                    nomination_price INTEGER,
                    final_price INTEGER,
                    pick_overall INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (player_id) REFERENCES dim_player(player_id),
                    FOREIGN KEY (team_id) REFERENCES dim_team(team_id)
                );
                
                -- Create indexes for performance
                CREATE INDEX IF NOT EXISTS idx_fact_team_week_team_season ON fact_team_week(team_id, season);
                CREATE INDEX IF NOT EXISTS idx_fact_team_week_week_season ON fact_team_week(week, season);
                CREATE INDEX IF NOT EXISTS idx_fact_player_week_player_season ON fact_player_week(player_id, season);
                CREATE INDEX IF NOT EXISTS idx_fact_player_week_team_week ON fact_player_week(team_id, week, season);
            """)
            
            logger.info(f"Initialized database schema: {self.db_path}")
    
    def build_season_data(self, season: int, force_rebuild: bool = False) -> None:
        """
        Build star schema data for a specific season.
        
        Args:
            season: NFL season year
            force_rebuild: Whether to force rebuild existing data
        """
        logger.info(f"Building star schema for season {season}")
        
        # Check if data already exists
        if not force_rebuild and self._season_data_exists(season):
            logger.info(f"Season {season} data already exists, skipping")
            return
        
        # Load raw schedule data
        schedule_data = self._load_schedule_data(season)
        if not schedule_data:
            logger.warning(f"No schedule data found for season {season}")
            return
        
        # Extract teams and create dimension records
        teams = self._extract_teams_from_schedule(schedule_data, season)
        self._upsert_teams(teams)
        
        # Create league season record
        league_id = self._get_league_id_for_season(season)
        self._upsert_league_season(league_id, season)
        
        # Build team weekly facts
        team_weeks = self._build_team_weeks(schedule_data, season)
        self._upsert_team_weeks(team_weeks)
        
        # Build player weekly facts (placeholder for now)
        # player_weeks = self._build_player_weeks(schedule_data, season)
        # self._upsert_player_weeks(player_weeks)
        
        logger.info(f"Completed building star schema for season {season}")
    
    def _season_data_exists(self, season: int) -> bool:
        """Check if data for a season already exists in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM fact_team_week WHERE season = ?",
                (season,)
            )
            count = cursor.fetchone()[0]
            return count > 0
    
    def _load_schedule_data(self, season: int) -> Optional[List[Dict[str, Any]]]:
        """Load raw schedule data for a season."""
        schedule_file = Path(f"data/processed/schedule/{season}/schedule.csv")
        
        if not schedule_file.exists():
            logger.warning(f"Schedule file not found: {schedule_file}")
            return None
        
        try:
            df = pd.read_csv(schedule_file)
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Failed to load schedule data: {e}")
            return None
    
    def _extract_teams_from_schedule(self, schedule_data: List[Dict[str, Any]], season: int) -> List[Dict[str, Any]]:
        """Extract unique teams from schedule data."""
        teams = set()
        league_id = self._get_league_id_for_season(season)
        
        for game in schedule_data:
            # Add home team
            teams.add((
                int(game['home_team_id']),
                league_id,
                season,
                game['home_team']
            ))
            
            # Add away team
            teams.add((
                int(game['away_team_id']),
                league_id,
                season,
                game['away_team']
            ))
        
        return [
            {
                'team_id': team_id,
                'league_id': league_id,
                'season': season,
                'franchise_name': franchise_name
            }
            for team_id, league_id, season, franchise_name in teams
        ]
    
    def _get_league_id_for_season(self, season: int) -> int:
        """Get the league ID for a given season."""
        if season == 2011:
            return 400491
        else:
            return 864504
    
    def _upsert_teams(self, teams: List[Dict[str, Any]]) -> None:
        """Insert or update team dimension records."""
        with sqlite3.connect(self.db_path) as conn:
            for team in teams:
                conn.execute("""
                    INSERT OR REPLACE INTO dim_team 
                    (team_id, league_id, season, franchise_name)
                    VALUES (?, ?, ?, ?)
                """, (
                    team['team_id'],
                    team['league_id'],
                    team['season'],
                    team['franchise_name']
                ))
            
            logger.info(f"Upserted {len(teams)} team records")
    
    def _upsert_league_season(self, league_id: int, season: int) -> None:
        """Insert or update league season dimension record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO dim_league_season 
                (league_id, season, league_name)
                VALUES (?, ?, ?)
            """, (league_id, season, f"Stag League {season}"))
            
            logger.info(f"Upserted league season record: {league_id}/{season}")
    
    def _build_team_weeks(self, schedule_data: List[Dict[str, Any]], season: int) -> List[Dict[str, Any]]:
        """Build team weekly fact records from schedule data."""
        team_weeks = []
        league_id = self._get_league_id_for_season(season)
        
        for game in schedule_data:
            week = int(game['week'])
            
            # Determine result for home team
            home_result = 'W' if game['home_points'] > game['away_points'] else 'L'
            if game['home_points'] == game['away_points']:
                home_result = 'T'
            
            # Determine result for away team
            away_result = 'W' if game['away_points'] > game['home_points'] else 'L'
            if game['away_points'] == game['home_points']:
                away_result = 'T'
            
            # Home team week record
            team_weeks.append({
                'team_id': int(game['home_team_id']),
                'league_season_id': f"{league_id}_{season}",
                'week': week,
                'season': season,
                'pts_for': float(game['home_points']),
                'pts_against': float(game['away_points']),
                'result': home_result
            })
            
            # Away team week record
            team_weeks.append({
                'team_id': int(game['away_team_id']),
                'league_season_id': f"{league_id}_{season}",
                'week': week,
                'season': season,
                'pts_for': float(game['away_points']),
                'pts_against': float(game['home_points']),
                'result': away_result
            })
        
        return team_weeks
    
    def _upsert_team_weeks(self, team_weeks: List[Dict[str, Any]]) -> None:
        """Insert or update team weekly fact records."""
        with sqlite3.connect(self.db_path) as conn:
            for week in team_weeks:
                conn.execute("""
                    INSERT OR REPLACE INTO fact_team_week 
                    (team_id, league_season_id, week, season, pts_for, pts_against, result)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    week['team_id'],
                    week['league_season_id'],
                    week['week'],
                    week['season'],
                    week['pts_for'],
                    week['pts_against'],
                    week['result']
                ))
            
            logger.info(f"Upserted {len(team_weeks)} team week records")
    
    def get_team_standings(self, season: int, week: Optional[int] = None) -> pd.DataFrame:
        """
        Get team standings for a season and optional week.
        
        Args:
            season: NFL season year
            week: Week number (None for season totals)
            
        Returns:
            DataFrame with team standings
        """
        with sqlite3.connect(self.db_path) as conn:
            if week:
                # Weekly standings
                query = """
                    SELECT 
                        t.franchise_name,
                        tw.week,
                        tw.pts_for,
                        tw.pts_against,
                        tw.result,
                        ROW_NUMBER() OVER (ORDER BY tw.pts_for DESC) as rank
                    FROM fact_team_week tw
                    JOIN dim_team t ON tw.team_id = t.team_id
                    WHERE tw.season = ? AND tw.week = ?
                    ORDER BY tw.pts_for DESC
                """
                df = pd.read_sql_query(query, conn, params=(season, week))
            else:
                # Season standings
                query = """
                    SELECT 
                        t.franchise_name,
                        COUNT(*) as games_played,
                        SUM(CASE WHEN tw.result = 'W' THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN tw.result = 'L' THEN 1 ELSE 0 END) as losses,
                        SUM(CASE WHEN tw.result = 'T' THEN 1 ELSE 0 END) as ties,
                        SUM(tw.pts_for) as total_points_for,
                        SUM(tw.pts_against) as total_points_against,
                        AVG(tw.pts_for) as avg_points_for,
                        AVG(tw.pts_against) as avg_points_against
                    FROM fact_team_week tw
                    JOIN dim_team t ON tw.team_id = t.team_id
                    WHERE tw.season = ?
                    GROUP BY t.team_id, t.franchise_name
                    ORDER BY wins DESC, total_points_for DESC
                """
                df = pd.read_sql_query(query, conn, params=(season,))
        
        return df
    
    def validate_data(self, season: int) -> Dict[str, Any]:
        """
        Validate the star schema data for a season.
        
        Args:
            season: NFL season year
            
        Returns:
            Dictionary with validation results
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check team week counts
            team_week_counts = pd.read_sql_query("""
                SELECT 
                    t.franchise_name,
                    COUNT(*) as games_played
                FROM fact_team_week tw
                JOIN dim_team t ON tw.team_id = t.team_id
                WHERE tw.season = ?
                GROUP BY t.team_id, t.franchise_name
                ORDER BY games_played DESC
            """, conn, params=(season,))
            
            # Check for data consistency
            validation_results = {
                'season': season,
                'total_teams': len(team_week_counts),
                'team_week_counts': team_week_counts.to_dict('records'),
                'validation_passed': True,
                'issues': []
            }
            
            # Validate that all teams have the same number of games
            if len(team_week_counts) > 0:
                expected_games = team_week_counts['games_played'].iloc[0]
                teams_with_wrong_count = team_week_counts[
                    team_week_counts['games_played'] != expected_games
                ]
                
                if len(teams_with_wrong_count) > 0:
                    validation_results['validation_passed'] = False
                    validation_results['issues'].append(
                        f"Teams with incorrect game count: {teams_with_wrong_count['franchise_name'].tolist()}"
                    )
            
            return validation_results 