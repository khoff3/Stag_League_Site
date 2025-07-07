"""
Cache utility module for the Stag League History project.

This module provides caching functionality for raw data ingestion,
isolating disk caching logic as specified in the architecture documentation.
"""

import json
import pickle
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Union
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching operations for raw data ingestion."""
    
    def __init__(self, cache_dir: Union[str, Path] = "data/raw"):
        """
        Initialize the cache manager.
        
        Args:
            cache_dir: Base directory for cache storage
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cache_path(self, category: str, identifier: str, extension: str = "json") -> Path:
        """
        Get the cache file path for a given category and identifier.
        
        Args:
            category: Cache category (e.g., 'schedule', 'team_weeks', 'player_weeks')
            identifier: Unique identifier (e.g., '2012_week_01')
            extension: File extension (default: 'json')
            
        Returns:
            Path to the cache file
        """
        category_dir = self.cache_dir / category
        category_dir.mkdir(exist_ok=True)
        return category_dir / f"{identifier}.{extension}"
    
    def is_cached(self, category: str, identifier: str, max_age_hours: Optional[int] = None) -> bool:
        """
        Check if data is cached and optionally check if it's fresh.
        
        Args:
            category: Cache category
            identifier: Unique identifier
            max_age_hours: Maximum age in hours before considering stale (None = no age limit)
            
        Returns:
            True if cached and fresh, False otherwise
        """
        cache_path = self.get_cache_path(category, identifier)
        
        if not cache_path.exists():
            return False
        
        if max_age_hours is None:
            return True
        
        # Check file age
        file_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        return file_age < timedelta(hours=max_age_hours)
    
    def load_cache(self, category: str, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Load data from cache.
        
        Args:
            category: Cache category
            identifier: Unique identifier
            
        Returns:
            Cached data or None if not found
        """
        cache_path = self.get_cache_path(category, identifier)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Loaded cache: {cache_path}")
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cache {cache_path}: {e}")
            return None
    
    def save_cache(self, category: str, identifier: str, data: Dict[str, Any]) -> None:
        """
        Save data to cache.
        
        Args:
            category: Cache category
            identifier: Unique identifier
            data: Data to cache
        """
        cache_path = self.get_cache_path(category, identifier)
        
        try:
            # Add metadata
            cache_data = {
                "data": data,
                "cached_at": datetime.now().isoformat(),
                "identifier": identifier,
                "category": category
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved cache: {cache_path}")
        except IOError as e:
            logger.error(f"Failed to save cache {cache_path}: {e}")
            raise
    
    def clear_cache(self, category: Optional[str] = None, identifier: Optional[str] = None) -> None:
        """
        Clear cache entries.
        
        Args:
            category: Cache category to clear (None = all categories)
            identifier: Specific identifier to clear (None = all in category)
        """
        if category is None:
            # Clear all cache
            import shutil
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Cleared all cache")
        elif identifier is None:
            # Clear category
            category_dir = self.cache_dir / category
            if category_dir.exists():
                import shutil
                shutil.rmtree(category_dir)
            logger.info(f"Cleared cache category: {category}")
        else:
            # Clear specific file
            cache_path = self.get_cache_path(category, identifier)
            if cache_path.exists():
                cache_path.unlink()
                logger.info(f"Cleared cache: {cache_path}")
    
    def get_cache_info(self, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about cached data.
        
        Args:
            category: Cache category to inspect (None = all categories)
            
        Returns:
            Dictionary with cache information
        """
        info = {
            "cache_dir": str(self.cache_dir),
            "categories": {}
        }
        
        if category:
            category_dir = self.cache_dir / category
            if category_dir.exists():
                files = list(category_dir.glob("*.json"))
                info["categories"][category] = {
                    "file_count": len(files),
                    "total_size": sum(f.stat().st_size for f in files),
                    "files": [f.name for f in files]
                }
        else:
            for category_dir in self.cache_dir.iterdir():
                if category_dir.is_dir():
                    files = list(category_dir.glob("*.json"))
                    info["categories"][category_dir.name] = {
                        "file_count": len(files),
                        "total_size": sum(f.stat().st_size for f in files),
                        "files": [f.name for f in files]
                    }
        
        return info


def generate_cache_key(*args, **kwargs) -> str:
    """
    Generate a cache key from arguments.
    
    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Cache key string
    """
    # Create a string representation of the arguments
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_string = "_".join(key_parts)
    
    # Create a hash for shorter, consistent keys
    return hashlib.md5(key_string.encode()).hexdigest()[:16]


# Global cache manager instance
cache_manager = CacheManager()


def cached(category: str, max_age_hours: Optional[int] = None):
    """
    Decorator for caching function results.
    
    Args:
        category: Cache category
        max_age_hours: Maximum age in hours before considering stale
        
    Returns:
        Decorated function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{func.__name__}_{generate_cache_key(*args, **kwargs)}"
            
            # Check if cached
            if cache_manager.is_cached(category, cache_key, max_age_hours):
                cached_data = cache_manager.load_cache(category, cache_key)
                if cached_data:
                    return cached_data["data"]
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.save_cache(category, cache_key, result)
            return result
        
        return wrapper
    return decorator 