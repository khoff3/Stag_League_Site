"""
NFL Data Validation Module

This module provides data validation and cleaning functionality for NFL Fantasy Football data.
It ensures data quality, consistency, and completeness.
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of data validation."""
    is_valid: bool
    errors: List[str] = None
    warnings: List[str] = None
    cleaned_data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.cleaned_data is None:
            self.cleaned_data = {}

class DataValidator:
    """Validates and cleans NFL Fantasy Football data."""
    
    # Valid positions
    VALID_POSITIONS = {
        'QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DST', 'BN', 'W/R', 'W/T', 'Q/W/R/T'
    }
    
    # Valid NFL teams
    VALID_NFL_TEAMS = {
        'ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE', 'DAL', 'DEN',
        'DET', 'GB', 'HOU', 'IND', 'JAX', 'KC', 'LAC', 'LAR', 'LV', 'MIA',
        'MIN', 'NE', 'NO', 'NYG', 'NYJ', 'PHI', 'PIT', 'SEA', 'SF', 'TB',
        'TEN', 'WAS'
    }
    
    # Required fields for player data
    REQUIRED_FIELDS = ['name', 'position']
    
    # Numeric fields that should be integers
    INTEGER_FIELDS = {
        'passing_yards', 'rushing_yards', 'receiving_yards',
        'passing_tds', 'rushing_tds', 'receiving_tds', 'interceptions',
        'fumbles_lost', 'two_point_conversions'
    }
    
    # Numeric fields that should be floats
    FLOAT_FIELDS = {'fantasy_points'}
    
    @classmethod
    def validate_player_data(cls, player_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate and clean player data.
        
        Args:
            player_data: Raw player data dictionary
            
        Returns:
            ValidationResult with validation status and cleaned data
        """
        result = ValidationResult(is_valid=True)
        cleaned_data = player_data.copy()
        
        # Check required fields
        for field in cls.REQUIRED_FIELDS:
            if not player_data.get(field):
                result.errors.append(f"Missing required field: {field}")
                result.is_valid = False
        
        # Validate and clean name
        if 'name' in player_data:
            name = cls._clean_name(player_data['name'])
            if name:
                cleaned_data['name'] = name
            else:
                result.errors.append("Invalid player name")
                result.is_valid = False
        
        # Validate and clean position
        if 'position' in player_data:
            position = cls._clean_position(player_data['position'])
            if position:
                cleaned_data['position'] = position
            else:
                result.errors.append(f"Invalid position: {player_data['position']}")
                result.is_valid = False
        
        # Validate and clean NFL team
        if 'nfl_team' in player_data:
            nfl_team = cls._clean_nfl_team(player_data['nfl_team'])
            if nfl_team:
                cleaned_data['nfl_team'] = nfl_team
            else:
                result.warnings.append(f"Invalid NFL team: {player_data['nfl_team']}")
        
        # Clean numeric fields
        for field in cls.INTEGER_FIELDS:
            if field in player_data:
                value = cls._clean_integer(player_data[field])
                cleaned_data[field] = value
                if value is None:
                    result.warnings.append(f"Invalid integer value for {field}: {player_data[field]}")
        
        for field in cls.FLOAT_FIELDS:
            if field in player_data:
                value = cls._clean_float(player_data[field])
                cleaned_data[field] = value
                if value is None:
                    result.warnings.append(f"Invalid float value for {field}: {player_data[field]}")
        
        # Calculate derived fields
        cls._calculate_derived_fields(cleaned_data)
        
        # Validate data consistency
        cls._validate_consistency(cleaned_data, result)
        
        result.cleaned_data = cleaned_data
        return result
    
    @classmethod
    def validate_team_data(cls, team_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate team data structure.
        
        Args:
            team_data: Team data dictionary
            
        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=True)
        
        # Check required structure
        if 'players' not in team_data:
            result.errors.append("Missing 'players' field in team data")
            result.is_valid = False
            return result
        
        if not isinstance(team_data['players'], list):
            result.errors.append("'players' field must be a list")
            result.is_valid = False
            return result
        
        # Validate each player
        valid_players = []
        for i, player in enumerate(team_data['players']):
            if not isinstance(player, dict):
                result.errors.append(f"Player {i} is not a dictionary")
                continue
            
            player_result = cls.validate_player_data(player)
            if player_result.is_valid:
                valid_players.append(player_result.cleaned_data)
            else:
                result.errors.extend([f"Player {i}: {error}" for error in player_result.errors])
                result.warnings.extend([f"Player {i}: {warning}" for warning in player_result.warnings])
        
        # Update team data with validated players
        cleaned_team_data = team_data.copy()
        cleaned_team_data['players'] = valid_players
        
        # Add metadata
        cleaned_team_data['_validation'] = {
            'validated_at': datetime.now().isoformat(),
            'total_players': len(valid_players),
            'validation_errors': len(result.errors),
            'validation_warnings': len(result.warnings)
        }
        
        result.cleaned_data = cleaned_team_data
        return result
    
    @classmethod
    def _clean_name(cls, name: str) -> Optional[str]:
        """Clean and validate player name."""
        if not name or not isinstance(name, str):
            return None
        
        # Remove extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', name.strip())
        
        # Check for reasonable name length
        if len(cleaned) < 2 or len(cleaned) > 50:
            return None
        
        # Check for valid characters (letters, spaces, hyphens, periods)
        if not re.match(r'^[A-Za-z\s\-\.]+$', cleaned):
            return None
        
        return cleaned
    
    @classmethod
    def _clean_position(cls, position: str) -> Optional[str]:
        """Clean and validate position."""
        if not position or not isinstance(position, str):
            return None
        
        # Normalize position
        cleaned = position.strip().upper()
        
        # Handle common variations
        position_mapping = {
            'DEFENSE': 'DEF',
            'DEF/ST': 'DEF',
            'DST': 'DEF',
            'BENCH': 'BN',
            'FLEX': 'W/R',
            'SUPERFLEX': 'Q/W/R/T'
        }
        
        if cleaned in position_mapping:
            cleaned = position_mapping[cleaned]
        
        return cleaned if cleaned in cls.VALID_POSITIONS else None
    
    @classmethod
    def _clean_nfl_team(cls, team: str) -> Optional[str]:
        """Clean and validate NFL team abbreviation."""
        if not team or not isinstance(team, str):
            return None
        
        # Normalize team abbreviation
        cleaned = team.strip().upper()
        
        # Handle common variations
        team_mapping = {
            'LA': 'LAR',  # Los Angeles Rams
            'OAK': 'LV',  # Oakland Raiders -> Las Vegas Raiders
            'SD': 'LAC',  # San Diego Chargers -> Los Angeles Chargers
        }
        
        if cleaned in team_mapping:
            cleaned = team_mapping[cleaned]
        
        return cleaned if cleaned in cls.VALID_NFL_TEAMS else None
    
    @classmethod
    def _clean_integer(cls, value: Any) -> Optional[int]:
        """Clean and convert value to integer."""
        if value is None:
            return 0
        
        if isinstance(value, int):
            return value
        
        if isinstance(value, float):
            return int(value)
        
        if isinstance(value, str):
            # Extract numeric value from string
            match = re.search(r'(\d+)', value)
            if match:
                return int(match.group(1))
        
        return None
    
    @classmethod
    def _clean_float(cls, value: Any) -> Optional[float]:
        """Clean and convert value to float."""
        if value is None:
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Extract numeric value from string
            match = re.search(r'(\d+\.?\d*)', value)
            if match:
                return float(match.group(1))
        
        return None
    
    @classmethod
    def _calculate_derived_fields(cls, player_data: Dict[str, Any]) -> None:
        """Calculate derived fields from player data."""
        # Calculate total touchdowns
        td_fields = ['passing_tds', 'rushing_tds', 'receiving_tds']
        total_tds = sum(player_data.get(field, 0) for field in td_fields)
        player_data['touchdowns'] = total_tds
        
        # Determine lineup status based on position
        position = player_data.get('position', '').upper()
        if position in ['QB', 'RB', 'WR', 'TE', 'W/R', 'K', 'DEF']:
            player_data['lineup_status'] = 'starter'
        elif position == 'BN':
            player_data['lineup_status'] = 'bench'
        else:
            player_data['lineup_status'] = 'unknown'
    
    @classmethod
    def _validate_consistency(cls, player_data: Dict[str, Any], result: ValidationResult) -> None:
        """Validate data consistency."""
        # Check for unrealistic values
        fantasy_points = player_data.get('fantasy_points', 0)
        if fantasy_points is not None and fantasy_points > 100:  # Very high fantasy points
            result.warnings.append(f"Unusually high fantasy points: {fantasy_points}")
        
        # Check for negative values
        for field in cls.INTEGER_FIELDS:
            value = player_data.get(field, 0)
            if value is not None and value < 0:
                result.warnings.append(f"Negative value for {field}: {value}")
        
        # Check for unrealistic yardage
        passing_yds = player_data.get('passing_yards', 0)
        rushing_yds = player_data.get('rushing_yards', 0)
        receiving_yds = player_data.get('receiving_yards', 0)
        
        if passing_yds is not None and passing_yds > 600:  # Very high passing yards
            result.warnings.append(f"Unusually high passing yards: {passing_yds}")
        if rushing_yds is not None and rushing_yds > 300:  # Very high rushing yards
            result.warnings.append(f"Unusually high rushing yards: {rushing_yds}")
        if receiving_yds is not None and receiving_yds > 300:  # Very high receiving yards
            result.warnings.append(f"Unusually high receiving yards: {receiving_yds}")

class DataQualityReport:
    """Generates data quality reports."""
    
    @classmethod
    def generate_team_report(cls, team_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a data quality report for team data."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_players': len(team_data.get('players', [])),
            'data_quality': {},
            'issues': []
        }
        
        if 'players' not in team_data:
            report['issues'].append("No players data found")
            return report
        
        players = team_data['players']
        
        # Calculate quality metrics
        report['data_quality'] = {
            'players_with_names': sum(1 for p in players if p.get('name')),
            'players_with_positions': sum(1 for p in players if p.get('position')),
            'players_with_nfl_teams': sum(1 for p in players if p.get('nfl_team')),
            'players_with_fantasy_points': sum(1 for p in players if 'fantasy_points' in p),
            'average_fantasy_points': sum(p.get('fantasy_points', 0) for p in players) / max(len(players), 1),
            'total_fantasy_points': sum(p.get('fantasy_points', 0) for p in players)
        }
        
        # Check for issues
        for i, player in enumerate(players):
            if not player.get('name'):
                report['issues'].append(f"Player {i}: Missing name")
            if not player.get('position'):
                report['issues'].append(f"Player {i}: Missing position")
            if player.get('fantasy_points', 0) < 0:
                report['issues'].append(f"Player {i}: Negative fantasy points")
        
        return report
    
    @classmethod
    def print_report(cls, report: Dict[str, Any]) -> None:
        """Print a formatted data quality report."""
        print("\n=== DATA QUALITY REPORT ===")
        print(f"Generated: {report['timestamp']}")
        print(f"Total Players: {report['total_players']}")
        
        print("\n--- Data Quality Metrics ---")
        quality = report['data_quality']
        print(f"Players with names: {quality['players_with_names']}/{report['total_players']}")
        print(f"Players with positions: {quality['players_with_positions']}/{report['total_players']}")
        print(f"Players with NFL teams: {quality['players_with_nfl_teams']}/{report['total_players']}")
        print(f"Players with fantasy points: {quality['players_with_fantasy_points']}/{report['total_players']}")
        print(f"Average fantasy points: {quality['average_fantasy_points']:.2f}")
        print(f"Total fantasy points: {quality['total_fantasy_points']:.2f}")
        
        if report['issues']:
            print(f"\n--- Issues Found ({len(report['issues'])}) ---")
            for issue in report['issues']:
                print(f"  • {issue}")
        else:
            print("\n--- No Issues Found ---")
        
        print("=" * 30) 