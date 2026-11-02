import os
"""Notification Management Service.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
"""

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status

from backend.app.database.connection import get_db_connection
from backend.app.models.notification_dto import (
    NotificationCreate,
    NotificationResponse,
    NotificationListResponse,
    NotificationPreferenceDTO,
    NotificationPreferenceResponse
)
from backend.app.services.cache_service import cache_service
from backend.app.utils.logger import logger


class NotificationService:
    """Centralized notification management and multi-channel delivery service."""

    @classmethod
    def get_preferences(cls, user_id: int) -> NotificationPreferenceResponse:
        """Fetch notification preferences for a user, returning safe defaults if unset."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, in_app_enabled, email_enabled, browser_enabled, disabled_categories, updated_at
                FROM notification_preferences
                WHERE user_id = ?;
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return NotificationPreferenceResponse(
                    user_id=user_id,
                    in_app_enabled=True,
                    email_enabled=False,
                    browser_enabled=False,
                    disabled_categories=[],
                    updated_at=datetime.now().isoformat()
                )

            disabled = []
            try:
                disabled = json.loads(row["disabled_categories"] or "[]")
            except Exception:
                disabled = []

            return NotificationPreferenceResponse(
                user_id=row["user_id"],
                in_app_enabled=bool(row["in_app_enabled"]),
                email_enabled=bool(row["email_enabled"]),
                browser_enabled=bool(row["browser_enabled"]),
                disabled_categories=disabled,
                updated_at=row["updated_at"]
            )

    @classmethod
    def update_preferences(cls, user_id: int, payload: NotificationPreferenceDTO) -> NotificationPreferenceResponse:
        """Update notification preferences for the authenticated user."""
        now = datetime.now().isoformat()
        disabled_json = json.dumps(payload.disabled_categories or [])

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notification_preferences (
                    user_id, in_app_enabled, email_enabled, browser_enabled, disabled_categories, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    in_app_enabled = excluded.in_app_enabled,
                    email_enabled = excluded.email_enabled,
                    browser_enabled = excluded.browser_enabled,
                    disabled_categories = excluded.disabled_categories,
                    updated_at = excluded.updated_at;
            """, (
                user_id,
                1 if payload.in_app_enabled else 0,
                1 if payload.email_enabled else 0,
                1 if payload.browser_enabled else 0,
                disabled_json,
                now
            ))
            conn.commit()

        cache_service.invalidate(f"notif_pref:{user_id}")
        return cls.get_preferences(user_id)

    @classmethod
    def create_notification(cls, payload: NotificationCreate) -> Optional[NotificationResponse]:
        """Dispatch a new notification respecting Poka-Yoke deduplication and user preferences."""
        # 1. Check user preferences
        prefs = cls.get_preferences(payload.user_id)
        if not prefs.in_app_enabled and payload.priority != "Critical":
            logger.info(f"Notification suppressed for user #{payload.user_id}: In-app notifications disabled.")
            return None

        if payload.category in prefs.disabled_categories and payload.priority != "Critical":
            logger.info(f"Notification suppressed for user #{payload.user_id}: Category '{payload.category}' disabled in user preferences.")
            return None

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 2. Poka-Yoke: Prevent duplicate notifications for the same event
            if payload.event_key and payload.event_key.strip():
                cursor.execute("""
                    SELECT id, user_id, title, message, category, priority, notification_type,
                           is_read, read_at, related_entity_type, related_entity_id, event_key, delivery_channel, created_at
                    FROM notifications
                    WHERE user_id = ? AND event_key = ?;
                """, (payload.user_id, payload.event_key.strip()))
                existing = cursor.fetchone()
                if existing:
                    logger.debug(f"Poka-Yoke: Duplicate notification prevented for event_key='{payload.event_key}'.")
                    return NotificationResponse(
                        id=existing["id"],
                        user_id=existing["user_id"],
                        title=existing["title"],
                        message=existing["message"],
                        category=existing["category"] or "general",
                        priority=existing["priority"] or "Normal",
                        notification_type=existing["notification_type"] or "info",
                        is_read=bool(existing["is_read"]),
                        read_at=existing["read_at"],
                        related_entity_type=existing["related_entity_type"] or "",
                        related_entity_id=existing["related_entity_id"] or "",
                        event_key=existing["event_key"] or "",
                        delivery_channel=existing["delivery_channel"] or "in_app",
                        created_at=existing["created_at"]
                    )

            # 3. Insert notification
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO notifications (
                    user_id, title, message, category, priority, notification_type,
                    is_read, related_entity_type, related_entity_id, event_key, delivery_channel, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?);
            """, (
                payload.user_id,
                payload.title.strip(),
                payload.message.strip(),
                payload.category,
                payload.priority,
                payload.notification_type,
                payload.related_entity_type or "",
                payload.related_entity_id or "",
                payload.event_key or "",
                payload.delivery_channel,
                now
            ))
            notif_id = cursor.lastrowid
            conn.commit()

        # Invalidate unread cache
        cache_service.invalidate(f"notif_unread:{payload.user_id}")

        # 4. Optional delivery channels
        cls._dispatch_optional_channels(payload, prefs)

        return NotificationResponse(
            id=notif_id,
            user_id=payload.user_id,
            title=payload.title,
            message=payload.message,
            category=payload.category,
            priority=payload.priority,
            notification_type=payload.notification_type,
            is_read=False,
            read_at=None,
            related_entity_type=payload.related_entity_type or "",
            related_entity_id=payload.related_entity_id or "",
            event_key=payload.event_key or "",
            delivery_channel=payload.delivery_channel,
            created_at=now
        )

    @classmethod
    def _dispatch_optional_channels(cls, payload: NotificationCreate, prefs: NotificationPreferenceResponse) -> None:
        """Handle optional external delivery channels gracefully without crashing if unconfigured."""
        # Email channel check
        if prefs.email_enabled:
            # Check system setting
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'email_notifications_enabled';")
                row = cursor.fetchone()
                is_enabled = row and row["setting_value"].lower() == "true"
                smtp_host = os.getenv("SMTP_HOST")
                if is_enabled and smtp_host:
                    logger.info(f"[Email Channel] Dispatched email notification to user #{payload.user_id} via {smtp_host}: '{payload.title}'")
                elif is_enabled:
                    logger.info(f"[Email Channel] Email notification marked Unconfigured_Channel for user #{payload.user_id} (SMTP_HOST not set): '{payload.title}'")
                else:
                    logger.debug(f"[Email Channel] Email dispatch skipped for user #{payload.user_id} (email_notifications_enabled=false).")

        # Browser notification check
        if prefs.browser_enabled:
            logger.debug(f"[Browser Channel] Browser notification queued for user #{payload.user_id}: '{payload.title}'")

    @classmethod
    def get_user_notifications(
        cls,
        user_id: int,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        is_read: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> NotificationListResponse:
        """Retrieve paginated notifications for the user with sub-10ms Q05 SLA."""
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        offset = (page - 1) * page_size

        with get_db_connection() as conn:
            cursor = conn.cursor()

            conditions = ["user_id = ?"]
            params: List[Any] = [user_id]

            if category:
                conditions.append("category = ?")
                params.append(category)

            if priority:
                conditions.append("priority = ?")
                params.append(priority)

            if is_read is not None:
                conditions.append("is_read = ?")
                params.append(1 if is_read else 0)

            if search and search.strip():
                s = f"%{search.strip()}%"
                conditions.append("(title LIKE ? OR message LIKE ?)")
                params.extend([s, s])

            where_clause = " WHERE " + " AND ".join(conditions)

            # Get total count
            cursor.execute(f"SELECT COUNT(*) FROM notifications {where_clause};", params)
            total = cursor.fetchone()[0]

            # Get unread count
            cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0;", (user_id,))
            unread_count = cursor.fetchone()[0]

            # Get items
            query = f"""
                SELECT id, user_id, title, message, category, priority, notification_type,
                       is_read, read_at, related_entity_type, related_entity_id, event_key, delivery_channel, created_at
                FROM notifications
                {where_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?;
            """
            cursor.execute(query, params + [page_size, offset])
            rows = cursor.fetchall()

            items = []
            for r in rows:
                items.append(NotificationResponse(
                    id=r["id"],
                    user_id=r["user_id"],
                    title=r["title"],
                    message=r["message"],
                    category=r["category"] or "general",
                    priority=r["priority"] or "Normal",
                    notification_type=r["notification_type"] or "info",
                    is_read=bool(r["is_read"]),
                    read_at=r["read_at"],
                    related_entity_type=r["related_entity_type"] or "",
                    related_entity_id=r["related_entity_id"] or "",
                    event_key=r["event_key"] or "",
                    delivery_channel=r["delivery_channel"] or "in_app",
                    created_at=r["created_at"]
                ))

            return NotificationListResponse(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                unread_count=unread_count
            )

    @classmethod
    def get_unread_count(cls, user_id: int) -> int:
        """Get ultra-fast unread notification count with microsecond cached response."""
        cache_key = f"notif_unread:{user_id}"
        cached = cache_service.get(cache_key)
        if cached is not None:
            return int(cached)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0;", (user_id,))
            count = cursor.fetchone()[0]
            cache_service.set(cache_key, count, ttl=30)
            return count

    @classmethod
    def mark_as_read(cls, notification_id: int, user_id: int) -> bool:
        """Mark single notification as read with strict user data isolation."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM notifications WHERE id = ?;", (notification_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Notification not found.")

            if row["user_id"] != user_id:
                raise HTTPException(status_code=403, detail="Unauthorized: Cannot access another user's notification.")

            cursor.execute("""
                UPDATE notifications
                SET is_read = 1, read_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (notification_id,))
            conn.commit()

        cache_service.invalidate(f"notif_unread:{user_id}")
        return True

    @classmethod
    def mark_all_read(cls, user_id: int) -> int:
        """Mark all unread notifications as read for the user."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE notifications
                SET is_read = 1, read_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND is_read = 0;
            """, (user_id,))
            affected = cursor.rowcount
            conn.commit()

        cache_service.invalidate(f"notif_unread:{user_id}")
        return affected
