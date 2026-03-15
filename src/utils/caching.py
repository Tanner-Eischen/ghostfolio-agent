"""Caching utilities for API responses."""

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from cachetools import TTLCache

from src.utils.config import get_settings

T = TypeVar("T")


class CacheManager:
    """Thread-safe TTL cache manager."""

    def __init__(self, ttl_seconds: int | None = None, maxsize: int = 1000):
        """Initialize cache with TTL and max size."""
        settings = get_settings()
        self._ttl = ttl_seconds or settings.cache_ttl_seconds
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=maxsize, ttl=self._ttl)

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        return self._cache.get(key)

    def set(self, key: str, value: Any, **kwargs: Any) -> None:
        """Set value in cache. Accepts optional ttl= for API compatibility (single global TTL is used)."""
        self._cache[key] = value

    def delete(self, key: str) -> None:
        """Delete value from cache."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "maxsize": self._cache.maxsize,
            "ttl": self._ttl,
        }


# Global cache instance
_cache_manager: CacheManager | None = None


def get_cache() -> CacheManager:
    """Get the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def cached(key_prefix: str = "") -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to cache function results."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            cache = get_cache()

            # Build cache key
            key_parts = [key_prefix or func.__name__]
            if args:
                key_parts.extend(str(arg) for arg in args)
            if kwargs:
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            # Check cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute and cache
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result

        return wrapper

    return decorator
