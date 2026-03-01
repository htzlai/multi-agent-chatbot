# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Query caching layer (memory + Redis).

Extracted from ``enhanced_rag.py``.  Fixes:
- Missing ``self.memory_fallback`` assignment (AttributeError in original)
- Cache key now includes ``top_k`` for correctness
"""

import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _make_cache_key(
    query: str,
    sources: Optional[List[str]] = None,
    top_k: int = 10,
    use_hybrid: Optional[bool] = None,
) -> str:
    """Shared cache-key builder for both backends."""
    key_data = json.dumps(
        {"q": query, "s": sorted(sources or []), "k": top_k, "h": use_hybrid},
        sort_keys=True,
    )
    return hashlib.sha256(key_data.encode()).hexdigest()


class QueryCache:
    """Simple in-memory query cache with TTL."""

    def __init__(self, ttl: int = 3600):
        self.cache: Dict[str, Tuple[str, float]] = {}
        self.ttl = ttl

    def get(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        top_k: int = 10,
        use_hybrid: Optional[bool] = None,
    ) -> Optional[str]:
        key = _make_cache_key(query, sources, top_k, use_hybrid)
        if key in self.cache:
            result, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return result
            del self.cache[key]
        return None

    def set(
        self,
        query: str,
        result: str,
        sources: Optional[List[str]] = None,
        top_k: int = 10,
        use_hybrid: Optional[bool] = None,
    ) -> None:
        key = _make_cache_key(query, sources, top_k, use_hybrid)
        self.cache[key] = (result, time.time())

    def clear(self) -> None:
        self.cache.clear()


class RedisQueryCache:
    """Redis-backed query cache with in-memory fallback.

    Fixed from original: ``self.memory_fallback`` is now properly assigned.
    """

    def __init__(
        self,
        ttl: int = 3600,
        redis_host: Optional[str] = None,
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
        use_redis: bool = True,
        memory_fallback: bool = True,
    ):
        self.ttl = ttl
        self.redis_host = redis_host or os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", str(redis_port)))
        self.redis_db = int(os.getenv("REDIS_DB", str(redis_db)))
        self.redis_password = redis_password or os.getenv("REDIS_PASSWORD")
        self.use_redis = use_redis and self.redis_host is not None
        self.memory_fallback = memory_fallback  # BUG FIX: was missing in original

        self._redis_client = None
        self._redis_available: Optional[bool] = None
        self._memory_cache: Dict[str, Tuple[str, float]] = {}
        self._key_prefix = "rag:query_cache:"

    def _get_redis_client(self):
        """Lazy-initialize Redis connection."""
        if self._redis_client is not None:
            return self._redis_client
        if not self.use_redis:
            return None
        try:
            import redis
            self._redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self._redis_client.ping()
            self._redis_available = True
            logger.info({"message": "Redis cache connected", "host": self.redis_host})
            return self._redis_client
        except Exception as exc:
            logger.warning({"message": "Redis unavailable, memory fallback", "error": str(exc)})
            self._redis_available = False
            self._redis_client = None
            return None

    def get(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        top_k: int = 10,
        use_hybrid: Optional[bool] = None,
    ) -> Optional[str]:
        key = _make_cache_key(query, sources, top_k, use_hybrid)
        full_key = f"{self._key_prefix}{key}"

        if self.use_redis and self._redis_available is not False:
            client = self._get_redis_client()
            if client:
                try:
                    result = client.get(full_key)
                    if result and client.ttl(full_key) > 0:
                        return result
                except Exception as exc:
                    logger.warning({"message": "Redis get failed", "error": str(exc)})

        if self.memory_fallback and key in self._memory_cache:
            result, timestamp = self._memory_cache[key]
            if time.time() - timestamp < self.ttl:
                return result
            del self._memory_cache[key]
        return None

    def set(
        self,
        query: str,
        result: str,
        sources: Optional[List[str]] = None,
        top_k: int = 10,
        use_hybrid: Optional[bool] = None,
    ) -> None:
        key = _make_cache_key(query, sources, top_k, use_hybrid)
        full_key = f"{self._key_prefix}{key}"

        if self.use_redis and self._redis_available is not False:
            client = self._get_redis_client()
            if client:
                try:
                    client.setex(full_key, self.ttl, result)
                except Exception as exc:
                    logger.warning({"message": "Redis set failed", "error": str(exc)})

        if self.memory_fallback:
            self._memory_cache[key] = (result, time.time())

    def clear(self) -> None:
        """Clear all cached queries from Redis and memory."""
        if self.use_redis and self._redis_available is not False:
            client = self._get_redis_client()
            if client:
                try:
                    for key in client.scan_iter(f"{self._key_prefix}*"):
                        client.delete(key)
                except Exception as exc:
                    logger.warning({"message": "Redis clear failed", "error": str(exc)})
        self._memory_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self.use_redis and self._redis_available is None:
            self._get_redis_client()

        stats: Dict[str, Any] = {
            "backend": "redis" if (self.use_redis and self._redis_available) else "memory",
            "ttl": self.ttl,
            "memory_entries": len(self._memory_cache),
            "redis_available": self._redis_available,
        }

        if self.use_redis and self._redis_available:
            client = self._get_redis_client()
            if client:
                try:
                    info = client.info("stats")
                    stats["redis_keys"] = sum(
                        1 for _ in client.scan_iter(f"{self._key_prefix}*")
                    )
                    stats["redis_hits"] = info.get("keyspace_hits", 0)
                    stats["redis_misses"] = info.get("keyspace_misses", 0)
                except Exception:
                    pass
        return stats

    def is_healthy(self) -> bool:
        """Check if cache backend is healthy."""
        if self.use_redis and self._redis_available is not False:
            client = self._get_redis_client()
            if client:
                try:
                    client.ping()
                    return True
                except Exception:
                    return False
        return self.memory_fallback


# ---------------------------------------------------------------------------
# Factory functions (singleton pattern via module-level globals)
# ---------------------------------------------------------------------------

_query_cache: Optional[QueryCache] = None
_redis_cache: Optional[RedisQueryCache] = None


def get_query_cache() -> QueryCache:
    """Get or create the in-memory query cache."""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache(ttl=3600)
    return _query_cache


def get_redis_query_cache() -> RedisQueryCache:
    """Get or create the Redis-backed query cache."""
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisQueryCache(
            ttl=int(os.getenv("QUERY_CACHE_TTL", "3600")),
            use_redis=os.getenv("REDIS_HOST") is not None,
            memory_fallback=True,
        )
    return _redis_cache
