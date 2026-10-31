"""Transactional Dependency-Based Cache Invalidation Engine.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

from contextlib import contextmanager
import sqlite3
from typing import Generator, List, Optional
from backend.app.services.cache_service import cache_service
from backend.app.utils.logger import logger


class CacheInvalidator:
    """Centralized invalidation coordinator executing atomic cache evictions following DB commits."""

    @staticmethod
    def on_student_mutation(hostel_id: Optional[int] = None) -> int:
        """Invalidate student rosters and affected dashboard scopes."""
        count = cache_service.invalidate_by_tag("students")
        count += cache_service.invalidate_by_tag("global")
        if hostel_id:
            count += cache_service.invalidate_by_tag(f"hostel_{hostel_id}")
        logger.info(f"Cache Invalidation: Student mutation evicted {count} cache entries.")
        return count

    @staticmethod
    def on_allocation_mutation(hostel_id: Optional[int] = None) -> int:
        """Invalidate allocation matrices, beds, and room capacities."""
        tags = ["allocations", "beds", "rooms", "global"]
        if hostel_id:
            tags.append(f"hostel_{hostel_id}")

        count = sum(cache_service.invalidate_by_tag(tag) for tag in tags)
        logger.info(f"Cache Invalidation: Allocation mutation evicted {count} cache entries (tags: {tags}).")
        return count

    @staticmethod
    def on_hostel_infrastructure_mutation(hostel_id: Optional[int] = None) -> int:
        """Invalidate hostel hierarchy, rooms, and bed directories."""
        tags = ["hostels", "rooms", "beds", "global"]
        if hostel_id:
            tags.append(f"hostel_{hostel_id}")

        count = sum(cache_service.invalidate_by_tag(tag) for tag in tags)
        logger.info(f"Cache Invalidation: Infrastructure mutation evicted {count} cache entries.")
        return count

    @staticmethod
    def on_complaint_mutation(hostel_id: Optional[int] = None) -> int:
        """Invalidate grievance queues and operational counts."""
        tags = ["complaints", "global"]
        if hostel_id:
            tags.append(f"hostel_{hostel_id}")

        count = sum(cache_service.invalidate_by_tag(tag) for tag in tags)
        logger.info(f"Cache Invalidation: Complaint mutation evicted {count} cache entries.")
        return count

    @staticmethod
    def on_maintenance_mutation(hostel_id: Optional[int] = None) -> int:
        """Invalidate facility maintenance task counts and schedules."""
        tags = ["maintenance", "global"]
        if hostel_id:
            tags.append(f"hostel_{hostel_id}")

        count = sum(cache_service.invalidate_by_tag(tag) for tag in tags)
        logger.info(f"Cache Invalidation: Maintenance mutation evicted {count} cache entries.")
        return count

    @staticmethod
    def on_financial_mutation() -> int:
        """Invalidate ledger aggregates, invoice tallies, and fee collections."""
        count = cache_service.invalidate_by_tag("finance")
        count += cache_service.invalidate_by_tag("global")
        logger.info(f"Cache Invalidation: Financial mutation evicted {count} cache entries.")
        return count

    @staticmethod
    def on_admission_mutation() -> int:
        """Invalidate pending candidate admissions and intake statistics."""
        count = cache_service.invalidate_by_tag("admissions")
        count += cache_service.invalidate_by_tag("global")
        logger.info(f"Cache Invalidation: Admission mutation evicted {count} cache entries.")
        return count


@contextmanager
def transactional_cache_invalidation(conn: sqlite3.Connection, tags: List[str]) -> Generator[None, None, None]:
    """Execute a database transaction and only invalidate cached tags upon successful COMMIT.
    If an exception is raised, the transaction is safely ROLLED BACK and no cache invalidation occurs.
    """
    try:
        yield
        conn.commit()
        for tag in tags:
            cache_service.invalidate_by_tag(tag)
    except Exception:
        conn.rollback()
        raise
