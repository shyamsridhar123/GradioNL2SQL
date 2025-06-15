"""
Query-level caching system for Text2SQL
Caches entire query results and SQL generation for fast repeated queries
"""

import time
import hashlib
import json
from typing import Dict, Any, Optional, Tuple
from utils.logging_config import get_logger

logger = get_logger(__name__)

class QueryResultCache:
    """
    Intelligent caching system for SQL queries and results
    """
    
    def __init__(self, cache_ttl: int = 3600):  # 1 hour default TTL
        self._query_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._sql_cache: Dict[str, Tuple[str, float]] = {}
        self._cache_ttl = cache_ttl
        self._cache_hits = 0
        self._cache_misses = 0
        
    def _get_cache_key(self, query: str) -> str:
        """Generate consistent cache key from query"""
        # Normalize query for better cache hits
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def _is_cache_valid(self, timestamp: float) -> bool:
        """Check if cache entry is still valid"""
        return time.time() - timestamp < self._cache_ttl
    
    def get_cached_result(self, query: str) -> Optional[Dict[str, Any]]:
        """Get cached complete query result if available"""
        cache_key = self._get_cache_key(query)
        
        if cache_key in self._query_cache:
            result, timestamp = self._query_cache[cache_key]
            if self._is_cache_valid(timestamp):
                self._cache_hits += 1
                logger.info(f"Cache HIT for query: {query[:50]}...")
                logger.debug(f"Cache stats: {self._cache_hits} hits, {self._cache_misses} misses")
                return result.copy()  # Return a copy to prevent modification
            else:
                # Remove expired entry
                del self._query_cache[cache_key]
                
        self._cache_misses += 1
        logger.debug(f"Cache MISS for query: {query[:50]}...")
        return None
    
    def cache_result(self, query: str, result: Dict[str, Any]) -> None:
        """Cache complete query result"""
        cache_key = self._get_cache_key(query)
        self._query_cache[cache_key] = (result.copy(), time.time())
        logger.debug(f"Cached result for query: {query[:50]}...")
    
    def get_cached_sql(self, query: str) -> Optional[str]:
        """Get cached SQL for query if available"""
        cache_key = self._get_cache_key(query)
        
        if cache_key in self._sql_cache:
            sql, timestamp = self._sql_cache[cache_key]
            if self._is_cache_valid(timestamp):
                logger.debug(f"SQL cache HIT for: {query[:50]}...")
                return sql
            else:
                del self._sql_cache[cache_key]
                
        return None
    
    def cache_sql(self, query: str, sql: str) -> None:
        """Cache generated SQL"""
        cache_key = self._get_cache_key(query)
        self._sql_cache[cache_key] = (sql, time.time())
        logger.debug(f"Cached SQL for query: {query[:50]}...")
    
    def clear_expired(self) -> int:
        """Remove expired cache entries and return count removed"""
        current_time = time.time()
        expired_query_keys = [
            key for key, (_, timestamp) in self._query_cache.items()
            if current_time - timestamp >= self._cache_ttl
        ]
        expired_sql_keys = [
            key for key, (_, timestamp) in self._sql_cache.items()
            if current_time - timestamp >= self._cache_ttl
        ]
        
        for key in expired_query_keys:
            del self._query_cache[key]
        for key in expired_sql_keys:
            del self._sql_cache[key]
            
        total_expired = len(expired_query_keys) + len(expired_sql_keys)
        if total_expired > 0:
            logger.info(f"Removed {total_expired} expired cache entries")
            
        return total_expired
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0,
            "query_entries": len(self._query_cache),
            "sql_entries": len(self._sql_cache),
            "cache_ttl": self._cache_ttl
        }
    
    def clear_all(self) -> None:
        """Clear all cache entries"""
        self._query_cache.clear()
        self._sql_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("All cache entries cleared")

# Global cache instance
_global_cache = QueryResultCache()

def get_global_cache() -> QueryResultCache:
    """Get the global query cache instance"""
    return _global_cache
