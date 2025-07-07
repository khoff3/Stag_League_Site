"""
NFL API Client Configuration

This module provides configuration management for the NFL Fantasy Football scraper.
It includes environment variable loading, configuration validation, and default settings.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class NFLConfig:
    """Configuration for NFL Fantasy Football operations."""
    
    # API and scraping settings
    base_url: str = "https://fantasy.nfl.com"
    headless: bool = True
    timeout: int = 30
    wait_time: int = 10
    max_retries: int = 3
    retry_delay: float = 2.0
    
    # Browser settings
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    window_size: str = "1920,1080"
    
    # Data and caching
    data_dir: str = "data"
    cache_enabled: bool = True
    cache_expiry_hours: int = 24
    
    # Performance settings
    max_workers: int = 4
    requests_per_minute: int = 30
    min_delay_between_requests: float = 1.0
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # League settings
    default_league_id: str = "864504"
    default_season: int = 2023
    
    @classmethod
    def from_env(cls) -> 'NFLConfig':
        """Create configuration from environment variables."""
        return cls(
            base_url=os.getenv("NFL_BASE_URL", "https://fantasy.nfl.com"),
            headless=os.getenv("NFL_HEADLESS", "true").lower() == "true",
            timeout=int(os.getenv("NFL_TIMEOUT", "30")),
            wait_time=int(os.getenv("NFL_WAIT_TIME", "10")),
            max_retries=int(os.getenv("NFL_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("NFL_RETRY_DELAY", "2.0")),
            user_agent=os.getenv("NFL_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
            window_size=os.getenv("NFL_WINDOW_SIZE", "1920,1080"),
            data_dir=os.getenv("NFL_DATA_DIR", "data"),
            cache_enabled=os.getenv("NFL_CACHE_ENABLED", "true").lower() == "true",
            cache_expiry_hours=int(os.getenv("NFL_CACHE_EXPIRY_HOURS", "24")),
            max_workers=int(os.getenv("NFL_MAX_WORKERS", "4")),
            requests_per_minute=int(os.getenv("NFL_REQUESTS_PER_MINUTE", "30")),
            min_delay_between_requests=float(os.getenv("NFL_MIN_DELAY", "1.0")),
            log_level=os.getenv("NFL_LOG_LEVEL", "INFO"),
            log_file=os.getenv("NFL_LOG_FILE"),
            default_league_id=os.getenv("NFL_LEAGUE_ID", "864504"),
            default_season=int(os.getenv("NFL_DEFAULT_SEASON", "2023"))
        )
    
    def validate(self) -> None:
        """Validate configuration values."""
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.max_workers <= 0:
            raise ValueError("max_workers must be positive")
        if self.requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        if self.cache_expiry_hours < 0:
            raise ValueError("cache_expiry_hours must be non-negative")
    
    def get_data_paths(self) -> Dict[str, Path]:
        """Get data directory paths."""
        base_path = Path(self.data_dir)
        return {
            'raw': base_path / "raw",
            'processed': base_path / "processed",
            'cache': base_path / "cache",
            'logs': base_path / "logs"
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'base_url': self.base_url,
            'headless': self.headless,
            'timeout': self.timeout,
            'wait_time': self.wait_time,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'user_agent': self.user_agent,
            'window_size': self.window_size,
            'data_dir': self.data_dir,
            'cache_enabled': self.cache_enabled,
            'cache_expiry_hours': self.cache_expiry_hours,
            'max_workers': self.max_workers,
            'requests_per_minute': self.requests_per_minute,
            'min_delay_between_requests': self.min_delay_between_requests,
            'log_level': self.log_level,
            'log_file': self.log_file,
            'default_league_id': self.default_league_id,
            'default_season': self.default_season
        }

# Default configuration instance
DEFAULT_CONFIG = NFLConfig.from_env()

def get_config() -> NFLConfig:
    """Get the default configuration."""
    return DEFAULT_CONFIG

def create_config(**kwargs) -> NFLConfig:
    """Create a custom configuration."""
    config = NFLConfig.from_env()
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    config.validate()
    return config 