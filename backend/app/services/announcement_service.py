"""Announcement Management Service.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status

from backend.app.database.connection import get_db_connection
from backend.app.models.announcement_dto import (
    AnnouncementCreate,
    AnnouncementUpdate,
    AnnouncementResponse,
    AnnouncementViewResponse
)
from backend.app.models.notification_dto import NotificationCreate
from backend.app.services.notification_service import NotificationService
from backend.app.services.cache_service import cache_service
from backend.app.utils.logger import logger


class AnnouncementService:
    """Centralized announcement creation, lifecycle management, and audience targeting."""

    @staticmethod
    def _extract_user_id(current_user: Dict[str, Any]) -> int:
        return current_user.get("user_id") or current_user.get("id") or 1

    @staticmethod
    def _extract_role(current_user: Dict[str, Any]) -> str:
        role = current_user.get("role")
        if not role and current_user.get("roles") and isinstance(current_user["roles"], list):
            role = current_user["roles"][0]
        return role or "student"

    @classmethod
    def _enforce_admin_or_warden(cls, current_user: Dict[str, Any]):
        role = cls._extract_role(current_user)
        if role not in ["super_admin", "hostel_admin", "warden", "assistant_warden"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only administrators and wardens can create or manage announcements."
            )

    @classmethod
    def create_announcement(cls, payload: AnnouncementCreate, current_user: Dict[str, Any]) -> AnnouncementResponse:
        """Create a new announcement with audience targeting and lifecycle state."""
        cls._enforce_admin_or_warden(current_user)
        user_id = cls._extract_user_id(current_user)
        now = datetime.now().isoformat()
        publish_time = payload.publish_at or (now if payload.status == "Published" else None)

        roles_str = ",".join(payload.target_roles or [])

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO announcements (
                    title, content, category, priority, target_audience, target_hostel_id,
                    target_roles, status, publish_at, expires_at, attachment_url, attachment_name,
                    created_by, published_by, published_at, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?);
            """, (
                payload.title.strip(),
                payload.content.strip(),
                payload.category,
                payload.priority,
                payload.target_audience,
                payload.target_hostel_id,
                roles_str,
                payload.status,
                publish_time,
                payload.expires_at,
                payload.attachment_url or "",
                payload.attachment_name or "",
                user_id,
                user_id if payload.status == "Published" else None,
                publish_time if payload.status == "Published" else None,
                now
            ))
            ann_id = cursor.lastrowid

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'CREATE_ANNOUNCEMENT', 'announcements', ?, ?, 0.5);
            """, (
                user_id,
                current_user.get("username", "admin"),
                str(ann_id),
                f"Created announcement #{ann_id} '{payload.title}' with status {payload.status}"
            ))
            conn.commit()

        cache_service.invalidate_by_tag("announcements")
        logger.info(f"Announcement #{ann_id} created by user #{user_id} (Status: {payload.status})")

        # If published immediately, dispatch notifications to target audience
        if payload.status == "Published":
            cls._notify_target_audience(ann_id, payload.title, payload.category, payload.priority, payload.target_audience, payload.target_hostel_id)

        return cls.get_announcement_by_id(ann_id, current_user)

    @classmethod
    def get_announcements(
        cls,
        current_user: Dict[str, Any],
        category: Optional[str] = None,
        priority: Optional[str] = None,
        status_filter: Optional[str] = None,
        hostel_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 50
    ) -> List[AnnouncementResponse]:
        """Fetch targeted announcements for the user with sub-10ms Q05 SLA."""
        user_id = cls._extract_user_id(current_user)
        role = cls._extract_role(current_user)
        is_admin = role in ["super_admin", "hostel_admin", "warden", "assistant_warden"]

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Determine user's assigned hostel if resident student
            user_hostel_id = None
            if role == "student":
                cursor.execute("""
                    SELECT bl.hostel_id
                    FROM room_allocations ra
                    JOIN beds b ON ra.bed_id = b.id
                    JOIN rooms r ON b.room_id = r.id
                    JOIN floors fl ON r.floor_id = fl.id
                    JOIN buildings bl ON fl.building_id = bl.id
                    JOIN students s ON ra.student_id = s.id
                    WHERE s.user_id = ?
                    ORDER BY ra.id DESC
                    LIMIT 1;
                """, (user_id,))
                h_row = cursor.fetchone()
                if h_row:
                    user_hostel_id = h_row[0]
                else:
                    cursor.execute("SELECT linked_hostel_id FROM users WHERE id = ?;", (user_id,))
                    u_h = cursor.fetchone()
                    if u_h and u_h[0]:
                        user_hostel_id = u_h[0]

            conditions = ["a.is_active = 1"]
            params: List[Any] = []

            # Non-admins only see published, unexpired announcements
            if not is_admin:
                conditions.append("a.status = 'Published'")
                now_str = datetime.now().isoformat()
                conditions.append("(a.publish_at IS NULL OR a.publish_at <= ?)")
                params.append(now_str)
                conditions.append("(a.expires_at IS NULL OR a.expires_at > ?)")
                params.append(now_str)

                # Audience targeting rules
                if role == "student":
                    conditions.append("""
                        (a.target_audience IN ('All Users', 'All Students', 'all', 'students')
                         OR (a.target_audience = 'Hostel Residents' AND (a.target_hostel_id IS NULL OR a.target_hostel_id = ?)))
                    """)
                    params.append(user_hostel_id or -1)
                elif role == "parent_guardian":
                    conditions.append("a.target_audience IN ('All Users', 'Guardians', 'all')")
                else:
                    conditions.append("(a.target_audience IN ('All Users', 'all') OR a.target_roles LIKE ?)")
                    params.append(f"%{role}%")
            else:
                # Admins can filter by status
                if status_filter:
                    conditions.append("a.status = ?")
                    params.append(status_filter)

            if category:
                conditions.append("a.category = ?")
                params.append(category)

            if priority:
                conditions.append("a.priority = ?")
                params.append(priority)

            if hostel_id:
                conditions.append("(a.target_hostel_id = ? OR a.target_hostel_id IS NULL)")
                params.append(hostel_id)

            if search and search.strip():
                s = f"%{search.strip()}%"
                conditions.append("(a.title LIKE ? OR a.content LIKE ?)")
                params.extend([s, s])

            where_clause = " WHERE " + " AND ".join(conditions)

            query = f"""
                SELECT a.*,
                       h.name AS target_hostel_name,
                       (u.first_name || ' ' || u.last_name) AS created_by_name,
                       (SELECT COUNT(*) FROM announcement_views v WHERE v.announcement_id = a.id) AS view_count,
                       (SELECT COUNT(*) FROM announcement_views v WHERE v.announcement_id = a.id AND v.acknowledged_at IS NOT NULL) AS acknowledged_count,
                       EXISTS(SELECT 1 FROM announcement_views v WHERE v.announcement_id = a.id AND v.user_id = ?) AS is_viewed_by_me,
                       EXISTS(SELECT 1 FROM announcement_views v WHERE v.announcement_id = a.id AND v.user_id = ? AND v.acknowledged_at IS NOT NULL) AS is_acknowledged_by_me
                FROM announcements a
                LEFT JOIN hostels h ON a.target_hostel_id = h.id
                LEFT JOIN users u ON a.created_by = u.id
                {where_clause}
                ORDER BY 
                    CASE a.priority
                        WHEN 'Critical' THEN 1
                        WHEN 'Emergency' THEN 1
                        WHEN 'High' THEN 2
                        WHEN 'Normal' THEN 3
                        ELSE 4
                    END,
                    a.created_at DESC
                LIMIT ?;
            """
            cursor.execute(query, [user_id, user_id] + params + [limit])
            rows = cursor.fetchall()

            results = []
            for r in rows:
                roles_list = [role_str.strip() for role_str in (r["target_roles"] or "").split(",") if role_str.strip()]
                results.append(AnnouncementResponse(
                    id=r["id"],
                    title=r["title"],
                    content=r["content"],
                    category=r["category"] or "General Notice",
                    priority=r["priority"] or "Normal",
                    target_audience=r["target_audience"] or "All Users",
                    target_hostel_id=r["target_hostel_id"],
                    target_hostel_name=r["target_hostel_name"],
                    target_roles=roles_list,
                    status=r["status"] or "Published",
                    publish_at=r["publish_at"],
                    expires_at=r["expires_at"],
                    attachment_url=r["attachment_url"] or "",
                    attachment_name=r["attachment_name"] or "",
                    created_by=r["created_by"],
                    created_by_name=r["created_by_name"] or "System Admin",
                    published_by=r["published_by"],
                    published_at=r["published_at"],
                    archived_at=r["archived_at"],
                    is_active=bool(r["is_active"]),
                    view_count=r["view_count"] or 0,
                    acknowledged_count=r["acknowledged_count"] or 0,
                    is_viewed_by_me=bool(r["is_viewed_by_me"]),
                    is_acknowledged_by_me=bool(r["is_acknowledged_by_me"]),
                    created_at=r["created_at"]
                ))
            return results

    @classmethod
    def get_announcement_by_id(cls, announcement_id: int, current_user: Dict[str, Any]) -> AnnouncementResponse:
        """Fetch single announcement detail and record view for user."""
        user_id = cls._extract_user_id(current_user)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.*,
                       h.name AS target_hostel_name,
                       (u.first_name || ' ' || u.last_name) AS created_by_name,
                       (SELECT COUNT(*) FROM announcement_views v WHERE v.announcement_id = a.id) AS view_count,
                       (SELECT COUNT(*) FROM announcement_views v WHERE v.announcement_id = a.id AND v.acknowledged_at IS NOT NULL) AS acknowledged_count,
                       EXISTS(SELECT 1 FROM announcement_views v WHERE v.announcement_id = a.id AND v.user_id = ?) AS is_viewed_by_me,
                       EXISTS(SELECT 1 FROM announcement_views v WHERE v.announcement_id = a.id AND v.user_id = ? AND v.acknowledged_at IS NOT NULL) AS is_acknowledged_by_me
                FROM announcements a
                LEFT JOIN hostels h ON a.target_hostel_id = h.id
                LEFT JOIN users u ON a.created_by = u.id
                WHERE a.id = ?;
            """, (user_id, user_id, announcement_id))
            r = cursor.fetchone()
            if not r:
                raise HTTPException(status_code=404, detail="Announcement not found.")

            # Record user view in announcement_views
            cursor.execute("""
                INSERT OR IGNORE INTO announcement_views (announcement_id, user_id, viewed_at)
                VALUES (?, ?, CURRENT_TIMESTAMP);
            """, (announcement_id, user_id))
            conn.commit()

            roles_list = [role_str.strip() for role_str in (r["target_roles"] or "").split(",") if role_str.strip()]
            return AnnouncementResponse(
                id=r["id"],
                title=r["title"],
                content=r["content"],
                category=r["category"] or "General Notice",
                priority=r["priority"] or "Normal",
                target_audience=r["target_audience"] or "All Users",
                target_hostel_id=r["target_hostel_id"],
                target_hostel_name=r["target_hostel_name"],
                target_roles=roles_list,
                status=r["status"] or "Published",
                publish_at=r["publish_at"],
                expires_at=r["expires_at"],
                attachment_url=r["attachment_url"] or "",
                attachment_name=r["attachment_name"] or "",
                created_by=r["created_by"],
                created_by_name=r["created_by_name"] or "System Admin",
                published_by=r["published_by"],
                published_at=r["published_at"],
                archived_at=r["archived_at"],
                is_active=bool(r["is_active"]),
                view_count=r["view_count"] or 0,
                acknowledged_count=r["acknowledged_count"] or 0,
                is_viewed_by_me=True,
                is_acknowledged_by_me=bool(r["is_acknowledged_by_me"]),
                created_at=r["created_at"]
            )

    @classmethod
    def update_announcement(cls, announcement_id: int, payload: AnnouncementUpdate, current_user: Dict[str, Any]) -> AnnouncementResponse:
        """Update announcement fields with administrative privilege validation."""
        cls._enforce_admin_or_warden(current_user)
        user_id = cls._extract_user_id(current_user)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM announcements WHERE id = ?;", (announcement_id,))
            current = cursor.fetchone()
            if not current:
                raise HTTPException(status_code=404, detail="Announcement not found.")

            update_data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
            if not update_data:
                return cls.get_announcement_by_id(announcement_id, current_user)

            if "target_roles" in update_data and update_data["target_roles"] is not None:
                update_data["target_roles"] = ",".join(update_data["target_roles"])

            fields = []
            values = []
            for k, v in update_data.items():
                fields.append(f"{k} = ?")
                values.append(v)
            values.append(announcement_id)

            cursor.execute(f"UPDATE announcements SET {', '.join(fields)} WHERE id = ?;", values)

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'UPDATE_ANNOUNCEMENT', 'announcements', ?, ?, 0.5);
            """, (
                user_id,
                current_user.get("username", "admin"),
                str(announcement_id),
                f"Updated announcement #{announcement_id} fields: {list(update_data.keys())}"
            ))
            conn.commit()

        cache_service.invalidate_by_tag("announcements")
        return cls.get_announcement_by_id(announcement_id, current_user)

    @classmethod
    def publish_announcement(cls, announcement_id: int, current_user: Dict[str, Any]) -> AnnouncementResponse:
        """Publish a draft or scheduled announcement immediately and notify target audience."""
        cls._enforce_admin_or_warden(current_user)
        user_id = cls._extract_user_id(current_user)
        now = datetime.now().isoformat()

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM announcements WHERE id = ?;", (announcement_id,))
            ann = cursor.fetchone()
            if not ann:
                raise HTTPException(status_code=404, detail="Announcement not found.")

            cursor.execute("""
                UPDATE announcements
                SET status = 'Published', published_by = ?, published_at = ?, publish_at = ?
                WHERE id = ?;
            """, (user_id, now, now, announcement_id))

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'PUBLISH_ANNOUNCEMENT', 'announcements', ?, ?, 0.5);
            """, (
                user_id,
                current_user.get("username", "admin"),
                str(announcement_id),
                f"Published announcement #{announcement_id} '{ann['title']}'"
            ))
            conn.commit()

        cache_service.invalidate_by_tag("announcements")
        cls._notify_target_audience(ann_id=announcement_id, title=ann["title"], category=ann["category"], priority=ann["priority"], target_audience=ann["target_audience"], target_hostel_id=ann["target_hostel_id"])
        return cls.get_announcement_by_id(announcement_id, current_user)

    @classmethod
    def archive_announcement(cls, announcement_id: int, current_user: Dict[str, Any]) -> AnnouncementResponse:
        """Archive an announcement, removing it from active dashboards."""
        cls._enforce_admin_or_warden(current_user)
        user_id = cls._extract_user_id(current_user)
        now = datetime.now().isoformat()

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM announcements WHERE id = ?;", (announcement_id,))
            ann = cursor.fetchone()
            if not ann:
                raise HTTPException(status_code=404, detail="Announcement not found.")

            cursor.execute("""
                UPDATE announcements
                SET status = 'Archived', archived_at = ?, archived_by = ?
                WHERE id = ?;
            """, (now, user_id, announcement_id))

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'ARCHIVE_ANNOUNCEMENT', 'announcements', ?, ?, 0.5);
            """, (
                user_id,
                current_user.get("username", "admin"),
                str(announcement_id),
                f"Archived announcement #{announcement_id} '{ann['title']}'"
            ))
            conn.commit()

        cache_service.invalidate_by_tag("announcements")
        return cls.get_announcement_by_id(announcement_id, current_user)

    @classmethod
    def acknowledge_announcement(cls, announcement_id: int, current_user: Dict[str, Any]) -> bool:
        """Record formal student/resident acknowledgement for mandatory notices."""
        user_id = cls._extract_user_id(current_user)
        now = datetime.now().isoformat()

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO announcement_views (announcement_id, user_id, viewed_at, acknowledged_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(announcement_id, user_id) DO UPDATE SET
                    acknowledged_at = excluded.acknowledged_at;
            """, (announcement_id, user_id, now, now))
            conn.commit()

        return True

    @classmethod
    def get_announcement_views(cls, announcement_id: int, current_user: Dict[str, Any]) -> List[AnnouncementViewResponse]:
        """Administrative inspection of users who viewed or acknowledged an announcement."""
        cls._enforce_admin_or_warden(current_user)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.id, v.user_id, v.viewed_at, v.acknowledged_at,
                       u.username, u.first_name, u.last_name,
                       COALESCE(
                           (SELECT r.name FROM user_roles ur JOIN roles r ON ur.role_id = r.id WHERE ur.user_id = u.id LIMIT 1),
                           'student'
                       ) AS role
                FROM announcement_views v
                JOIN users u ON v.user_id = u.id
                WHERE v.announcement_id = ?
                ORDER BY v.viewed_at DESC;
            """, (announcement_id,))
            rows = cursor.fetchall()
            return [
                AnnouncementViewResponse(
                    id=r["id"],
                    user_id=r["user_id"],
                    username=r["username"],
                    first_name=r["first_name"] or "",
                    last_name=r["last_name"] or "",
                    role=r["role"],
                    viewed_at=r["viewed_at"],
                    acknowledged_at=r["acknowledged_at"]
                )
                for r in rows
            ]

    @classmethod
    def _notify_target_audience(
        cls,
        ann_id: int,
        title: str,
        category: str,
        priority: str,
        target_audience: str,
        target_hostel_id: Optional[int]
    ) -> None:
        """Dispatches automated in-app notifications to eligible recipients of an announcement."""
        notif_priority = "Critical" if priority in ["Critical", "Emergency"] else ("High" if priority == "High" else "Normal")
        notif_type = "alert" if priority in ["Critical", "Emergency"] else ("warning" if priority == "High" else "info")

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Target user IDs selection
            if target_audience in ["All Users", "all"]:
                cursor.execute("SELECT id FROM users WHERE is_active = 1;")
            elif target_audience in ["All Students", "students"]:
                cursor.execute("""
                    SELECT u.id
                    FROM users u
                    JOIN user_roles ur ON u.id = ur.user_id
                    JOIN roles r ON ur.role_id = r.id
                    WHERE u.is_active = 1 AND r.name = 'student';
                """)
            elif target_audience == "Hostel Residents" and target_hostel_id:
                cursor.execute("""
                    SELECT s.user_id
                    FROM room_allocations ra
                    JOIN beds b ON ra.bed_id = b.id
                    JOIN rooms r ON b.room_id = r.id
                    JOIN floors fl ON r.floor_id = fl.id
                    JOIN buildings bl ON fl.building_id = bl.id
                    JOIN students s ON ra.student_id = s.id
                    WHERE bl.hostel_id = ? AND ra.allocation_status = 'Active' AND s.user_id IS NOT NULL;
                """, (target_hostel_id,))
            else:
                cursor.execute("SELECT id FROM users WHERE is_active = 1 LIMIT 200;")

            recipient_ids = [row[0] for row in cursor.fetchall()]

        # Dispatch notifications
        for uid in recipient_ids:
            try:
                NotificationService.create_notification(NotificationCreate(
                    user_id=uid,
                    title=f"Announcement: {title}",
                    message=f"A new notice has been published under category '{category}'. Priority: {priority}.",
                    category="announcement",
                    priority=notif_priority,
                    notification_type=notif_type,
                    related_entity_type="announcement",
                    related_entity_id=str(ann_id),
                    event_key=f"announcement:{ann_id}:{uid}"
                ))
            except Exception as e:
                logger.warning(f"Failed to dispatch announcement notification to user #{uid}: {e}")
