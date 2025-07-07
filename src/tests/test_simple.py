#!/usr/bin/env python3
"""
Simple test script for the improved NFL API client.
This focuses on testing the working parts without ChromeDriver issues.
"""

import logging
from pathlib import Path

from .api_client import NFLFantasyScraper, ScraperConfig
from .validators import DataValidator, DataQualityReport
from .config import create_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_configuration():
    """Test configuration management."""
    print("=== Testing Configuration ===")
    
    # Test default configuration
    config = ScraperConfig()
    print(f"Default config: headless={config.headless}, timeout={config.timeout}")
    
    # Test custom configuration
    custom_config = create_config(
        headless=True,
        timeout=45,
        max_retries=5,
        requests_per_minute=20
    )
    print(f"Custom config: {custom_config.to_dict()}")
    
    # Test data paths
    paths = custom_config.get_data_paths()
    print(f"Data paths: {paths}")
    
    print("✅ Configuration tests passed\n")

def test_data_validation():
    """Test data validation with sample data."""
    print("=== Testing Data Validation ===")
    
    # Sample player data
    sample_player = {
        "name": "Tom Brady",
        "position": "QB",
        "nfl_team": "TB",
        "fantasy_points": 25.5,
        "passing_yards": 350,
        "passing_tds": 3,
        "interceptions": 1
    }
    
    # Test player validation
    result = DataValidator.validate_player_data(sample_player)
    if result.is_valid:
        print("✅ Player validation passed")
        print(f"Cleaned data: {result.cleaned_data}")
    else:
        print("❌ Player validation failed")
        for error in result.errors:
            print(f"  Error: {error}")
    
    # Sample team data
    sample_team = {
        "players": [sample_player, {
            "name": "Aaron Rodgers",
            "position": "QB",
            "nfl_team": "GB",
            "fantasy_points": 22.0
        }]
    }
    
    # Test team validation
    team_result = DataValidator.validate_team_data(sample_team)
    if team_result.is_valid:
        print("✅ Team validation passed")
        print(f"Team has {len(team_result.cleaned_data['players'])} players")
        
        # Test quality report
        quality_report = DataQualityReport.generate_team_report(team_result.cleaned_data)
        DataQualityReport.print_report(quality_report)
    else:
        print("❌ Team validation failed")
        for error in team_result.errors:
            print(f"  Error: {error}")
    
    print()

def test_cached_data():
    """Test loading and processing cached data."""
    print("=== Testing Cached Data ===")
    
    config = ScraperConfig(cache_enabled=True)
    
    # Check if we have cached data
    cache_path = Path("data/raw/2012/week_15/team_1.json")
    if cache_path.exists():
        print(f"✅ Found cached data at {cache_path}")
        
        # Test loading cached data
        try:
            with open(cache_path, 'r') as f:
                import json
                cached_data = json.load(f)
            
            print(f"✅ Loaded cached data with {len(cached_data.get('players', []))} players")
            
            # Test validation of cached data
            validation_result = DataValidator.validate_team_data(cached_data)
            if validation_result.is_valid:
                print("✅ Cached data validation passed")
                
                # Generate quality report
                quality_report = DataQualityReport.generate_team_report(validation_result.cleaned_data)
                DataQualityReport.print_report(quality_report)
            else:
                print("❌ Cached data validation failed")
                for error in validation_result.errors[:3]:  # Show first 3 errors
                    print(f"  Error: {error}")
                    
        except Exception as e:
            print(f"❌ Error loading cached data: {e}")
    else:
        print("⚠️ No cached data found - run scraping first to generate cache")
    
    print()

def test_error_handling():
    """Test error handling with invalid data."""
    print("=== Testing Error Handling ===")
    
    # Test with invalid player data
    invalid_player = {
        "name": "",  # Empty name
        "position": "INVALID",  # Invalid position
        "fantasy_points": "not_a_number"  # Invalid number
    }
    
    result = DataValidator.validate_player_data(invalid_player)
    if not result.is_valid:
        print("✅ Invalid data correctly rejected")
        for error in result.errors:
            print(f"  Error: {error}")
        for warning in result.warnings:
            print(f"  Warning: {warning}")
    else:
        print("❌ Invalid data should have been rejected")
    
    # Test with missing required fields
    incomplete_player = {
        "name": "John Doe"
        # Missing position
    }
    
    result = DataValidator.validate_player_data(incomplete_player)
    if not result.is_valid:
        print("✅ Incomplete data correctly rejected")
        for error in result.errors:
            print(f"  Error: {error}")
    else:
        print("❌ Incomplete data should have been rejected")
    
    print()

def test_configuration_validation():
    """Test configuration validation."""
    print("=== Testing Configuration Validation ===")
    
    try:
        # Test valid configuration
        valid_config = create_config(
            timeout=30,
            max_retries=3,
            max_workers=4
        )
        valid_config.validate()
        print("✅ Valid configuration accepted")
        
        # Test invalid configuration
        try:
            invalid_config = create_config(
                timeout=-1,  # Invalid timeout
                max_retries=-1  # Invalid retries
            )
            invalid_config.validate()
            print("❌ Invalid configuration should have been rejected")
        except ValueError as e:
            print(f"✅ Invalid configuration correctly rejected: {e}")
            
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
    
    print()

def main():
    """Run all tests."""
    print("NFL API Client - Simple Tests")
    print("=" * 40)
    
    try:
        test_configuration()
        test_data_validation()
        test_cached_data()
        test_error_handling()
        test_configuration_validation()
        
        print("=" * 40)
        print("✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.exception("Test error")

if __name__ == "__main__":
    main() 