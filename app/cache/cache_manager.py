import logging
from datetime import datetime, timedelta
from typing import Optional, List, Any
from cachetools import TTLCache
import json
import threading
from app.models.dividend import DividendData, DividendCalendarResponse

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching of dividend data with TTL support"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        Initialize cache manager
        
        Args:
            max_size: Maximum number of items to cache
            default_ttl: Default TTL in seconds (1 hour by default)
        """
        self._cache = TTLCache(maxsize=max_size, ttl=default_ttl)
        self._lock = threading.RLock()
        self.default_ttl = default_ttl
        
    def _generate_cache_key(self, symbol: str, source: Optional[str] = None) -> str:
        """Generate cache key for a symbol and optional source"""
        if source:
            return f"dividend:{symbol.upper()}:{source}"
        return f"dividend:{symbol.upper()}"
    
    def get(self, symbol: str, source: Optional[str] = None) -> Optional[DividendCalendarResponse]:
        """
        Retrieve cached dividend data for a symbol
        
        Args:
            symbol: Stock ticker symbol
            source: Optional specific source to retrieve
            
        Returns:
            Cached DividendCalendarResponse if found, None otherwise
        """
        cache_key = self._generate_cache_key(symbol, source)
        
        with self._lock:
            try:
                cached_data = self._cache.get(cache_key)
                if cached_data:
                    logger.info(f"Cache hit for {cache_key}")
                    # Update cache metadata
                    cached_data["cached"] = True
                    cached_data["cache_expires_at"] = datetime.utcnow() + timedelta(seconds=self.default_ttl)
                    return DividendCalendarResponse(**cached_data)
                else:
                    logger.info(f"Cache miss for {cache_key}")
                    return None
            except Exception as e:
                logger.error(f"Error retrieving from cache: {e}")
                return None
    
    def set(self, symbol: str, data: DividendCalendarResponse, source: Optional[str] = None, ttl: Optional[int] = None) -> bool:
        """
        Store dividend data in cache
        
        Args:
            symbol: Stock ticker symbol
            data: DividendCalendarResponse to cache
            source: Optional specific source identifier
            ttl: Custom TTL in seconds (uses default if not provided)
            
        Returns:
            True if successfully cached, False otherwise
        """
        cache_key = self._generate_cache_key(symbol, source)
        cache_ttl = ttl or self.default_ttl
        
        with self._lock:
            try:
                # Convert to dict for caching
                cache_data = data.model_dump()
                cache_data["cache_expires_at"] = datetime.utcnow() + timedelta(seconds=cache_ttl)
                
                # Store in cache with custom TTL if provided
                if ttl:
                    # Create a new TTLCache entry with custom TTL
                    self._cache[cache_key] = cache_data
                else:
                    self._cache[cache_key] = cache_data
                
                logger.info(f"Cached data for {cache_key} with TTL {cache_ttl}s")
                return True
                
            except Exception as e:
                logger.error(f"Error caching data: {e}")
                return False
    
    def invalidate(self, symbol: str, source: Optional[str] = None) -> bool:
        """
        Invalidate cached data for a symbol
        
        Args:
            symbol: Stock ticker symbol
            source: Optional specific source to invalidate
            
        Returns:
            True if data was invalidated, False if not found
        """
        cache_key = self._generate_cache_key(symbol, source)
        
        with self._lock:
            try:
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    logger.info(f"Invalidated cache for {cache_key}")
                    return True
                return False
            except Exception as e:
                logger.error(f"Error invalidating cache: {e}")
                return False
    
    def clear_all(self) -> int:
        """
        Clear all cached data
        
        Returns:
            Number of items cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {count} items from cache")
            return count
    
    def get_cache_stats(self) -> dict:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            return {
                "current_size": len(self._cache),
                "max_size": self._cache.maxsize,
                "default_ttl": self.default_ttl,
                "cache_info": {
                    "hits": getattr(self._cache, 'hits', 0),
                    "misses": getattr(self._cache, 'misses', 0)
                }
            }


# Global cache manager instance
cache_manager = CacheManager(max_size=1000, default_ttl=3600)  # 1 hour default TTL
