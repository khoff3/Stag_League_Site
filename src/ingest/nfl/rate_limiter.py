"""
NFL Rate Limiter and Connection Manager

This module provides rate limiting and connection management for NFL Fantasy Football scraping.
It helps prevent overwhelming the servers and ensures respectful scraping practices.
"""

import time
import asyncio
from typing import Optional, Callable, Any
from dataclasses import dataclass
from contextlib import contextmanager
import logging
from collections import deque
from threading import Lock, Timer
import random

logger = logging.getLogger(__name__)

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 30
    requests_per_second: int = 2
    min_delay_between_requests: float = 1.0
    max_delay_between_requests: float = 3.0
    burst_size: int = 5
    jitter_factor: float = 0.1  # Add randomness to avoid synchronized requests

class RateLimiter:
    """Rate limiter for API requests."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.request_times = deque()
        self.last_request_time = 0
        self.lock = Lock()
        
        # Calculate delays
        self.min_delay = max(config.min_delay_between_requests, 1.0 / config.requests_per_second)
        self.max_delay = config.max_delay_between_requests
        
        logger.info(f"Initialized rate limiter: {config.requests_per_minute} req/min, "
                   f"{config.requests_per_second} req/sec, delay: {self.min_delay}-{self.max_delay}s")
    
    def wait_if_needed(self) -> float:
        """
        Wait if necessary to respect rate limits.
        
        Returns:
            Time waited in seconds
        """
        with self.lock:
            current_time = time.time()
            wait_time = 0
            
            # Remove old requests from tracking (older than 1 minute)
            while self.request_times and current_time - self.request_times[0] > 60:
                self.request_times.popleft()
            
            # Check if we need to wait due to rate limits
            if len(self.request_times) >= self.config.requests_per_minute:
                # Wait until we can make another request
                oldest_request = self.request_times[0]
                required_wait = 60 - (current_time - oldest_request)
                if required_wait > 0:
                    wait_time += required_wait
                    logger.debug(f"Rate limit: waiting {required_wait:.2f}s")
            
            # Ensure minimum delay between requests
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_delay:
                additional_wait = self.min_delay - time_since_last
                wait_time += additional_wait
                logger.debug(f"Min delay: waiting {additional_wait:.2f}s")
            
            # Add jitter to avoid synchronized requests
            if wait_time > 0:
                jitter = random.uniform(-self.config.jitter_factor * wait_time, 
                                      self.config.jitter_factor * wait_time)
                wait_time += jitter
                wait_time = max(0, wait_time)  # Ensure non-negative
            
            if wait_time > 0:
                time.sleep(wait_time)
                logger.debug(f"Total wait time: {wait_time:.2f}s")
            
            # Record this request
            self.request_times.append(current_time)
            self.last_request_time = current_time
            
            return wait_time
    
    def get_status(self) -> dict:
        """Get current rate limiter status."""
        with self.lock:
            current_time = time.time()
            recent_requests = len([t for t in self.request_times 
                                 if current_time - t <= 60])
            
            return {
                'requests_in_last_minute': recent_requests,
                'max_requests_per_minute': self.config.requests_per_minute,
                'time_since_last_request': current_time - self.last_request_time,
                'min_delay_between_requests': self.min_delay
            }

class ConnectionPool:
    """Manages a pool of webdriver connections."""
    
    def __init__(self, max_connections: int = 3, config: Optional[RateLimitConfig] = None):
        self.max_connections = max_connections
        self.rate_limiter = RateLimiter(config or RateLimitConfig())
        self.active_connections = 0
        self.lock = Lock()
        
        logger.info(f"Initialized connection pool with {max_connections} max connections")
    
    @contextmanager
    def get_connection(self):
        """Context manager for getting a connection from the pool."""
        with self.lock:
            while self.active_connections >= self.max_connections:
                logger.debug("Connection pool full, waiting for available connection...")
                time.sleep(0.1)
            
            self.active_connections += 1
            logger.debug(f"Acquired connection ({self.active_connections}/{self.max_connections})")
        
        try:
            # Apply rate limiting
            wait_time = self.rate_limiter.wait_if_needed()
            yield wait_time
        finally:
            with self.lock:
                self.active_connections -= 1
                logger.debug(f"Released connection ({self.active_connections}/{self.max_connections})")
    
    def get_status(self) -> dict:
        """Get connection pool status."""
        with self.lock:
            return {
                'active_connections': self.active_connections,
                'max_connections': self.max_connections,
                'available_connections': self.max_connections - self.active_connections,
                'rate_limiter_status': self.rate_limiter.get_status()
            }

class RetryManager:
    """Manages retry logic for failed requests."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, 
                 max_delay: float = 30.0, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        
        logger.info(f"Initialized retry manager: max_retries={max_retries}, "
                   f"base_delay={base_delay}s, max_delay={max_delay}s")
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (self.backoff_factor ** attempt), 
                               self.max_delay)
                    
                    # Add jitter to avoid thundering herd
                    jitter = random.uniform(0, delay * 0.1)
                    total_delay = delay + jitter
                    
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. "
                                 f"Retrying in {total_delay:.2f}s...")
                    time.sleep(total_delay)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed. "
                               f"Last error: {e}")
        
        raise last_exception

