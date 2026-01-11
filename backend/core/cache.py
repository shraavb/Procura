"""
Redis caching service for LLM responses and rate limiting.
"""
import hashlib
import json
from typing import Any, Optional
import logging

import redis.asyncio as redis

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Global cache instance
_cache: Optional["RedisCache"] = None


class RedisCache:
    """
    Async Redis cache for LLM prompt caching and rate limiting.
    """

    def __init__(self, url: str):
        self.url = url
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        try:
            self._client = redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._client.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self._client = None

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._client is not None

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        if not self._client:
            return None
        try:
            return await self._client.get(key)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
    ) -> bool:
        """Set value in cache with optional TTL."""
        if not self._client:
            return False
        try:
            await self._client.set(key, value, ex=ttl or settings.redis_cache_ttl)
            return True
        except Exception as e:
            logger.warning(f"Redis set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self._client:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")
            return False

    async def incr(self, key: str) -> int:
        """Increment counter."""
        if not self._client:
            return 0
        try:
            return await self._client.incr(key)
        except Exception as e:
            logger.warning(f"Redis incr error: {e}")
            return 0

    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration."""
        if not self._client:
            return False
        try:
            return await self._client.expire(key, seconds)
        except Exception as e:
            logger.warning(f"Redis expire error: {e}")
            return False

    # LLM-specific caching methods

    @staticmethod
    def hash_prompt(prompt: str, model: str, **kwargs: Any) -> str:
        """Create cache key from prompt and parameters."""
        cache_data = {
            "prompt": prompt,
            "model": model,
            **kwargs,
        }
        content = json.dumps(cache_data, sort_keys=True)
        return f"llm:{hashlib.sha256(content.encode()).hexdigest()}"

    async def get_llm_response(
        self,
        prompt: str,
        model: str,
        **kwargs: Any,
    ) -> Optional[dict]:
        """Get cached LLM response."""
        key = self.hash_prompt(prompt, model, **kwargs)
        cached = await self.get(key)
        if cached:
            logger.debug(f"Cache hit for LLM prompt: {key[:16]}...")
            return json.loads(cached)
        return None

    async def set_llm_response(
        self,
        prompt: str,
        model: str,
        response: dict,
        ttl: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        """Cache LLM response."""
        key = self.hash_prompt(prompt, model, **kwargs)
        return await self.set(key, json.dumps(response), ttl)

    async def get_embedding(self, text: str, model: str) -> Optional[list[float]]:
        """Get cached embedding."""
        key = f"emb:{hashlib.sha256(f'{model}:{text}'.encode()).hexdigest()}"
        cached = await self.get(key)
        if cached:
            return json.loads(cached)
        return None

    async def set_embedding(
        self,
        text: str,
        model: str,
        embedding: list[float],
        ttl: int = 86400,  # 24 hours default
    ) -> bool:
        """Cache embedding."""
        key = f"emb:{hashlib.sha256(f'{model}:{text}'.encode()).hexdigest()}"
        return await self.set(key, json.dumps(embedding), ttl)


async def init_cache() -> RedisCache:
    """Initialize and connect Redis cache."""
    global _cache
    _cache = RedisCache(settings.redis_url)
    await _cache.connect()
    return _cache


async def close_cache() -> None:
    """Close Redis cache connection."""
    global _cache
    if _cache:
        await _cache.disconnect()
        _cache = None


def get_cache() -> Optional[RedisCache]:
    """Get the cache instance."""
    return _cache
