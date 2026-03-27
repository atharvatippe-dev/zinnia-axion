"""
Redis cache configuration and helpers for Zinnia Axion.

Provides centralized cache management for:
  - User data (5 min TTL)
  - Team hierarchy (15 min TTL)
  - Dashboard aggregations (1 min TTL)
"""

import os
import logging
import json
from functools import wraps
from typing import Optional, Any, Callable
import redis
from redis import Redis

logger = logging.getLogger(__name__)


class CacheConfig:
    """Redis cache configuration loaded from environment."""

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # Cache TTL (Time-To-Live) in seconds
    CACHE_TTL_USER_DATA: int = int(os.getenv("CACHE_TTL_USER_DATA", "300"))  # 5 min
    CACHE_TTL_TEAM_HIERARCHY: int = int(
        os.getenv("CACHE_TTL_TEAM_HIERARCHY", "900")
    )  # 15 min
    CACHE_TTL_DASHBOARD: int = int(os.getenv("CACHE_TTL_DASHBOARD", "60"))  # 1 min

    # Cache enable/disable
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() in (
        "true",
        "1",
        "yes",
    )


# Global Redis client instance
_redis_client: Optional[Redis] = None


def get_redis_client() -> Optional[Redis]:
    """
    Get or create a Redis client instance.
    Returns None if Redis is unavailable or cache is disabled.
    """
    global _redis_client

    if not CacheConfig.CACHE_ENABLED:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        _redis_client = redis.from_url(
            CacheConfig.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
        )
        # Test connection
        _redis_client.ping()
        logger.info("Redis cache connected successfully")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Cache will be disabled.")
        _redis_client = None
        return None


def close_redis_client():
    """Close the Redis connection."""
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
        _redis_client = None


def cache_get(key: str) -> Optional[Any]:
    """
    Retrieve a value from cache.
    Automatically handles JSON deserialization.
    """
    client = get_redis_client()
    if client is None:
        return None

    try:
        value = client.get(key)
        if value is None:
            return None
        # Try to deserialize JSON
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    except Exception as e:
        logger.error(f"Cache GET error for key {key}: {e}")
        return None


def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    """
    Store a value in cache with optional TTL.
    Automatically handles JSON serialization.
    """
    client = get_redis_client()
    if client is None:
        return False

    try:
        # Serialize to JSON if not already a string
        if not isinstance(value, str):
            value = json.dumps(value)
        client.setex(key, ttl, value)
        return True
    except Exception as e:
        logger.error(f"Cache SET error for key {key}: {e}")
        return False


def cache_delete(key: str) -> bool:
    """Delete a key from cache."""
    client = get_redis_client()
    if client is None:
        return False

    try:
        client.delete(key)
        return True
    except Exception as e:
        logger.error(f"Cache DELETE error for key {key}: {e}")
        return False


def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching a pattern (e.g., 'user:*')."""
    client = get_redis_client()
    if client is None:
        return 0

    try:
        keys = client.keys(pattern)
        if keys:
            return client.delete(*keys)
        return 0
    except Exception as e:
        logger.error(f"Cache DELETE PATTERN error for pattern {pattern}: {e}")
        return 0


def cache_clear() -> bool:
    """Clear all cache."""
    client = get_redis_client()
    if client is None:
        return False

    try:
        client.flushdb()
        logger.info("Cache cleared")
        return True
    except Exception as e:
        logger.error(f"Cache FLUSH error: {e}")
        return False


def cached(key_prefix: str, ttl: int = 300) -> Callable:
    """
    Decorator for caching function results.

    Usage:
        @cached("user", ttl=300)
        def get_user_data(user_id):
            return db.query(User).get(user_id).to_dict()

        # Will generate cache key: "user:123"
        result = get_user_data(123)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Generate cache key from function name and first positional arg
            if args:
                cache_key = f"{key_prefix}:{args[0]}"
            else:
                # Fallback: use all kwargs as key
                cache_key = f"{key_prefix}:{json.dumps(kwargs, sort_keys=True, default=str)}"

            # Try to get from cache
            cached_value = cache_get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT for {cache_key}")
                return cached_value

            # Cache miss: call function
            result = func(*args, **kwargs)

            # Store in cache
            if result is not None:
                cache_set(cache_key, result, ttl=ttl)
                logger.debug(f"Cache SET for {cache_key}")

            return result

        return wrapper

    return decorator


def get_cache_stats() -> dict:
    """Get Redis cache statistics (for CloudWatch)."""
    client = get_redis_client()
    if client is None:
        return {"status": "disabled"}

    try:
        info = client.info()
        return {
            "status": "connected",
            "used_memory_mb": info.get("used_memory_mb", 0),
            "used_memory_peak_mb": info.get("used_memory_peak_mb", 0),
            "evicted_keys": info.get("evicted_keys", 0),
            "expired_keys": info.get("expired_keys", 0),
            "total_commands_processed": info.get("total_commands_processed", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "hit_rate": (
                info.get("keyspace_hits", 0)
                / (
                    info.get("keyspace_hits", 0)
                    + info.get("keyspace_misses", 1)
                )
                * 100
            ),
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {"status": "error", "error": str(e)}
