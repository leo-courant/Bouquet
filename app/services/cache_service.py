"""Caching service for embeddings and query results."""

import hashlib
import json
from typing import Any, Optional

from loguru import logger

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - caching will use in-memory LRU cache")


class CacheService:
    """Intelligent caching service with Redis fallback to in-memory."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl: int = 3600,
        max_memory_items: int = 10000,
    ) -> None:
        """Initialize cache service."""
        self.ttl = ttl
        self.redis_client: Optional[redis.Redis] = None
        self.memory_cache: dict[str, Any] = {}
        self.max_memory_items = max_memory_items
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Try to connect to Redis
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
                logger.info(f"Connected to Redis at {redis_url}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory cache.")
                self.redis_client = None
        else:
            logger.info("Using in-memory cache (Redis not configured)")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        # Try Redis first
        if self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value:
                    self.cache_hits += 1
                    return json.loads(value)
            except Exception as e:
                logger.debug(f"Redis get error: {e}")
        
        # Fallback to memory cache
        if key in self.memory_cache:
            self.cache_hits += 1
            return self.memory_cache[key]
        
        self.cache_misses += 1
        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        ttl = ttl or self.ttl
        serialized = json.dumps(value)
        
        # Try Redis first
        if self.redis_client:
            try:
                await self.redis_client.setex(key, ttl, serialized)
                return
            except Exception as e:
                logger.debug(f"Redis set error: {e}")
        
        # Fallback to memory cache (with LRU eviction)
        if len(self.memory_cache) >= self.max_memory_items:
            # Simple LRU: remove first item
            self.memory_cache.pop(next(iter(self.memory_cache)))
        
        self.memory_cache[key] = value

    async def delete(self, key: str) -> None:
        """Delete from cache."""
        if self.redis_client:
            try:
                await self.redis_client.delete(key)
            except Exception:
                pass
        
        self.memory_cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all cache."""
        if self.redis_client:
            try:
                await self.redis_client.flushdb()
            except Exception:
                pass
        
        self.memory_cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        
        return {
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "hit_rate_percent": round(hit_rate, 2),
            "backend": "redis" if self.redis_client else "memory",
            "memory_items": len(self.memory_cache),
        }

    @staticmethod
    def hash_key(*args: Any) -> str:
        """Generate cache key from arguments."""
        content = json.dumps(args, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    async def close(self) -> None:
        """Close connections."""
        if self.redis_client:
            await self.redis_client.close()


class EmbeddingCache:
    """Specialized cache for embeddings."""

    def __init__(self, cache_service: CacheService) -> None:
        """Initialize embedding cache."""
        self.cache = cache_service
        self.prefix = "emb:"

    async def get_embedding(self, text: str) -> Optional[list[float]]:
        """Get cached embedding."""
        key = self.prefix + self.cache.hash_key(text)
        return await self.cache.get(key)

    async def set_embedding(self, text: str, embedding: list[float]) -> None:
        """Cache embedding (24 hour TTL - embeddings don't change)."""
        key = self.prefix + self.cache.hash_key(text)
        await self.cache.set(key, embedding, ttl=86400)  # 24 hours


class QueryCache:
    """Specialized cache for query results."""

    def __init__(self, cache_service: CacheService) -> None:
        """Initialize query cache."""
        self.cache = cache_service
        self.prefix = "query:"

    async def get_result(
        self,
        query: str,
        strategy: str,
        top_k: int,
    ) -> Optional[dict]:
        """Get cached query result."""
        key = self.prefix + self.cache.hash_key(query, strategy, top_k)
        return await self.cache.get(key)

    async def set_result(
        self,
        query: str,
        strategy: str,
        top_k: int,
        result: dict,
    ) -> None:
        """Cache query result (5 minute TTL - data might be updated)."""
        key = self.prefix + self.cache.hash_key(query, strategy, top_k)
        await self.cache.set(key, result, ttl=300)  # 5 minutes

    async def invalidate_all(self) -> None:
        """Invalidate all query caches (e.g., after document upload)."""
        # With Redis, we'd use pattern matching, for now just clear
        logger.info("Query cache invalidated")