class ScrapingSession:
    """Manages a scraping session with rate limiting and connection pooling."""
    
    def __init__(self, rate_limit_config: Optional[RateLimitConfig] = None,
                 max_connections: int = 3, max_retries: int = 3):
        self.rate_limit_config = rate_limit_config or RateLimitConfig()
        self.connection_pool = ConnectionPool(max_connections, self.rate_limit_config)
        self.retry_manager = RetryManager(max_retries)
        self.session_start_time = time.time()
        self.total_requests = 0
        self.failed_requests = 0
        
        logger.info("Initialized scraping session")
    
    def execute_request(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a request with rate limiting, connection pooling, and retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        def _execute():
            with self.connection_pool.get_connection() as wait_time:
                self.total_requests += 1
                logger.debug(f"Executing request #{self.total_requests} "
                           f"(waited {wait_time:.2f}s)")
                return func(*args, **kwargs)
        
        try:
            result = self.retry_manager.execute_with_retry(_execute)
            return result
        except Exception as e:
            self.failed_requests += 1
            logger.error(f"Request failed after retries: {e}")
            raise
    
    def get_session_stats(self) -> dict:
        """Get session statistics."""
        session_duration = time.time() - self.session_start_time
        success_rate = ((self.total_requests - self.failed_requests) / 
                       max(self.total_requests, 1)) * 100
        
        return {
            'session_duration_seconds': session_duration,
            'total_requests': self.total_requests,
            'failed_requests': self.failed_requests,
            'success_rate_percent': success_rate,
            'requests_per_minute': (self.total_requests / max(session_duration / 60, 1)),
            'connection_pool_status': self.connection_pool.get_status()
        }
    
    def print_session_summary(self) -> None:
        """Print a summary of the scraping session."""
        stats = self.get_session_stats()
        
        print("\n=== SCRAPING SESSION SUMMARY ===")
        print(f"Duration: {stats['session_duration_seconds']:.1f} seconds")
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Failed Requests: {stats['failed_requests']}")
        print(f"Success Rate: {stats['success_rate_percent']:.1f}%")
        print(f"Requests per Minute: {stats['requests_per_minute']:.1f}")
        
        pool_status = stats['connection_pool_status']
        print(f"Max Connections: {pool_status['max_connections']}")
        print(f"Peak Active Connections: {pool_status['active_connections']}")
        
        rate_status = pool_status['rate_limiter_status']
        print(f"Rate Limit: {rate_status['requests_in_last_minute']}/{rate_status['max_requests_per_minute']} req/min")
        print("=" * 35)

# Convenience functions
def create_session(requests_per_minute: int = 30, max_connections: int = 3, 
                  max_retries: int = 3) -> ScrapingSession:
    """Create a scraping session with default settings."""
    config = RateLimitConfig(requests_per_minute=requests_per_minute)
    return ScrapingSession(config, max_connections, max_retries)

def with_rate_limiting(func: Callable) -> Callable:
    """Decorator to add rate limiting to a function."""
    def wrapper(*args, **kwargs):
        # Create a simple rate limiter for the decorated function
        rate_limiter = RateLimiter(RateLimitConfig())
        rate_limiter.wait_if_needed()
        return func(*args, **kwargs)
    return wrapper 