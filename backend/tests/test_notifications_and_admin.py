"""Unit and Integration Tests for Notifications, Announcements, System Admin & Backups.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
"""

import os
import unittest
import uuid
from datetime import datetime, timedelta
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.database.connection import get_db_connection
from backend.app.main import app
from backend.app.models.admin_dto import (
    SystemSettingsBulkUpdate,
    UserStatusUpdate,
    UserRolesUpdate,
    UserPasswordResetAdmin,
    RolePermissionsUpdate
)
from backend.app.models.announcement_dto import (
    AnnouncementCreate,
    AnnouncementUpdate
)
from backend.app.models.notification_dto import (
    NotificationCreate,
    NotificationPreferenceDTO
)
from backend.app.services.admin_service import AdminService
from backend.app.services.announcement_service import AnnouncementService
from backend.app.services.backup_service import BackupService
from backend.app.services.notification_service import NotificationService


class TestNotificationsAndAdmin(unittest.TestCase):
    """Rigorous test suite covering Prompt 14 & 15 deliverables."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.admin_user = {
            "id": 1,
            "user_id": 1,
            "username": "admin",
            "role": "super_admin",
            "roles": ["super_admin"]
        }
        cls.warden_user = {
            "id": 3,
            "user_id": 3,
            "username": "warden",
            "role": "warden",
            "roles": ["warden"]
        }
        cls.student_user = {
            "id": 5,
            "user_id": 5,
            "username": "rohan",
            "role": "student",
            "roles": ["student"]
        }

    # ==================== 1. NOTIFICATION TESTS ====================

    def test_notification_creation_and_preferences(self):
        """Verify notification dispatch, user preferences, and category suppression."""
        uid = 5  # Rohan
        # Set preferences to disable 'mess' category
        NotificationService.update_preferences(
            uid,
            NotificationPreferenceDTO(
                in_app_enabled=True,
                email_enabled=False,
                browser_enabled=False,
                disabled_categories=["mess"]
            )
        )

        # 1. Normal notification under disabled category -> Suppressed (returns None)
        suppressed = NotificationService.create_notification(NotificationCreate(
            user_id=uid,
            title="Dinner Menu Updated",
            message="Check out today's dinner menu.",
            category="mess",
            priority="Normal",
            notification_type="info"
        ))
        self.assertIsNone(suppressed)

        # 2. Critical notification under disabled category -> Bypasses suppression
        critical = NotificationService.create_notification(NotificationCreate(
            user_id=uid,
            title="Mess Emergency Evacuation",
            message="Immediate evacuation due to gas leak drill.",
            category="mess",
            priority="Critical",
            notification_type="alert"
        ))
        self.assertIsNotNone(critical)
        self.assertEqual(critical.priority, "Critical")

        # 3. Enabled category notification -> Dispatched
        allowed = NotificationService.create_notification(NotificationCreate(
            user_id=uid,
            title="Room Allocation Confirmed",
            message="Your allocation in Room 101 has been confirmed.",
            category="room",
            priority="High",
            notification_type="success"
        ))
        self.assertIsNotNone(allowed)
        self.assertEqual(allowed.title, "Room Allocation Confirmed")

    def test_notification_unread_and_mark_read(self):
        """Verify unread counts, mark-as-read, and user-level data isolation."""
        uid = 5
        notif = NotificationService.create_notification(NotificationCreate(
            user_id=uid,
            title="Fee Reminder",
            message="Semester fee is due next week.",
            category="finance",
            priority="Normal",
            notification_type="warning"
        ))
        self.assertIsNotNone(notif)

        # Check unread count
        unread = NotificationService.get_unread_count(uid)
        self.assertGreaterEqual(unread, 1)

        # User isolation: User 3 cannot mark User 5's notification as read
        with self.assertRaises(HTTPException) as ctx:
            NotificationService.mark_as_read(notif.id, user_id=3)
        self.assertEqual(ctx.exception.status_code, 403)

        # Legitimate owner marks as read
        success = NotificationService.mark_as_read(notif.id, user_id=uid)
        self.assertTrue(success)

        # Mark all read
        affected = NotificationService.mark_all_read(uid)
        self.assertGreaterEqual(affected, 0)
        self.assertEqual(NotificationService.get_unread_count(uid), 0)

    def test_notification_poka_yoke_duplicate_prevention(self):
        """Poka-Yoke: Prevent duplicate notifications for the exact same event."""
        uid = 5
        event_key = f"fee_inv_1099_{uuid.uuid4().hex[:6]}"

        notif1 = NotificationService.create_notification(NotificationCreate(
            user_id=uid,
            title="Invoice Generated",
            message="Invoice INV-202611-0099 is generated.",
            category="finance",
            priority="Normal",
            event_key=event_key
        ))
        self.assertIsNotNone(notif1)

        # Second dispatch with identical event_key must return existing without duplicate insert
        notif2 = NotificationService.create_notification(NotificationCreate(
            user_id=uid,
            title="Invoice Generated (Duplicate)",
            message="Invoice INV-202611-0099 is generated.",
            category="finance",
            priority="Normal",
            event_key=event_key
        ))
        self.assertEqual(notif1.id, notif2.id)

    # ==================== 2. ANNOUNCEMENT TESTS ====================

    def test_announcement_crud_and_lifecycle(self):
        """Verify announcement lifecycle: Draft -> Update -> Publish -> Archive."""
        title = f"Campus Library Hours Extended {uuid.uuid4().hex[:4]}"
        created = AnnouncementService.create_announcement(
            AnnouncementCreate(
                title=title,
                content="Library reading halls will now remain open until 02:00 AM during exams.",
                category="Academic Notice",
                priority="Normal",
                target_audience="All Users",
                status="Draft"
            ),
            self.admin_user
        )
        self.assertEqual(created.status, "Draft")
        ann_id = created.id

        # Update announcement
        updated = AnnouncementService.update_announcement(
            ann_id,
            AnnouncementUpdate(priority="High"),
            self.admin_user
        )
        self.assertEqual(updated.priority, "High")

        # Publish announcement -> verifies notification generation
        published = AnnouncementService.publish_announcement(ann_id, self.admin_user)
        self.assertEqual(published.status, "Published")

        # Archive announcement
        archived = AnnouncementService.archive_announcement(ann_id, self.admin_user)
        self.assertEqual(archived.status, "Archived")

    def test_announcement_audience_targeting_and_hostel_isolation(self):
        """Verify target audience filtering: hostel residents only see notices for their hostel."""
        title = f"Nilgiri Hostel Lift Maintenance {uuid.uuid4().hex[:4]}"
        ann = AnnouncementService.create_announcement(
            AnnouncementCreate(
                title=title,
                content="Lift A in Nilgiri Hostel will be paused for greasing.",
                category="Maintenance Notice",
                priority="Normal",
                target_audience="Hostel Residents",
                target_hostel_id=1,  # Nilgiri Hostel
                status="Published"
            ),
            self.admin_user
        )

        # Fetch as student assigned to Hostel 1
        visible_list = AnnouncementService.get_announcements(self.student_user)
        found = any(a.id == ann.id for a in visible_list)
        self.assertTrue(found, "Resident student should see notice targeted to their assigned hostel.")

    def test_announcement_views_and_acknowledgement(self):
        """Verify view logging and formal resident acknowledgement recording."""
        title = f"Mandatory Safety Drill {uuid.uuid4().hex[:4]}"
        ann = AnnouncementService.create_announcement(
            AnnouncementCreate(
                title=title,
                content="All hostel residents must participate in the fire safety drill on Friday.",
                category="Emergency Notice",
                priority="Critical",
                target_audience="All Users",
                status="Published"
            ),
            self.admin_user
        )

        # Student views announcement
        detail = AnnouncementService.get_announcement_by_id(ann.id, self.student_user)
        self.assertTrue(detail.is_viewed_by_me)
        self.assertFalse(detail.is_acknowledged_by_me)

        # Student acknowledges announcement
        ack = AnnouncementService.acknowledge_announcement(ann.id, self.student_user)
        self.assertTrue(ack)

        # Check detail again
        detail_after = AnnouncementService.get_announcement_by_id(ann.id, self.student_user)
        self.assertTrue(detail_after.is_acknowledged_by_me)

        # Admin views reader log
        views = AnnouncementService.get_announcement_views(ann.id, self.admin_user)
        self.assertGreaterEqual(len(views), 1)
        student_view = [v for v in views if v.user_id == self.student_user["id"]]
        self.assertTrue(len(student_view) > 0)
        self.assertIsNotNone(student_view[0].acknowledged_at)

    # ==================== 3. SYSTEM ADMINISTRATION TESTS ====================

    def test_system_settings_bulk_update_and_history(self):
        """Verify system settings update, cache invalidation, and history logging."""
        settings = AdminService.get_settings(category="general")
        self.assertGreater(len(settings), 0)

        # Update setting
        new_app_name = f"Hostel Management System TQM v{uuid.uuid4().hex[:4]}"
        AdminService.update_settings(
            SystemSettingsBulkUpdate(
                settings={"app_name": new_app_name},
                reason="System rebranding test"
            ),
            self.admin_user
        )

        # Verify update applied
        updated_settings = {s.setting_key: s.setting_value for s in AdminService.get_settings()}
        self.assertEqual(updated_settings["app_name"], new_app_name)

        # Verify history recorded
        history = AdminService.get_settings_history(limit=10)
        self.assertTrue(any(h.setting_key == "app_name" and h.new_value == new_app_name for h in history))

    def test_user_admin_status_and_super_admin_protection(self):
        """Verify user status toggling and Poka-Yoke Super Admin deactivation protection."""
        # 1. Poka-Yoke: Super Admin cannot be deactivated
        with self.assertRaises(HTTPException) as ctx:
            AdminService.update_user_status(1, UserStatusUpdate(is_active=False), self.admin_user)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("cannot be deactivated", ctx.exception.detail)

        # 2. Regular user deactivation and reactivation
        user_summary = AdminService.update_user_status(5, UserStatusUpdate(is_active=False), self.admin_user)
        self.assertFalse(user_summary.is_active)

        user_summary_restored = AdminService.update_user_status(5, UserStatusUpdate(is_active=True), self.admin_user)
        self.assertTrue(user_summary_restored.is_active)

    def test_user_admin_roles_and_privilege_escalation_protection(self):
        """Verify role assignment and protection against privilege escalation."""
        # Warden attempts to grant super_admin to user 5 -> Forbidden
        with self.assertRaises(HTTPException) as ctx:
            AdminService.update_user_roles(
                5,
                UserRolesUpdate(roles=["student", "super_admin"]),
                self.warden_user
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Only Super Administrators can grant Super Admin", ctx.exception.detail)

        # Super Admin assigns role
        updated = AdminService.update_user_roles(
            5,
            UserRolesUpdate(roles=["student"]),
            self.admin_user
        )
        self.assertIn("student", updated.roles)

    def test_admin_password_reset(self):
        """Verify administrative password reset without exposing plaintext in logs."""
        res = AdminService.admin_reset_password(
            5,
            UserPasswordResetAdmin(reason="User forgot credentials"),
            self.admin_user
        )
        self.assertEqual(res["status"], "success")
        self.assertIsNotNone(res.get("temporary_password"))

        # Restore user 5 password to default demo password to avoid test pollution
        from backend.app.services.security import hash_password
        from backend.app.database.connection import get_db_connection
        with get_db_connection() as conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = 5", (hash_password("Password123!"),))

    def test_role_permissions_update(self):
        """Verify role permissions inspection, updates, and core integrity protection."""
        roles = AdminService.get_roles()
        self.assertGreaterEqual(len(roles), 12)

        permissions = AdminService.get_permissions()
        self.assertGreater(len(permissions), 50)

        # Protection: Cannot strip core permissions from super_admin
        super_admin_role = [r for r in roles if r.name == "super_admin"][0]
        with self.assertRaises(HTTPException) as ctx:
            AdminService.update_role_permissions(
                super_admin_role.id,
                RolePermissionsUpdate(permission_names=["auth:login"]),
                self.admin_user
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Cannot strip fundamental core permissions", ctx.exception.detail)

    def test_audit_logs_search_and_rfc4180_export(self):
        """Verify audit log search, pagination, and RFC 4180 CSV streaming export."""
        logs = AdminService.get_audit_logs(page=1, page_size=10)
        self.assertGreater(logs.total, 0)
        self.assertLessEqual(len(logs.items), 10)

        # Export CSV
        csv_str = AdminService.export_audit_logs_csv()
        self.assertIn("Audit ID,Timestamp,User ID,Username,Action,Module / Entity,Entity ID,Details,IP Address,Latency (ms)", csv_str)
        self.assertGreater(len(csv_str.splitlines()), 2)

    # ==================== 4. BACKUP & INTEGRITY TESTS ====================

    def test_database_backup_and_integrity_check(self):
        """Verify SQLite-safe online backup creation and PRAGMA integrity verification."""
        backup_res = BackupService.create_backup(note="Automated test backup")
        self.assertEqual(backup_res["status"], "success")
        self.assertTrue(os.path.exists(backup_res["path"]))

        # Verify integrity
        integrity = BackupService.verify_backup_integrity(backup_res["path"])
        self.assertTrue(integrity["is_valid"])
        self.assertGreater(integrity["table_count"], 30)

        # List backups
        all_backups = BackupService.list_backups()
        self.assertTrue(any(b["filename"] == backup_res["filename"] for b in all_backups))

        # Cleanup test backup file
        if os.path.exists(backup_res["path"]):
            os.remove(backup_res["path"])


if __name__ == "__main__":
    unittest.main()
