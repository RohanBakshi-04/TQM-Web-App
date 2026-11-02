"""Q05 In-Memory Cache Service with TTL, Dependency Invalidation, and Telemetry.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional, Set


class CacheEntry:
    """Represents a cached item with expiration time, metadata, and dependency tags."""

    __slots__ = ("key", "value", "created_at", "expires_at", "tags")

    def __init__(self, key: str, value: Any, ttl_seconds: float, tags: Optional[List[str]] = None):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds if ttl_seconds > 0 else float("inf")
        self.tags: Set[str] = set(tags or [])

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class CacheService:
    """Thread-safe, high-speed in-memory caching engine designed for sub-millisecond retrieval."""

    def __init__(self, default_ttl: float = 60.0, max_size: int = 1000):
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = threading.RLock()
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._tag_index: Dict[str, Set[str]] = {}  # tag -> set of keys

        # Telemetry & Performance Counters
        self._hits: int = 0
        self._misses: int = 0
        self._invalidations: int = 0
        self._evictions: int = 0
        self._start_time: float = time.time()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached value if present and unexpired; tracks hit/miss telemetry."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired:
                self._evict_entry(key)
                self._misses += 1
                return None

            self._store.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None, tags: Optional[List[str]] = None) -> None:
        """Store a value in cache with configurable TTL and dependency tags."""
        ttl_val = self._default_ttl if ttl is None else ttl
        tags_list = tags or []

        with self._lock:
            # If key already existed, remove previous tag associations
            if key in self._store:
                old_entry = self._store[key]
                for tag in old_entry.tags:
                    if tag in self._tag_index:
                        self._tag_index[tag].discard(key)
                        if not self._tag_index[tag]:
                            del self._tag_index[tag]

            # Enforce bounded capacity via LRU eviction
            if len(self._store) >= self._max_size and key not in self._store:
                self.cleanup_expired()
                while len(self._store) >= self._max_size:
                    oldest_key, _ = next(iter(self._store.items()))
                    self._evict_entry(oldest_key)
                    self._evictions += 1

            entry = CacheEntry(key, value, ttl_val, tags_list)
            self._store[key] = entry
            self._store.move_to_end(key)

            # Index by tags for instant group invalidation
            for tag in entry.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(key)

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: Optional[float] = None, tags: Optional[List[str]] = None) -> Any:
        """Atomically fetch from cache or compute and store if missing (Cache-Aside pattern)."""
        val = self.get(key)
        if val is not None:
            return val

        # Compute outside lock if needed or within lock to avoid thundering herd
        with self._lock:
            # Double check within lock
            entry = self._store.get(key)
            if entry and not entry.is_expired:
                self._hits += 1
                return entry.value

            computed_val = factory()
            self.set(key, computed_val, ttl, tags)
            return computed_val

    def invalidate(self, key: str) -> bool:
        """Explicitly invalidate a single cached key."""
        with self._lock:
            if key in self._store:
                self._evict_entry(key)
                self._invalidations += 1
                return True
            return False

    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all cached keys associated with a dependency tag."""
        with self._lock:
            keys_to_remove = self._tag_index.get(tag, set()).copy()
            count = 0
            for k in keys_to_remove:
                if k in self._store:
                    self._evict_entry(k)
                    count += 1
            self._invalidations += count
            if tag in self._tag_index:
                del self._tag_index[tag]
            return count

    def invalidate_by_prefix(self, prefix: str) -> int:
        """Invalidate all keys starting with the given prefix."""
        with self._lock:
            matching_keys = [k for k in self._store if k.startswith(prefix)]
            count = 0
            for k in matching_keys:
                self._evict_entry(k)
                count += 1
            self._invalidations += count
            return count

    def clear(self) -> None:
        """Purge the entire cache and reset tag indices."""
        with self._lock:
            self._store.clear()
            self._tag_index.clear()
            self._invalidations += 1

    def cleanup_expired(self) -> int:
        """Active pruning of expired cache keys."""
        with self._lock:
            expired_keys = [k for k, entry in self._store.items() if entry.is_expired]
            for k in expired_keys:
                self._evict_entry(k)
            self._evictions += len(expired_keys)
            return len(expired_keys)

    def _evict_entry(self, key: str) -> None:
        """Internal helper to clean store and tag indices for a single key (requires lock)."""
        entry = self._store.pop(key, None)
        if entry:
            for tag in entry.tags:
                if tag in self._tag_index:
                    self._tag_index[tag].discard(key)
                    if not self._tag_index[tag]:
                        del self._tag_index[tag]

    def get_stats(self) -> Dict[str, Any]:
        """Return comprehensive cache telemetry and hit ratio."""
        with self._lock:
            total_reqs = self._hits + self._misses
            hit_ratio = round((self._hits / total_reqs * 100), 2) if total_reqs > 0 else 0.0
            now = time.time()
            active_entries = sum(1 for e in self._store.values() if not e.is_expired)

            return {
                "active_entries": active_entries,
                "total_entries": len(self._store),
                "total_tags": len(self._tag_index),
                "hits": self._hits,
                "misses": self._misses,
                "total_requests": total_reqs,
                "hit_ratio_percent": hit_ratio,
                "invalidations": self._invalidations,
                "evictions": self._evictions,
                "uptime_seconds": round(now - self._start_time, 2)
            }


# Singleton Global Cache Instance
cache_service = CacheService(default_ttl=60.0)


# Cache Key Generator Utilities
def make_dashboard_cache_key(
    role: str,
    hostel_id: Optional[int] = None,
    user_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """Generate deterministic, isolated cache key for dashboard aggregates."""
    parts = ["dashboard", f"role:{role}"]
    if hostel_id is not None:
        parts.append(f"hostel:{hostel_id}")
    else:
        parts.append("hostel:global")

    if user_id is not None and role in ("student", "parent_guardian", "warden", "assistant_warden"):
        parts.append(f"user:{user_id}")

    if date_from:
        parts.append(f"from:{date_from}")
    if date_to:
        parts.append(f"to:{date_to}")

    return ":".join(parts)
