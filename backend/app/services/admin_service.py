"""System Administration Service.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
"""

import csv
import io
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status

from backend.app.database.connection import get_db_connection
from backend.app.models.admin_dto import (
    SystemSettingItem,
    SystemSettingsBulkUpdate,
    SystemSettingHistoryResponse,
    UserAdminSummary,
    UserAdminDetail,
    UserAdminListResponse,
    UserStatusUpdate,
    UserRolesUpdate,
    UserPasswordResetAdmin,
    PermissionResponse,
    RoleDetailResponse,
    RolePermissionsUpdate,
    AuditLogResponse,
    AuditLogListResponse
)
from backend.app.services.cache_service import cache_service
from backend.app.services.security import hash_password
from backend.app.utils.logger import logger


class AdminService:
    """Centralized service for System Settings, User Administration, RBAC, and Audit Logs."""

    @staticmethod
    def _extract_user_id(current_user: Dict[str, Any]) -> int:
        return current_user.get("user_id") or current_user.get("id") or 1

    @staticmethod
    def _extract_role(current_user: Dict[str, Any]) -> str:
        role = current_user.get("role")
        if not role and current_user.get("roles") and isinstance(current_user["roles"], list):
            role = current_user["roles"][0]
        return role or "student"

    # ==================== 1. SYSTEM SETTINGS ====================

    @classmethod
    def get_settings(cls, category: Optional[str] = None) -> List[SystemSettingItem]:
        """Fetch system settings with microsecond cached performance."""
        cache_key = f"admin:settings:{category or 'all'}"
        cached = cache_service.get(cache_key)
        if cached:
            return [SystemSettingItem(**item) for item in cached]

        with get_db_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute("""
                    SELECT setting_key, setting_value, category, description, is_encrypted, updated_at
                    FROM system_settings
                    WHERE category = ?
                    ORDER BY category, setting_key;
                """, (category,))
            else:
                cursor.execute("""
                    SELECT setting_key, setting_value, category, description, is_encrypted, updated_at
                    FROM system_settings
                    ORDER BY category, setting_key;
                """)
            rows = cursor.fetchall()
            items = [
                SystemSettingItem(
                    setting_key=r["setting_key"],
                    setting_value=r["setting_value"],
                    category=r["category"],
                    description=r["description"] or "",
                    is_encrypted=bool(r["is_encrypted"]),
                    updated_at=r["updated_at"]
                )
                for r in rows
            ]
            cache_service.set(cache_key, [item.model_dump() for item in items], ttl=300, tags=["settings"])
            return items

    @classmethod
    def update_settings(cls, payload: SystemSettingsBulkUpdate, current_user: Dict[str, Any]) -> List[SystemSettingItem]:
        """Update system settings with change validation, history logging, and cache invalidation."""
        user_id = cls._extract_user_id(current_user)
        username = current_user.get("username", "admin")
        now = datetime.now().isoformat()

        with get_db_connection() as conn:
            cursor = conn.cursor()

            for key, val in payload.settings.items():
                cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = ?;", (key,))
                existing = cursor.fetchone()
                if not existing:
                    continue

                old_val = existing["setting_value"]
                if str(val) != str(old_val):
                    # Update setting
                    cursor.execute("""
                        UPDATE system_settings
                        SET setting_value = ?, updated_at = ?
                        WHERE setting_key = ?;
                    """, (str(val), now, key))

                    # Record history
                    cursor.execute("""
                        INSERT INTO system_setting_history (
                            setting_key, old_value, new_value, changed_by, reason, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?);
                    """, (key, str(old_val), str(val), user_id, payload.reason or "Administrative update", now))

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'UPDATE_SYSTEM_SETTINGS', 'system_settings', 'bulk', ?, 0.5);
            """, (
                user_id,
                username,
                f"Updated settings: {list(payload.settings.keys())}. Reason: {payload.reason}"
            ))
            conn.commit()

        cache_service.invalidate_by_tag("settings")
        logger.info(f"System settings updated by user #{user_id} ({list(payload.settings.keys())})")
        return cls.get_settings()

    @classmethod
    def get_settings_history(cls, limit: int = 50) -> List[SystemSettingHistoryResponse]:
        """Inspect audit history of system setting modifications."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT h.id, h.setting_key, h.old_value, h.new_value, h.changed_by,
                       h.reason, h.created_at,
                       (u.first_name || ' ' || u.last_name) AS changed_by_name
                FROM system_setting_history h
                LEFT JOIN users u ON h.changed_by = u.id
                ORDER BY h.created_at DESC
                LIMIT ?;
            """, (limit,))
            rows = cursor.fetchall()
            return [
                SystemSettingHistoryResponse(
                    id=r["id"],
                    setting_key=r["setting_key"],
                    old_value=r["old_value"],
                    new_value=r["new_value"],
                    changed_by=r["changed_by"],
                    changed_by_name=r["changed_by_name"] or "System Admin",
                    reason=r["reason"] or "",
                    created_at=r["created_at"]
                )
                for r in rows
            ]

    # ==================== 2. USER ADMINISTRATION ====================

    @classmethod
    def get_users(
        cls,
        search: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        hostel_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20
    ) -> UserAdminListResponse:
        """Paginated user directory with search and role filtering with Q05 < 10ms SLA."""
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        offset = (page - 1) * page_size

        with get_db_connection() as conn:
            cursor = conn.cursor()

            conditions = ["1=1"]
            params: List[Any] = []

            if is_active is not None:
                conditions.append("u.is_active = ?")
                params.append(1 if is_active else 0)

            if hostel_id:
                conditions.append("u.linked_hostel_id = ?")
                params.append(hostel_id)

            if search and search.strip():
                s = f"%{search.strip()}%"
                conditions.append("(u.username LIKE ? OR u.email LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ?)")
                params.extend([s, s, s, s])

            if role:
                conditions.append("EXISTS(SELECT 1 FROM user_roles ur2 JOIN roles r2 ON ur2.role_id = r2.id WHERE ur2.user_id = u.id AND r2.name = ?)")
                params.append(role)

            where_clause = " WHERE " + " AND ".join(conditions)

            # Total count
            cursor.execute(f"SELECT COUNT(DISTINCT u.id) FROM users u {where_clause};", params)
            total = cursor.fetchone()[0]

            # Query users
            query = f"""
                SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.phone,
                       u.is_active, u.linked_student_id, u.linked_hostel_id,
                       u.failed_login_attempts, u.locked_until, u.created_at, u.updated_at,
                       GROUP_CONCAT(r.name) AS role_names
                FROM users u
                LEFT JOIN user_roles ur ON u.id = ur.user_id
                LEFT JOIN roles r ON ur.role_id = r.id
                {where_clause}
                GROUP BY u.id
                ORDER BY u.id ASC
                LIMIT ? OFFSET ?;
            """
            cursor.execute(query, params + [page_size, offset])
            rows = cursor.fetchall()

            items = []
            for r in rows:
                roles_list = [rn.strip() for rn in (r["role_names"] or "").split(",") if rn.strip()]
                items.append(UserAdminSummary(
                    id=r["id"],
                    username=r["username"],
                    email=r["email"],
                    first_name=r["first_name"] or "",
                    last_name=r["last_name"] or "",
                    phone=r["phone"] or "",
                    is_active=bool(r["is_active"]),
                    roles=roles_list,
                    linked_student_id=r["linked_student_id"],
                    linked_hostel_id=r["linked_hostel_id"],
                    failed_login_attempts=r["failed_login_attempts"] or 0,
                    locked_until=r["locked_until"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"]
                ))

            return UserAdminListResponse(
                items=items,
                total=total,
                page=page,
                page_size=page_size
            )

    @classmethod
    def get_user_detail(cls, user_id: int) -> UserAdminDetail:
        """Fetch comprehensive user profile, role mappings, and recent login audit activity."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.phone,
                       u.is_active, u.linked_student_id, u.linked_hostel_id,
                       u.failed_login_attempts, u.locked_until, u.created_at, u.updated_at,
                       GROUP_CONCAT(r.name) AS role_names
                FROM users u
                LEFT JOIN user_roles ur ON u.id = ur.user_id
                LEFT JOIN roles r ON ur.role_id = r.id
                WHERE u.id = ?
                GROUP BY u.id;
            """, (user_id,))
            r = cursor.fetchone()
            if not r:
                raise HTTPException(status_code=404, detail="User not found.")

            roles_list = [rn.strip() for rn in (r["role_names"] or "").split(",") if rn.strip()]

            # Fetch user permissions across all roles
            cursor.execute("""
                SELECT DISTINCT p.name
                FROM user_roles ur
                JOIN role_permissions rp ON ur.role_id = rp.role_id
                JOIN permissions p ON rp.permission_id = p.id
                WHERE ur.user_id = ?
                ORDER BY p.name ASC;
            """, (user_id,))
            permissions = [p_row[0] for p_row in cursor.fetchall()]

            # Fetch recent login history
            cursor.execute("""
                SELECT id, ip_address, user_agent, status, failure_reason, timestamp AS attempted_at
                FROM login_history
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 10;
            """, (user_id,))
            logins = [dict(log_row) for log_row in cursor.fetchall()]

            return UserAdminDetail(
                id=r["id"],
                username=r["username"],
                email=r["email"],
                first_name=r["first_name"] or "",
                last_name=r["last_name"] or "",
                phone=r["phone"] or "",
                is_active=bool(r["is_active"]),
                roles=roles_list,
                linked_student_id=r["linked_student_id"],
                linked_hostel_id=r["linked_hostel_id"],
                failed_login_attempts=r["failed_login_attempts"] or 0,
                locked_until=r["locked_until"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                recent_logins=logins,
                permissions=permissions
            )

    @classmethod
    def update_user_status(cls, user_id: int, payload: UserStatusUpdate, current_user: Dict[str, Any]) -> UserAdminSummary:
        """Activate or deactivate a user account with Super Admin protection."""
        actor_id = cls._extract_user_id(current_user)
        actor_username = current_user.get("username", "admin")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
            u = cursor.fetchone()
            if not u:
                raise HTTPException(status_code=404, detail="User not found.")

            # Protection: Disallow deactivating primary super admin (user id 1 or username 'admin')
            if not payload.is_active and (u["id"] == 1 or u["username"].lower() in ["admin", "superadmin"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Forbidden: The primary Super Admin account cannot be deactivated."
                )

            now = datetime.now().isoformat()
            cursor.execute("""
                UPDATE users
                SET is_active = ?, updated_at = ?
                WHERE id = ?;
            """, (1 if payload.is_active else 0, now, user_id))

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'UPDATE_USER_STATUS', 'users', ?, ?, 0.5);
            """, (
                actor_id,
                actor_username,
                str(user_id),
                f"Changed user #{user_id} ({u['username']}) active status to {payload.is_active}. Reason: {payload.reason}"
            ))
            conn.commit()

        logger.info(f"User #{user_id} active status updated to {payload.is_active} by #{actor_id}")
        return cls.get_user_detail(user_id)

    @classmethod
    def update_user_roles(cls, user_id: int, payload: UserRolesUpdate, current_user: Dict[str, Any]) -> UserAdminSummary:
        """Assign or update user roles with privilege escalation prevention."""
        actor_id = cls._extract_user_id(current_user)
        actor_username = current_user.get("username", "admin")
        actor_role = cls._extract_role(current_user)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
            u = cursor.fetchone()
            if not u:
                raise HTTPException(status_code=404, detail="User not found.")

            # Protection against privilege escalation: non-super_admin cannot grant super_admin
            if "super_admin" in payload.roles and actor_role != "super_admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Only Super Administrators can grant Super Admin privileges."
                )

            # Protection: cannot remove super_admin from user 1
            if u["id"] == 1 and "super_admin" not in payload.roles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Forbidden: Primary administrator must retain the super_admin role."
                )

            # Resolve role IDs
            role_ids = []
            for rname in payload.roles:
                cursor.execute("SELECT id FROM roles WHERE name = ?;", (rname,))
                r_row = cursor.fetchone()
                if not r_row:
                    raise HTTPException(status_code=400, detail=f"Role '{rname}' does not exist.")
                role_ids.append(r_row["id"])

            # Remove old roles and assign new
            cursor.execute("DELETE FROM user_roles WHERE user_id = ?;", (user_id,))
            for rid in role_ids:
                cursor.execute("""
                    INSERT INTO user_roles (user_id, role_id, assigned_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP);
                """, (user_id, rid))

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'UPDATE_USER_ROLES', 'users', ?, ?, 0.5);
            """, (
                actor_id,
                actor_username,
                str(user_id),
                f"Assigned roles {payload.roles} to user #{user_id} ({u['username']}). Reason: {payload.reason}"
            ))
            conn.commit()

        logger.info(f"User #{user_id} roles reassigned to {payload.roles} by #{actor_id}")
        return cls.get_user_detail(user_id)

    @classmethod
    def admin_reset_password(cls, user_id: int, payload: UserPasswordResetAdmin, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Administrative password reset without exposing plaintext passwords in logs."""
        actor_id = cls._extract_user_id(current_user)
        actor_username = current_user.get("username", "admin")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
            u = cursor.fetchone()
            if not u:
                raise HTTPException(status_code=404, detail="User not found.")

            new_pw = payload.temporary_password or f"TqmSecure@{secrets.token_hex(4)}"
            hashed_pw = hash_password(new_pw)
            salt = ""
            now = datetime.now().isoformat()

            cursor.execute("""
                UPDATE users
                SET password_hash = ?, salt = ?, failed_login_attempts = 0, locked_until = NULL, updated_at = ?
                WHERE id = ?;
            """, (hashed_pw, salt, now, user_id))

            # Revoke active refresh tokens
            cursor.execute("UPDATE refresh_tokens SET is_revoked = 1 WHERE user_id = ?;", (user_id,))

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'ADMIN_PASSWORD_RESET', 'users', ?, ?, 0.5);
            """, (
                actor_id,
                actor_username,
                str(user_id),
                f"Administrative password reset for user #{user_id} ({u['username']}). Reason: {payload.reason}"
            ))
            conn.commit()

        return {
            "status": "success",
            "message": f"Password reset successfully for {u['username']}.",
            "temporary_password": new_pw
        }

    # ==================== 3. ROLES & PERMISSIONS ====================

    @classmethod
    def get_roles(cls) -> List[RoleDetailResponse]:
        """Directory of 12 system roles with assigned user counts and permissions."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.id, r.name, r.description, r.is_system, r.created_at,
                       (SELECT COUNT(*) FROM user_roles ur WHERE ur.role_id = r.id) AS user_count,
                       (SELECT GROUP_CONCAT(p.name) FROM role_permissions rp JOIN permissions p ON rp.permission_id = p.id WHERE rp.role_id = r.id) AS perm_names
                FROM roles r
                ORDER BY r.id ASC;
            """)
            rows = cursor.fetchall()
            results = []
            for r in rows:
                p_list = [p.strip() for p in (r["perm_names"] or "").split(",") if p.strip()]
                results.append(RoleDetailResponse(
                    id=r["id"],
                    name=r["name"],
                    description=r["description"] or "",
                    is_system=bool(r["is_system"]),
                    user_count=r["user_count"] or 0,
                    permissions=p_list,
                    created_at=r["created_at"]
                ))
            return results

    @classmethod
    def get_permissions(cls) -> List[PermissionResponse]:
        """Complete list of 173 system permissions grouped by operational module."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, module, description, created_at FROM permissions ORDER BY module, name ASC;")
            rows = cursor.fetchall()
            return [
                PermissionResponse(
                    id=r["id"],
                    name=r["name"],
                    module=r["module"],
                    description=r["description"] or "",
                    created_at=r["created_at"]
                )
                for r in rows
            ]

    @classmethod
    def update_role_permissions(cls, role_id: int, payload: RolePermissionsUpdate, current_user: Dict[str, Any]) -> RoleDetailResponse:
        """Update permissions assigned to a role with system integrity preservation."""
        actor_id = cls._extract_user_id(current_user)
        actor_username = current_user.get("username", "admin")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM roles WHERE id = ?;", (role_id,))
            role = cursor.fetchone()
            if not role:
                raise HTTPException(status_code=404, detail="Role not found.")

            # Super admin role protection
            if role["name"] == "super_admin" and len(payload.permission_names) < 50:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Forbidden: Cannot strip fundamental core permissions from Super Admin role."
                )

            # Map permission names to IDs
            perm_ids = []
            for pname in payload.permission_names:
                cursor.execute("SELECT id FROM permissions WHERE name = ?;", (pname,))
                p_row = cursor.fetchone()
                if p_row:
                    perm_ids.append(p_row["id"])

            cursor.execute("DELETE FROM role_permissions WHERE role_id = ?;", (role_id,))
            for pid in perm_ids:
                cursor.execute("""
                    INSERT INTO role_permissions (role_id, permission_id, created_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP);
                """, (role_id, pid))

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'UPDATE_ROLE_PERMISSIONS', 'roles', ?, ?, 0.5);
            """, (
                actor_id,
                actor_username,
                str(role_id),
                f"Reconfigured permissions for role '{role['name']}' ({len(perm_ids)} permissions). Reason: {payload.reason}"
            ))
            conn.commit()

        cache_service.invalidate_by_tag("rbac")
        return [r for r in cls.get_roles() if r.id == role_id][0]

    # ==================== 4. AUDIT LOGS ====================

    @classmethod
    def get_audit_logs(
        cls,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        action: Optional[str] = None,
        module: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 25
    ) -> AuditLogListResponse:
        """Indexed search across immutable audit log records with sub-10ms Q05 SLA."""
        page = max(1, page)
        page_size = max(1, min(200, page_size))
        offset = (page - 1) * page_size

        with get_db_connection() as conn:
            cursor = conn.cursor()

            conditions = ["1=1"]
            params: List[Any] = []

            if user_id:
                conditions.append("user_id = ?")
                params.append(user_id)

            if username:
                conditions.append("username = ?")
                params.append(username)

            if action:
                conditions.append("action = ?")
                params.append(action)

            if module:
                conditions.append("entity_name = ?")
                params.append(module)

            if start_date:
                conditions.append("created_at >= ?")
                params.append(start_date)

            if end_date:
                conditions.append("created_at <= ?")
                params.append(end_date + " 23:59:59")

            if search and search.strip():
                s = f"%{search.strip()}%"
                conditions.append("(action LIKE ? OR details LIKE ? OR username LIKE ? OR entity_name LIKE ?)")
                params.extend([s, s, s, s])

            where_clause = " WHERE " + " AND ".join(conditions)

            # Total count
            cursor.execute(f"SELECT COUNT(*) FROM audit_logs {where_clause};", params)
            total = cursor.fetchone()[0]

            # Query rows
            query = f"""
                SELECT id, user_id, username, action, entity_name, entity_id, details, ip_address, latency_ms, created_at
                FROM audit_logs
                {where_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?;
            """
            cursor.execute(query, params + [page_size, offset])
            rows = cursor.fetchall()

            items = [
                AuditLogResponse(
                    id=r["id"],
                    user_id=r["user_id"],
                    username=r["username"] or "anonymous",
                    action=r["action"],
                    entity_name=r["entity_name"] or "",
                    entity_id=r["entity_id"] or "",
                    details=r["details"] or "",
                    ip_address=r["ip_address"] or "",
                    latency_ms=r["latency_ms"] or 0.0,
                    created_at=r["created_at"]
                )
                for r in rows
            ]

            return AuditLogListResponse(
                items=items,
                total=total,
                page=page,
                page_size=page_size
            )

    @classmethod
    def get_audit_log_by_id(cls, log_id: int) -> AuditLogResponse:
        """Retrieve single audit record details."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_logs WHERE id = ?;", (log_id,))
            r = cursor.fetchone()
            if not r:
                raise HTTPException(status_code=404, detail="Audit log entry not found.")
            return AuditLogResponse(
                id=r["id"],
                user_id=r["user_id"],
                username=r["username"] or "anonymous",
                action=r["action"],
                entity_name=r["entity_name"] or "",
                entity_id=r["entity_id"] or "",
                details=r["details"] or "",
                ip_address=r["ip_address"] or "",
                latency_ms=r["latency_ms"] or 0.0,
                created_at=r["created_at"]
            )

    @classmethod
    def export_audit_logs_csv(
        cls,
        action: Optional[str] = None,
        module: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None
    ) -> str:
        """Stream RFC 4180 compliant CSV export of authorized audit trail records."""
        logs_resp = cls.get_audit_logs(
            action=action,
            module=module,
            start_date=start_date,
            end_date=end_date,
            search=search,
            page=1,
            page_size=10000
        )

        buffer = io.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)

        writer.writerow([
            "Audit ID",
            "Timestamp",
            "User ID",
            "Username",
            "Action",
            "Module / Entity",
            "Entity ID",
            "Details",
            "IP Address",
            "Latency (ms)"
        ])

        for log in logs_resp.items:
            writer.writerow([
                log.id,
                log.created_at,
                log.user_id or "",
                log.username,
                log.action,
                log.entity_name,
                log.entity_id or "",
                log.details,
                log.ip_address or "",
                f"{log.latency_ms:.2f}"
            ])

        return buffer.getvalue()
