"""Authentication and Role-Based Access Control (RBAC) Service.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import hashlib
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException, status
from backend.app.config import settings
from backend.app.database.connection import get_db_connection
from backend.app.services.rbac_data import normalize_role_name, ROLE_METADATA
from backend.app.services.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token
)
from backend.app.utils.logger import logger

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class AuthService:
    """Enterprise authentication service with token rotation, lockout protection, and RBAC."""

    @staticmethod
    def get_user_roles_and_permissions(conn: sqlite3.Connection, user_id: int) -> Tuple[List[str], Set[str]]:
        """Retrieve all role names and resolved permissions for a user."""
        cursor = conn.cursor()

        # Fetch roles
        cursor.execute("""
            SELECT r.name FROM roles r
            JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = ?;
        """, (user_id,))
        roles = [r[0] for r in cursor.fetchall()]

        # Fetch distinct permissions across all user roles
        cursor.execute("""
            SELECT DISTINCT p.name FROM permissions p
            JOIN role_permissions rp ON p.id = rp.permission_id
            JOIN user_roles ur ON rp.role_id = ur.role_id
            WHERE ur.user_id = ?;
        """, (user_id,))
        permissions = {r[0] for r in cursor.fetchall()}

        return roles, permissions

    @classmethod
    def authenticate_user(
        cls,
        username_or_email: str,
        password: str,
        ip_address: str = "",
        user_agent: str = "",
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        """Authenticate user with failed attempt lockout and audit logging."""
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            query = """
                SELECT id, username, email, password_hash, first_name, last_name, phone,
                       is_active, failed_login_attempts, locked_until, linked_student_id, linked_hostel_id, staff_id
                FROM users
                WHERE username = ? OR email = ?;
            """
            cursor.execute(query, (username_or_email.strip(), username_or_email.strip().lower()))
            user = cursor.fetchone()

            now = datetime.now(timezone.utc)

            if not user:
                # Log failed attempt for unknown user
                cls._log_login(conn, None, username_or_email, ip_address, user_agent, "FAILED", "User not found")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

            # Check if account is deactivated or pending registration approval
            if not user["is_active"]:
                cursor.execute("""
                    SELECT status, requested_role, admin_warden_approval_status, student_approval_status
                    FROM registration_requests
                    WHERE user_id = ?
                    ORDER BY id DESC LIMIT 1;
                """, (user["id"],))
                reg_req = cursor.fetchone()
                if reg_req and reg_req["status"] == "Pending":
                    r_role = reg_req["requested_role"]
                    if r_role == "parent_guardian":
                        if reg_req["student_approval_status"] != "Approved":
                            detail = "Your parent registration is awaiting confirmation by your child. Once verified by your child and approved by the Hostel Warden/Admin, your account will be active."
                        else:
                            detail = "Your child has verified your parent request! Your account is awaiting final approval by the Hostel Warden or Administrator."
                    elif r_role in ("staff", "maintenance_staff", "warden", "security_guard", "mess_manager", "accountant"):
                        detail = "Your staff registration is pending approval by the Administrator. You will be able to log in once approved."
                    else:
                        detail = "Your student registration is pending approval by the Hostel Warden or Administrator. You will be able to log in once approved."
                    cls._log_login(conn, user["id"], username_or_email, ip_address, user_agent, "BLOCKED", "Registration pending approval")
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
                elif reg_req and reg_req["status"] == "Rejected":
                    cls._log_login(conn, user["id"], username_or_email, ip_address, user_agent, "BLOCKED", "Registration rejected")
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your registration request was not approved. Contact hostel administration.")

                cls._log_login(conn, user["id"], username_or_email, ip_address, user_agent, "BLOCKED", "Account deactivated")
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated. Contact administration.")

            # Check account lockout
            if user["locked_until"]:
                locked_until_dt = datetime.fromisoformat(user["locked_until"].replace("Z", "+00:00")) if isinstance(user["locked_until"], str) else user["locked_until"]
                if locked_until_dt.tzinfo is None:
                    locked_until_dt = locked_until_dt.replace(tzinfo=timezone.utc)
                if now < locked_until_dt:
                    remaining_mins = int((locked_until_dt - now).total_seconds() // 60) + 1
                    cls._log_login(conn, user["id"], username_or_email, ip_address, user_agent, "BLOCKED", "Account temporarily locked")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Account is temporarily locked due to excessive failed attempts. Try again in {remaining_mins} minutes."
                    )

            # Verify password
            if not verify_password(password, user["password_hash"]):
                new_failed = user["failed_login_attempts"] + 1
                lock_until_str = None
                if new_failed >= MAX_FAILED_ATTEMPTS:
                    lock_time = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                    lock_until_str = lock_time.isoformat()
                    logger.warning(f"User {user['username']} locked until {lock_until_str} after {new_failed} failed attempts.")

                cursor.execute(
                    "UPDATE users SET failed_login_attempts = ?, locked_until = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                    (new_failed, lock_until_str, user["id"])
                )
                conn.commit()

                cls._log_login(conn, user["id"], username_or_email, ip_address, user_agent, "FAILED", f"Invalid password (attempt {new_failed})")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

            # Successful login: reset failed attempts
            cursor.execute(
                "UPDATE users SET failed_login_attempts = 0, locked_until = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (user["id"],)
            )
            conn.commit()

            cls._log_login(conn, user["id"], username_or_email, ip_address, user_agent, "SUCCESS", "")

            roles, permissions = cls.get_user_roles_and_permissions(conn, user["id"])

            # Resolve unique student_id if student
            resolved_student_id = None
            if user["linked_student_id"]:
                cursor.execute("SELECT student_id FROM students WHERE id = ?;", (user["linked_student_id"],))
                st_row = cursor.fetchone()
                if st_row:
                    resolved_student_id = st_row["student_id"] if isinstance(st_row, dict) or hasattr(st_row, 'keys') else st_row[0]

            # Resolve unique staff_id if staff role
            staff_roles = {'super_admin', 'hostel_admin', 'warden', 'assistant_warden', 'accountant', 'mess_manager', 'maintenance_staff', 'security_guard', 'admission_officer', 'auditor'}
            staff_id_val = user["staff_id"]
            if not staff_id_val and any(r in roles for r in staff_roles):
                staff_id_val = f"STF-{user['id']:04d}"
                cursor.execute("UPDATE users SET staff_id = ? WHERE id = ?;", (staff_id_val, user["id"]))
                conn.commit()

            user_gender = user["gender"] if "gender" in user.keys() and user["gender"] else "Male"
            return {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "phone": user["phone"] or "",
                "gender": user_gender,
                "roles": roles,
                "permissions": list(permissions),
                "linked_student_id": user["linked_student_id"],
                "linked_hostel_id": user["linked_hostel_id"],
                "staff_id": staff_id_val,
                "student_id": resolved_student_id
            }
        finally:
            if should_close:
                conn.close()

    @staticmethod
    def _log_login(
        conn: sqlite3.Connection,
        user_id: Optional[int],
        username_attempted: str,
        ip: str,
        ua: str,
        status_val: str,
        reason: str
    ) -> None:
        """Internal helper to write immutable login history."""
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO login_history (user_id, username_or_email_attempted, ip_address, user_agent, status, failure_reason)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (user_id, username_attempted, ip, ua, status_val, reason))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to log login audit: {e}")

    @classmethod
    def issue_token_pair(
        cls,
        user: Dict[str, Any],
        ip_address: str = "",
        device_info: str = "",
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        """Issue JWT access token and store rotated refresh token."""
        active_role = user.get("active_role")
        if not active_role or active_role not in user["roles"]:
            active_role = user["roles"][0] if user["roles"] else "student"
        user["active_role"] = active_role

        norm_role = normalize_role_name(active_role)
        meta = ROLE_METADATA.get(norm_role, {})
        user["role_code"] = meta.get("code", norm_role.upper())
        user["stakeholder_category"] = meta.get("category", "Operational / Student Life")
        user["can_switch_roles"] = len(user.get("roles", [])) > 1
        if "user_scopes" not in user:
            user["user_scopes"] = []

        token_payload = {
            "sub": user["username"],
            "user_id": user["id"],
            "roles": user["roles"],
            "active_role": active_role,
            "linked_student_id": user.get("linked_student_id"),
            "linked_hostel_id": user.get("linked_hostel_id")
        }
        access_token = create_access_token(token_payload)

        raw_refresh, token_hash, expires_at = create_refresh_token(user["id"])

        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO refresh_tokens (user_id, token_hash, device_info, ip_address, expires_at)
                VALUES (?, ?, ?, ?, ?);
            """, (user["id"], token_hash, device_info, ip_address, expires_at.isoformat()))
            conn.commit()
        finally:
            if should_close:
                conn.close()

        return {
            "access_token": access_token,
            "refresh_token": raw_refresh,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
            "user": user
        }

    @classmethod
    def rotate_refresh_token(
        cls,
        raw_refresh_token: str,
        ip_address: str = "",
        device_info: str = "",
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        """Perform cryptographic refresh token rotation and issue new token pair."""
        token_hash = hashlib.sha256(raw_refresh_token.encode("utf-8")).hexdigest()

        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, is_revoked, expires_at
                FROM refresh_tokens
                WHERE token_hash = ?;
            """, (token_hash,))
            token_row = cursor.fetchone()

            if not token_row:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

            # Reuse detection: If token is already revoked, potential theft! Revoke all tokens for user.
            if token_row["is_revoked"]:
                cursor.execute("UPDATE refresh_tokens SET is_revoked = 1 WHERE user_id = ?;", (token_row["user_id"],))
                conn.commit()
                logger.warning(f"Reused refresh token detected for user {token_row['user_id']}. Revoking all sessions!")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token compromised. Please re-authenticate.")

            # Expiration check
            exp_dt = datetime.fromisoformat(token_row["expires_at"].replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp_dt:
                cursor.execute("UPDATE refresh_tokens SET is_revoked = 1 WHERE id = ?;", (token_row["id"],))
                conn.commit()
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired.")

            # Load user details
            cursor.execute("SELECT id, username, email, first_name, last_name, phone, is_active, linked_student_id, linked_hostel_id, staff_id FROM users WHERE id = ?;", (token_row["user_id"],))
            user = cursor.fetchone()
            if not user or not user["is_active"]:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account inactive.")

            # Generate new pair
            roles, permissions = cls.get_user_roles_and_permissions(conn, user["id"])
            # Resolve unique student_id if student
            resolved_student_id = None
            if user["linked_student_id"]:
                cursor.execute("SELECT student_id FROM students WHERE id = ?;", (user["linked_student_id"],))
                st_row = cursor.fetchone()
                if st_row:
                    resolved_student_id = st_row["student_id"] if isinstance(st_row, dict) or hasattr(st_row, 'keys') else st_row[0]

            staff_roles = {'super_admin', 'hostel_admin', 'warden', 'assistant_warden', 'accountant', 'mess_manager', 'maintenance_staff', 'security_guard', 'admission_officer', 'auditor'}
            staff_id_val = user["staff_id"] or (f"STF-{user['id']:04d}" if any(r in roles for r in staff_roles) else None)

            user_dict = {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "phone": user["phone"] or "",
                "roles": roles,
                "permissions": list(permissions),
                "linked_student_id": user["linked_student_id"],
                "linked_hostel_id": user["linked_hostel_id"],
                "staff_id": staff_id_val,
                "student_id": resolved_student_id
            }

            raw_new_refresh, new_token_hash, new_expires_at = create_refresh_token(user["id"])
            access_token = create_access_token({
                "sub": user["username"],
                "user_id": user["id"],
                "roles": roles,
                "linked_student_id": user["linked_student_id"],
                "linked_hostel_id": user["linked_hostel_id"]
            })

            # Revoke old token and record replacement
            cursor.execute("""
                UPDATE refresh_tokens
                SET is_revoked = 1, replaced_by_token_hash = ?
                WHERE id = ?;
            """, (new_token_hash, token_row["id"]))

            # Insert new refresh token
            cursor.execute("""
                INSERT INTO refresh_tokens (user_id, token_hash, device_info, ip_address, expires_at)
                VALUES (?, ?, ?, ?, ?);
            """, (user["id"], new_token_hash, device_info, ip_address, new_expires_at.isoformat()))

            conn.commit()

            return {
                "access_token": access_token,
                "refresh_token": raw_new_refresh,
                "token_type": "bearer",
                "expires_in": settings.access_token_expire_minutes * 60,
                "user": user_dict
            }
        finally:
            if should_close:
                conn.close()

    @classmethod
    def revoke_refresh_token(cls, raw_refresh_token: str, conn: Optional[sqlite3.Connection] = None) -> bool:
        """Revoke a single refresh token during logout."""
        token_hash = hashlib.sha256(raw_refresh_token.encode("utf-8")).hexdigest()
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE refresh_tokens SET is_revoked = 1 WHERE token_hash = ?;", (token_hash,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if should_close:
                conn.close()

    @classmethod
    def get_authorized_hostels(cls, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
        """Retrieve all active hostels with real-time warden capacity and availability."""
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT h.id, h.name, h.code, h.hostel_type, h.address, h.contact_phone, h.contact_email
                FROM hostels h
                WHERE h.is_active = 1
                ORDER BY h.id ASC;
            """)
            hostels = [dict(r) for r in cursor.fetchall()]

            for h in hostels:
                hid = h["id"]
                # Count active assigned wardens
                cursor.execute("""
                    SELECT COUNT(DISTINCT u.id)
                    FROM users u
                    JOIN user_roles ur ON u.id = ur.user_id
                    JOIN roles r ON ur.role_id = r.id
                    WHERE r.name IN ('warden', 'assistant_warden')
                      AND u.linked_hostel_id = ?
                      AND u.is_active = 1;
                """, (hid,))
                active_wardens = cursor.fetchone()[0]

                # Count pending warden requests
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM registration_requests
                    WHERE (requested_role IN ('warden', 'assistant_warden') OR specialization IN ('warden', 'hostel_warden'))
                      AND hostel_id = ?
                      AND status = 'Pending';
                """, (hid,))
                pending_wardens = cursor.fetchone()[0]

                h["warden_count"] = active_wardens
                h["pending_wardens"] = pending_wardens
                h["max_wardens"] = 2
                h["is_full"] = (active_wardens + pending_wardens) >= 2
                h["available_for_warden"] = (active_wardens + pending_wardens) < 2

            return hostels
        finally:
            if should_close:
                conn.close()

    @classmethod
    def change_user_password(
        cls,
        user_id: int,
        old_password: str,
        new_password: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> bool:
        """Change password, hash with bcrypt, and revoke all active refresh tokens."""
        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")

        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM users WHERE id = ?;", (user_id,))
            row = cursor.fetchone()
            if not row or not verify_password(old_password, row["password_hash"]):
                raise HTTPException(status_code=400, detail="Current password incorrect.")

            new_hash = hash_password(new_password)
            cursor.execute("UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (new_hash, user_id))

            # Revoke all active sessions
            cursor.execute("UPDATE refresh_tokens SET is_revoked = 1 WHERE user_id = ?;", (user_id,))
            conn.commit()
            return True
        finally:
            if should_close:
                conn.close()

    @classmethod
    def initiate_password_reset(cls, email: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
        """Create a cryptographically secure, single-use password reset token with rate limiting."""
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            clean_email = email.strip().lower()
            cursor.execute("SELECT id, username FROM users WHERE email = ? AND is_active = 1;", (clean_email,))
            user = cursor.fetchone()

            raw_token = None
            if user:
                # Rate-limiting: maximum 3 password reset requests per 15 minutes per user
                cursor.execute("""
                    SELECT COUNT(*) FROM password_resets
                    WHERE user_id = ? AND created_at > datetime('now', '-15 minutes');
                """, (user["id"],))
                recent_count = cursor.fetchone()[0]
                if recent_count >= 3:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many password reset requests. Please wait 15 minutes before requesting another reset."
                    )

                # Invalidate previous unused reset tokens for this user
                cursor.execute("""
                    UPDATE password_resets
                    SET is_used = 1
                    WHERE user_id = ? AND is_used = 0;
                """, (user["id"],))

                # Cryptographically secure random token (256-bit entropy)
                raw_token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

                cursor.execute("""
                    INSERT INTO password_resets (user_id, reset_token_hash, expires_at)
                    VALUES (?, ?, ?);
                """, (user["id"], token_hash, expires_at.isoformat()))
                conn.commit()
                logger.info(f"Secure password reset initiated for user #{user['id']} ({user['username']})")

            # Always return a generic success message to prevent user enumeration
            generic_message = "If an account with that email exists, password reset instructions have been generated."
            return {
                "success": True,
                "message": generic_message,
                "dev_token": raw_token if (settings.app_env != "production" and settings.debug) else None
            }
        finally:
            if should_close:
                conn.close()

    @classmethod
    def complete_password_reset(
        cls,
        raw_token: str,
        new_password: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> bool:
        """Complete password reset using valid unexpired token."""
        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, is_used, expires_at
                FROM password_resets
                WHERE reset_token_hash = ?;
            """, (token_hash,))
            row = cursor.fetchone()
            if not row or row["is_used"]:
                raise HTTPException(status_code=400, detail="Invalid or already used reset token.")

            exp_dt = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp_dt:
                raise HTTPException(status_code=400, detail="Reset token has expired.")

            new_hash = hash_password(new_password)
            cursor.execute("UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (new_hash, row["user_id"]))
            cursor.execute("UPDATE password_resets SET is_used = 1 WHERE id = ?;", (row["id"],))
            cursor.execute("UPDATE refresh_tokens SET is_revoked = 1 WHERE user_id = ?;", (row["user_id"],))
            conn.commit()
            return True
        finally:
            if should_close:
                conn.close()

    @classmethod
    def switch_user_role(
        cls,
        user_id: int,
        target_role: str,
        ip_address: str = "",
        user_agent: str = ""
    ) -> Dict[str, Any]:
        """Validate and switch active role for multi-role accounts with audit logging."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, is_active FROM users WHERE id = ?;", (user_id,))
            user_row = cursor.fetchone()
            if not user_row or not user_row["is_active"]:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found or inactive.")

            roles, all_permissions = cls.get_user_roles_and_permissions(conn, user_id)
            if len(roles) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{target_role}' is not assigned to this account. Role switching is disabled for single-role accounts."
                )

            norm_target = normalize_role_name(target_role)
            user_norm_roles = [normalize_role_name(r) for r in roles]

            canonical_target = None
            if target_role in roles:
                canonical_target = target_role
            elif norm_target in roles:
                canonical_target = norm_target
            elif norm_target in user_norm_roles:
                for r in roles:
                    if normalize_role_name(r) == norm_target:
                        canonical_target = r
                        break

            if not canonical_target:
                try:
                    cursor.execute("""
                        INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, ip_address, latency_ms)
                        VALUES (?, ?, 'UNAUTHORIZED_ROLE_SWITCH_ATTEMPT', 'user_session', ?, ?, ?, 0.0);
                    """, (user_id, user_row["username"], str(user_id), f"Attempted switch to unauthorized role '{target_role}'", ip_address))
                    conn.commit()
                except Exception:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Unauthorized role switch: Role '{target_role}' is not assigned to your account."
                )

            # Calculate permissions specifically associated with the target active role
            cursor.execute("""
                SELECT DISTINCT p.name
                FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                JOIN roles r ON rp.role_id = r.id
                WHERE r.name = ?;
            """, (canonical_target,))
            target_permissions = [row[0] for row in cursor.fetchall()]

            # Fetch canonical role code
            cursor.execute("SELECT code FROM roles WHERE name = ?;", (canonical_target,))
            r_code_row = cursor.fetchone()
            role_code = (r_code_row["code"] if (r_code_row and r_code_row["code"])
                         else ROLE_METADATA.get(canonical_target, {}).get("code", canonical_target.upper()))

            # Issue new token with updated active_role
            token_payload = {
                "sub": user_row["username"],
                "user_id": user_id,
                "roles": roles,
                "active_role": canonical_target,
                "role_code": role_code
            }
            new_access_token = create_access_token(token_payload)

            # Record audit event
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, ip_address, latency_ms)
                VALUES (?, ?, 'ROLE_SWITCH', 'user_session', ?, ?, ?, 0.0);
            """, (user_id, user_row["username"], str(user_id), f"Switched active role to {canonical_target} ({role_code})", ip_address))
            conn.commit()

            return {
                "success": True,
                "active_role": canonical_target,
                "role_code": role_code,
                "access_token": new_access_token,
                "permissions": target_permissions,
                "message": f"Successfully switched active context to {canonical_target}."
            }
        finally:
            conn.close()

    @classmethod
    def register_user(
        cls,
        payload: Any,
        ip_address: str = "",
        user_agent: str = "",
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        """Register a new user (Student, Staff, or Parent), issue token pair, and create linked profiles."""
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            uname = payload.username.strip().lower()
            email = payload.email.strip().lower()
            first_name = payload.first_name.strip()
            last_name = payload.last_name.strip()
            phone = (payload.phone or "").strip()

            # Poka-Yoke Input Validation (Mistake-Proofing)
            if not email or "@" not in email or not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid email address: must contain '@' and a valid domain (e.g. name@univ.edu)."
                )

            if phone:
                if not re.match(r"^\d+$", phone):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid phone number: only digits (0-9) are allowed. Letters and special characters are not permitted."
                    )
                if len(phone) != 10:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Phone number must be exactly 10 digits. Provided: {len(phone)} digits."
                    )

            if not re.match(r"^[a-zA-Z\s'-]{1,50}$", first_name) or not re.match(r"^[a-zA-Z\s'-]{1,50}$", last_name):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Names must contain only alphabetic characters, spaces, or hyphens."
                )

            if not re.match(r"^[a-zA-Z0-9_.-]{3,30}$", uname):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username must be 3-30 characters containing only letters, numbers, hyphens, or underscores."
                )

            # Disallow administrative role self-registration
            requested_role = (payload.role or "student").strip().lower()
            if requested_role in ("super_admin", "admin", "hostel_admin", "auditor"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Administrative accounts cannot be self-registered. Contact system administration."
                )

            # Map generic staff roles into specialist staff categories
            if requested_role in ("staff", "staff_member"):
                spec = (payload.specialization or "").strip().lower()
                cat_req = (getattr(payload, "category", None) or "").strip().lower()
                if any(k in spec or k in cat_req for k in ("warden", "hostel_warden")):
                    target_role = "warden"
                elif any(k in spec or k in cat_req for k in ("mess", "chef", "cook", "kitchen", "dining")):
                    target_role = "mess_manager"
                elif any(k in spec or k in cat_req for k in ("security", "guard", "gate")):
                    target_role = "security_guard"
                elif any(k in spec or k in cat_req for k in ("account", "finance", "billing")):
                    target_role = "accountant"
                else:
                    target_role = "maintenance_staff"
            elif requested_role in ("student", "parent_guardian", "warden", "assistant_warden"):
                target_role = requested_role
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid registration role '{requested_role}'. Allowed roles are student, staff, parent_guardian, warden, assistant_warden."
                )

            # Check if username already exists in users or pending registrations
            # Poka-Yoke: Hostel selection and maximum 2 wardens constraint
            assigned_hostel_id = getattr(payload, "hostel_id", None)
            if requested_role in ("warden", "assistant_warden"):
                if not assigned_hostel_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Hostel selection is mandatory for warden registration."
                    )
            if assigned_hostel_id:
                    cursor.execute("SELECT id, name FROM hostels WHERE id = ? AND is_active = 1;", (assigned_hostel_id,))
                    h_target = cursor.fetchone()
                    if not h_target:
                        raise HTTPException(status_code=400, detail="Selected hostel is invalid or inactive.")
                    h_target_name = h_target["name"]

                    cursor.execute("""
                        SELECT COUNT(DISTINCT u.id)
                        FROM users u
                        JOIN user_roles ur ON u.id = ur.user_id
                        JOIN roles r ON ur.role_id = r.id
                        WHERE r.name IN ('warden', 'assistant_warden')
                          AND u.linked_hostel_id = ?
                          AND u.is_active = 1;
                    """, (assigned_hostel_id,))
                    active_w_count = cursor.fetchone()[0]

                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM registration_requests
                        WHERE (requested_role IN ('warden', 'assistant_warden') OR specialization IN ('warden', 'hostel_warden'))
                          AND hostel_id = ?
                          AND status = 'Pending';
                    """, (assigned_hostel_id,))
                    pend_w_count = cursor.fetchone()[0]

                    if active_w_count + pend_w_count >= 2:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Not Required: Hostel '{h_target_name}' has reached its institutional maximum quota of 2 hostel wardens ({active_w_count} active, {pend_w_count} pending). Warden capacity is full."
                        )

            cursor.execute("SELECT id FROM users WHERE username = ?;", (uname,))
            if cursor.fetchone():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already taken.")
            cursor.execute("SELECT id FROM registration_requests WHERE username = ? AND status = 'Pending';", (uname,))
            if cursor.fetchone():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A registration request with this username is already pending approval.")

            # Check if email already exists in users or pending registrations across ALL roles
            cursor.execute("SELECT id FROM users WHERE email = ?;", (email,))
            if cursor.fetchone():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This email address is already registered with an existing account.")
            cursor.execute("SELECT id FROM registration_requests WHERE email = ? AND status = 'Pending';", (email,))
            if cursor.fetchone():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A registration request with this email address is already pending approval.")

            # Check if phone number already exists in users or pending registrations across ALL roles
            if phone:
                cursor.execute("SELECT id FROM users WHERE phone = ?;", (phone,))
                if cursor.fetchone():
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This phone number is already registered with an existing account.")
                cursor.execute("SELECT id FROM registration_requests WHERE phone = ? AND status = 'Pending';", (phone,))
                if cursor.fetchone():
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A registration request with this phone number is already pending approval.")

            # If Parent: Resolve Child Student Records (Multi-ward support)
            linked_student_id = None
            child_info = None
            resolved_children = []
            if target_role == "parent_guardian":
                child_idents = []
                multi_ident = getattr(payload, 'child_identifiers', None)
                single_ident = getattr(payload, 'child_identifier', None)
                if multi_ident:
                    if isinstance(multi_ident, list):
                        child_idents.extend([str(x).strip() for x in multi_ident if str(x).strip()])
                    elif isinstance(multi_ident, str):
                        child_idents.extend([x.strip() for x in re.split(r'[,;]+', multi_ident) if x.strip()])
                elif single_ident:
                    child_idents.extend([x.strip() for x in re.split(r'[,;]+', str(single_ident)) if x.strip()])

                if not child_idents:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Child Roll Number or University Email is required for Parent / Guardian registration."
                    )

                for c_ident in child_idents:
                    cursor.execute("""
                        SELECT s.id, s.student_id, s.first_name, s.last_name, s.user_id, s.email
                        FROM students s
                        WHERE s.student_id = ? OR LOWER(s.email) = ?;
                    """, (c_ident, c_ident.lower()))
                    c_row = cursor.fetchone()
                    if not c_row:
                        cursor.execute("""
                            SELECT s.id, s.student_id, s.first_name, s.last_name, s.user_id, s.email
                            FROM students s
                            JOIN users u ON s.user_id = u.id
                            WHERE LOWER(u.username) = ?;
                        """, (c_ident.lower(),))
                        c_row = cursor.fetchone()
                    if not c_row:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No enrolled student found matching identifier '{c_ident}'. Please check your child's roll number or email."
                        )
                    resolved_children.append(c_row)

                child_info = resolved_children[0]
                linked_student_id = child_info["id"]

            # Hash password
            pwd_hash = hash_password(payload.password)

            gender_val = payload.gender if payload.gender in ("Male", "Female", "Other") else "Male"

            # Create User record in INACTIVE state awaiting approval
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, salt, first_name, last_name, phone, is_active, linked_student_id, gender)
                VALUES (?, ?, ?, '', ?, ?, ?, 0, ?, ?);
            """, (uname, email, pwd_hash, first_name, last_name, phone, linked_student_id if target_role == "parent_guardian" else None, gender_val))
            user_id = cursor.lastrowid

            # Resolve Role ID
            cursor.execute("SELECT id FROM roles WHERE name = ?;", (target_role,))
            role_row = cursor.fetchone()
            if not role_row:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Requested role '{target_role}' does not exist in system roles."
                )
            role_id = role_row["id"] if isinstance(role_row, sqlite3.Row) else role_row[0]

            # Assign Role in user_roles
            cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?);", (user_id, role_id))

            # Unique Staff ID generation and profile creation for staff members
            assigned_staff_id = None
            if target_role not in ("student", "parent_guardian"):
                assigned_staff_id = f"STF-{user_id:04d}"
                cursor.execute("SELECT id FROM users WHERE staff_id = ?;", (assigned_staff_id,))
                if cursor.fetchone():
                    assigned_staff_id = f"STF-{user_id:04d}-{uuid.uuid4().hex[:4].upper()}"
                cursor.execute("UPDATE users SET staff_id = ? WHERE id = ?;", (assigned_staff_id, user_id))

                # Insert into staff_profiles (Migration 017)
                emp_id = getattr(payload, "employee_id", None) or assigned_staff_id
                cat_val = getattr(payload, "category", None) or (
                    "Warden" if target_role in ("warden", "assistant_warden")
                    else "Maintenance" if target_role == "maintenance_staff"
                    else "Mess" if target_role == "mess_manager"
                    else "Security" if target_role == "security_guard"
                    else "Accounts" if target_role == "accountant"
                    else "Staff"
                )
                desig_val = getattr(payload, "designation", None) or target_role.replace("_", " ").title()
                dept_val = getattr(payload, "department", None) or cat_val
                spec_val = getattr(payload, "specialization", None) or ""
                emp_type = getattr(payload, "employment_type", None) or "Full-Time"
                doj = getattr(payload, "date_of_joining", None) or datetime.now().strftime("%Y-%m-%d")
                loc_val = getattr(payload, "assigned_location", None) or getattr(payload, "work_location", None) or (f"Hostel {assigned_hostel_id}" if assigned_hostel_id else "Campus")
                p_addr = getattr(payload, "permanent_address", None)
                c_addr = getattr(payload, "current_address", None)
                c_city = getattr(payload, "city", None)
                c_state = getattr(payload, "state", None)
                c_post = getattr(payload, "postal_code", None)
                c_country = getattr(payload, "country", None) or "India"
                emg_name = getattr(payload, "emergency_contact_name", None) or ""
                emg_phone = getattr(payload, "emergency_contact_phone", None) or ""

                cursor.execute("""
                    INSERT OR REPLACE INTO staff_profiles (
                        user_id, employee_id, category, designation, department, specialization,
                        employment_type, date_of_joining, assigned_location,
                        permanent_address, current_address, city, state, postal_code, country,
                        emergency_contact_name, emergency_contact_phone
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    user_id, emp_id, cat_val, desig_val, dept_val, spec_val,
                    emp_type, doj, loc_val, p_addr, c_addr, c_city, c_state, c_post, c_country,
                    emg_name, emg_phone
                ))

            # If Student: create linked student record with unique student_id and status='Pending'
            if target_role == "student":
                enrollment = (payload.enrollment_no or "").strip()
                if enrollment:
                    cursor.execute("SELECT id FROM students WHERE student_id = ?;", (enrollment,))
                    if cursor.fetchone():
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Student ID / Roll No '{enrollment}' is already registered to another student.")
                    cursor.execute("SELECT id FROM registration_requests WHERE student_roll_no = ? AND status = 'Pending';", (enrollment,))
                    if cursor.fetchone():
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A registration request with Student ID '{enrollment}' is already pending approval.")
                else:
                    enrollment = f"STU-{datetime.now().strftime('%Y%m')}-{user_id:04d}"
                    cursor.execute("SELECT id FROM students WHERE student_id = ?;", (enrollment,))
                    if cursor.fetchone():
                        enrollment = f"STU-{datetime.now().strftime('%Y%m')}-{user_id:04d}-{uuid.uuid4().hex[:4].upper()}"

                gender = payload.gender if payload.gender in ("Male", "Female", "Other") else "Male"
                branch = (payload.branch or "General").strip()
                acad_year = getattr(payload, "academic_year", None)
                if not acad_year or not str(acad_year).strip():
                    acad_year = f"{datetime.now().year}-{datetime.now().year + 1}"
                dob_val = getattr(payload, "date_of_birth", None)
                sem_val = getattr(payload, "semester", None) or 1
                course_val = getattr(payload, "course", None) or "General"
                perm_addr = getattr(payload, "permanent_address", None)
                curr_addr = getattr(payload, "current_address", None)
                city_val = getattr(payload, "city", None)
                state_val = getattr(payload, "state", None)
                postal_val = getattr(payload, "postal_code", None)
                country_val = getattr(payload, "country", None) or "India"
                g_name = getattr(payload, "guardian_name", None)
                g_rel = getattr(payload, "guardian_relation", None)
                g_phone = getattr(payload, "guardian_phone", None)
                g_email = getattr(payload, "guardian_email", None)
                ec_name = getattr(payload, "emergency_contact_name", None)
                ec_phone = getattr(payload, "emergency_contact_phone", None)

                cursor.execute("""
                    INSERT INTO students (
                        student_id, user_id, first_name, last_name, email, phone,
                        gender, date_of_birth, semester, branch, academic_year, admission_date, status,
                        course, permanent_address, current_address, city, state, postal_code, country,
                        guardian_name, guardian_relation, guardian_phone, guardian_email,
                        emergency_contact_name, emergency_contact_phone
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, date('now'), 'Pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    enrollment, user_id, first_name, last_name, email, phone,
                    gender, dob_val, sem_val, branch, acad_year,
                    course_val, perm_addr, curr_addr, city_val, state_val, postal_val, country_val,
                    g_name, g_rel, g_phone, g_email, ec_name, ec_phone
                ))
                linked_student_id = cursor.lastrowid
                cursor.execute("UPDATE users SET linked_student_id = ? WHERE id = ?;", (linked_student_id, user_id))

            # Insert Registration Approval Request
            if target_role == "parent_guardian":
                status_str = "Pending"
                admin_warden_status = "Pending"
                student_status = "Pending"
                reg_message = f"Parent registration submitted. Verification requests sent to your child ({child_info['first_name']} {child_info['last_name']}) and the Hostel Warden/Administrator."
            elif target_role == "student":
                status_str = "Pending"
                admin_warden_status = "Pending"
                student_status = "N/A"
                reg_message = f"Student registration submitted for {first_name} {last_name}. Awaiting approval by the Hostel Warden or Administrator."
            else:
                status_str = "Pending"
                admin_warden_status = "Pending"
                student_status = "N/A"
                role_title = "Hostel Warden" if target_role == "warden" else "Staff Member"
                reg_message = f"{role_title} registration submitted for {first_name} {last_name}. Awaiting approval by the Administrator."

            cursor.execute("""
                INSERT INTO registration_requests (
                    user_id, username, email, first_name, last_name, phone,
                    requested_role, specialization, student_roll_no, branch,
                    linked_student_id, relationship, status,
                    admin_warden_approval_status, student_approval_status,
                    staff_id, gender, hostel_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                user_id, uname, email, first_name, last_name, phone,
                target_role, payload.specialization,
                payload.enrollment_no if target_role == "student" else None,
                payload.branch if target_role == "student" else None,
                linked_student_id,
                getattr(payload, 'relationship', 'Parent'),
                status_str, admin_warden_status, student_status,
                assigned_staff_id, gender_val, assigned_hostel_id
            ))
            req_id = cursor.lastrowid

            # Multi-Ward Relationship Persistence (Migration 018)
            if target_role == "parent_guardian" and resolved_children:
                p_rel = getattr(payload, 'relationship', 'Parent') or 'Parent'
                for c_rec in resolved_children:
                    cursor.execute("""
                        INSERT INTO registration_request_wards (
                            registration_request_id, student_id, relationship,
                            student_approval_status, administrative_approval_status
                        ) VALUES (?, ?, ?, 'Pending', 'Pending');
                    """, (req_id, c_rec["id"], p_rel))

            # Notifications to all resolved children
            if target_role == "parent_guardian" and resolved_children:
                for c_rec in resolved_children:
                    if c_rec and c_rec["user_id"]:
                        cursor.execute("""
                            INSERT INTO notifications (user_id, title, message, category, priority, is_read, event_key, delivery_channel)
                            VALUES (?, 'Parent Verification Request', ?, 'security', 'Important', 0, ?, 'in_app');
                        """, (
                            c_rec["user_id"],
                            f"{first_name} {last_name} ({email}) has requested to link as your parent/guardian. Please confirm on your dashboard.",
                            f"reg_approval:{req_id}:{c_rec['id']}"
                        ))

            # Audit Log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, ip_address, latency_ms)
                VALUES (?, ?, 'USER_REGISTRATION_SUBMITTED', 'registration_requests', ?, ?, ?, 0.0);
            """, (user_id, uname, str(req_id), f"Registration submitted for role {target_role} (Pending Approval)", ip_address))

            conn.commit()

            # Fetch roles and permissions for user dict
            roles, permissions = cls.get_user_roles_and_permissions(conn, user_id)
            user_dict = {
                'id': user_id,
                'username': uname,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone,
                'roles': roles,
                'permissions': sorted(list(permissions)),
                'active_role': target_role,
                'linked_student_id': linked_student_id,
                'linked_hostel_id': None
            }

            return {
                "status": "Pending_Approval",
                "message": reg_message,
                "access_token": "",
                "refresh_token": "",
                "token_type": "bearer",
                "expires_in": 0,
                "user": user_dict,
                "requires_approval": True,
                "requires_student_approval": (target_role == "parent_guardian"),
                "requires_admin_warden_approval": True
            }
        finally:
            if should_close:
                conn.close()

    @classmethod
    def get_pending_registrations(cls, current_user: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
        """Retrieve pending registrations strictly filtered by active role permissions and facility boundaries."""
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            active_role = (
                current_user.get("active_role")
                or current_user.get("role")
                or (current_user.get("roles")[0] if isinstance(current_user.get("roles"), (list, tuple)) and current_user.get("roles") else "")
            ).strip().lower()

            # 1. Student view: only pending parent requests targeting this student (supporting multi-ward)
            if active_role == "student":
                linked_s_id = current_user.get("linked_student_id")
                if not linked_s_id:
                    return []
                cursor.execute("""
                    SELECT DISTINCT rr.*, s.first_name as student_first_name, s.last_name as student_last_name, s.student_id as student_roll_no_display, h.name as hostel_name, h.code as hostel_code, h.hostel_type,
                           COALESCE(rw.student_approval_status, rr.student_approval_status) as ward_student_approval_status
                    FROM registration_requests rr
                    LEFT JOIN registration_request_wards rw ON rr.id = rw.registration_request_id AND rw.student_id = ?
                    LEFT JOIN students s ON COALESCE(rw.student_id, rr.linked_student_id) = s.id
                    LEFT JOIN hostels h ON rr.hostel_id = h.id
                    WHERE rr.status = 'Pending'
                      AND (
                          (rw.student_id = ? AND rw.student_approval_status = 'Pending')
                          OR (rw.id IS NULL AND rr.linked_student_id = ? AND rr.student_approval_status = 'Pending')
                      )
                    ORDER BY rr.id DESC;
                """, (linked_s_id, linked_s_id, linked_s_id))
                return [dict(r) for r in cursor.fetchall()]

            # 2. Warden & Clerk view: can view and verify Students and Parents in assigned hostel (unassigned fails closed)
            if active_role in ("warden", "assistant_warden", "hostel_clerk"):
                linked_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
                if not linked_hid and current_user.get("id"):
                    cursor.execute("SELECT linked_hostel_id FROM users WHERE id = ?;", (current_user["id"],))
                    u_row = cursor.fetchone()
                    if u_row and u_row[0]:
                        linked_hid = u_row[0]
                    else:
                        cursor.execute("SELECT id FROM hostels WHERE warden_id = ? LIMIT 1;", (current_user["id"],))
                        hw = cursor.fetchone()
                        if hw:
                            linked_hid = hw[0]
                if not linked_hid:
                    return []
                cursor.execute("""
                    SELECT DISTINCT rr.*, s.first_name as student_first_name, s.last_name as student_last_name, s.student_id as student_roll_no_display, h.name as hostel_name, h.code as hostel_code, h.hostel_type
                    FROM registration_requests rr
                    LEFT JOIN students s ON rr.linked_student_id = s.id
                    LEFT JOIN hostels h ON rr.hostel_id = h.id
                    LEFT JOIN room_allocations ra ON ra.student_id = rr.linked_student_id AND ra.allocation_status = 'Active'
                    LEFT JOIN rooms rm ON rm.id = ra.room_id
                    LEFT JOIN floors fl ON fl.id = rm.floor_id
                    LEFT JOIN buildings bld ON bld.id = fl.building_id
                    LEFT JOIN registration_request_wards rw ON rr.id = rw.registration_request_id
                    LEFT JOIN room_allocations rwa ON rwa.student_id = rw.student_id AND rwa.allocation_status = 'Active'
                    LEFT JOIN rooms rwm ON rwm.id = rwa.room_id
                    LEFT JOIN floors rwfl ON rwfl.id = rwm.floor_id
                    LEFT JOIN buildings rwbld ON rwbld.id = rwfl.building_id
                    WHERE rr.requested_role IN ('student', 'parent_guardian')
                      AND rr.status = 'Pending'
                      AND (
                          -- Student registrations explicitly assigned or allocated to this warden's hostel
                          (rr.requested_role = 'student' AND rr.admin_warden_approval_status = 'Pending' AND (
                              rr.hostel_id = ? OR (rr.hostel_id IS NULL AND bld.hostel_id = ?)
                          ))
                          OR
                          -- Parent registrations where at least one ward belongs to this warden's hostel
                          (rr.requested_role = 'parent_guardian' AND (
                              rr.hostel_id = ?
                              OR (rw.student_id IS NOT NULL AND rwbld.hostel_id = ? AND rw.administrative_approval_status = 'Pending')
                              OR (rr.linked_student_id IS NOT NULL AND bld.hostel_id = ? AND rr.admin_warden_approval_status = 'Pending')
                          ))
                      )
                    ORDER BY rr.id DESC;
                """, (linked_hid, linked_hid, linked_hid, linked_hid, linked_hid))
                results = [dict(r) for r in cursor.fetchall()]
                for req in results:
                    if req.get("requested_role") in ("parent_guardian", "parent"):
                        cursor.execute("""
                            SELECT rw.id, rw.student_id, rw.relationship, rw.student_approval_status, rw.administrative_approval_status,
                                   s.first_name, s.last_name, s.student_id as student_roll_no,
                                   COALESCE(
                                       (SELECT bld.hostel_id FROM room_allocations ra
                                        JOIN rooms rm ON rm.id = ra.room_id
                                        JOIN floors fl ON fl.id = rm.floor_id
                                        JOIN buildings bld ON bld.id = fl.building_id
                                        WHERE ra.student_id = rw.student_id AND ra.allocation_status = 'Active' LIMIT 1),
                                       NULL
                                   ) as ward_hostel_id
                            FROM registration_request_wards rw
                            JOIN students s ON s.id = rw.student_id
                            WHERE rw.registration_request_id = ?;
                        """, (req["id"],))
                        all_wards = [dict(w) for w in cursor.fetchall()]
                        req["wards"] = [w for w in all_wards if w.get("ward_hostel_id") == int(linked_hid)]
                return results

            # 3. Super Admin, Hostel Admin, Admission Officer, Auditor: view registrations campus-wide
            if active_role in ("super_admin", "hostel_admin", "admission_officer", "auditor"):
                cursor.execute("""
                    SELECT rr.*, s.first_name as student_first_name, s.last_name as student_last_name, s.student_id as student_roll_no_display, h.name as hostel_name, h.code as hostel_code, h.hostel_type
                    FROM registration_requests rr
                    LEFT JOIN students s ON rr.linked_student_id = s.id
                    LEFT JOIN hostels h ON rr.hostel_id = h.id
                    WHERE rr.status = 'Pending'
                    ORDER BY rr.id DESC;
                """)
                results = [dict(r) for r in cursor.fetchall()]
                for req in results:
                    if req.get("requested_role") in ("parent_guardian", "parent"):
                        cursor.execute("""
                            SELECT rw.id, rw.student_id, rw.relationship, rw.student_approval_status, rw.administrative_approval_status,
                                   s.first_name, s.last_name, s.student_id as student_roll_no
                            FROM registration_request_wards rw
                            JOIN students s ON s.id = rw.student_id
                            WHERE rw.registration_request_id = ?;
                        """, (req["id"],))
                        req["wards"] = [dict(w) for w in cursor.fetchall()]
                return results

            return []
        finally:
            if should_close:
                conn.close()

    @classmethod
    def process_registration_action(
        cls,
        req_id: int,
        action: str,
        reason: Optional[str],
        current_user: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        """Process approval or rejection on a registration request according to strict active-role RBAC rules."""
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM registration_requests WHERE id = ?;", (req_id,))
            req_row = cursor.fetchone()
            if not req_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Registration request #{req_id} not found.")
            req = dict(req_row)

            if req["status"] != "Pending":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Registration request #{req_id} is already {req['status']}.")

            action_normalized = action.strip().lower()
            if action_normalized in ("approve", "approved"):
                action_normalized = "approve"
            elif action_normalized in ("reject", "rejected"):
                action_normalized = "reject"
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Action must be 'approve' or 'reject'.")

            active_role = (
                current_user.get("active_role")
                or current_user.get("role")
                or (current_user.get("roles")[0] if isinstance(current_user.get("roles"), (list, tuple)) and current_user.get("roles") else "")
            ).strip().lower()
            target_role = req["requested_role"]
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # -------------------------------------------------------------
            # RULE 1: STUDENT ACTIVE ROLE (Multi-Ward Support)
            # -------------------------------------------------------------
            if active_role == "student":
                if target_role != "parent_guardian":
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students can only verify parent/guardian registration requests.")
                
                cursor.execute("""
                    SELECT id FROM registration_request_wards
                    WHERE registration_request_id = ? AND student_id = ?;
                """, (req_id, current_user.get("linked_student_id")))
                ward_row = cursor.fetchone()

                if not ward_row and current_user.get("linked_student_id") != req["linked_student_id"]:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Security Violation: You can only approve verification requests for your own parent.")

                if action_normalized == "reject":
                    cursor.execute("""
                        UPDATE registration_request_wards
                        SET student_approval_status = 'Rejected', student_approved_by = ?, student_approved_at = ?,
                            rejection_reason = ?, updated_at = ?
                        WHERE registration_request_id = ? AND student_id = ?;
                    """, (current_user["id"], now_str, reason or "Declined by student", now_str, req_id, current_user.get("linked_student_id")))

                    cursor.execute("""
                        UPDATE registration_requests
                        SET status = 'Rejected', student_approval_status = 'Rejected',
                            student_approved_by = ?, student_approved_at = ?,
                            rejection_reason = ?, updated_at = ?
                        WHERE id = ?;
                    """, (current_user["id"], now_str, reason or "Declined by student", now_str, req_id))
                    conn.commit()
                    return {"success": True, "status": "Rejected", "message": "Parent registration request rejected."}

                # Student approves their ward link:
                cursor.execute("""
                    UPDATE registration_request_wards
                    SET student_approval_status = 'Approved', student_approved_by = ?, student_approved_at = ?, updated_at = ?
                    WHERE registration_request_id = ? AND student_id = ?;
                """, (current_user["id"], now_str, now_str, req_id, current_user.get("linked_student_id")))

                cursor.execute("""
                    SELECT COUNT(*) FROM registration_request_wards
                    WHERE registration_request_id = ? AND student_approval_status != 'Approved';
                """, (req_id,))
                unapproved_wards_count = cursor.fetchone()[0]

                if unapproved_wards_count == 0:
                    cursor.execute("""
                        UPDATE registration_requests
                        SET student_approval_status = 'Approved',
                            student_approved_by = ?, student_approved_at = ?,
                            updated_at = ?
                        WHERE id = ?;
                    """, (current_user["id"], now_str, now_str, req_id))
                    all_students_approved = True
                else:
                    all_students_approved = False

                # Check if Admin/Warden has also approved:
                cursor.execute("""
                    SELECT COUNT(*) FROM registration_request_wards
                    WHERE registration_request_id = ?
                      AND (student_approval_status != 'Approved' OR administrative_approval_status != 'Approved');
                """, (req_id,))
                unapproved_count = cursor.fetchone()[0]

                cursor.execute("SELECT admin_warden_approval_status FROM registration_requests WHERE id = ?;", (req_id,))
                fresh_admin_status = cursor.fetchone()[0]

                if all_students_approved and (fresh_admin_status == "Approved" or unapproved_count == 0):
                    cursor.execute("UPDATE registration_requests SET status = 'Approved', admin_warden_approval_status = 'Approved', updated_at = ? WHERE id = ?;", (now_str, req_id))
                    cursor.execute("UPDATE users SET is_active = 1, linked_student_id = ? WHERE id = ?;", (req["linked_student_id"], req["user_id"]))
                    cursor.execute("""
                        INSERT OR IGNORE INTO guardians (name, phone, email, relationship)
                        VALUES (?, ?, ?, ?);
                    """, (f"{req['first_name']} {req['last_name']}", req["phone"], req["email"], req["relationship"] or "Parent"))
                    gid = cursor.lastrowid
                    if not gid:
                        cursor.execute("SELECT id FROM guardians WHERE (phone = ? AND ? != '') OR (LOWER(email) = ? AND ? != '') LIMIT 1;",
                                       (req["phone"] or "", req["phone"] or "", (req["email"] or "").lower(), (req["email"] or "").lower()))
                        g_row = cursor.fetchone()
                        gid = g_row[0] if g_row else None

                    cursor.execute("SELECT student_id, relationship FROM registration_request_wards WHERE registration_request_id = ?;", (req_id,))
                    wards = cursor.fetchall()
                    if not wards and req["linked_student_id"]:
                        wards = [(req["linked_student_id"], req.get("relationship", "Parent"))]

                    for w in wards:
                        w_sid = w[0]
                        w_rel = w[1] or "Parent"
                        cursor.execute("""
                            INSERT INTO parent_student_links (parent_user_id, student_id, guardian_id, relationship, status)
                            VALUES (?, ?, ?, ?, 'Active')
                            ON CONFLICT(parent_user_id, student_id) DO UPDATE SET status = 'Active', updated_at = CURRENT_TIMESTAMP;
                        """, (req["user_id"], w_sid, gid, w_rel))
                        if gid and w_sid:
                            cursor.execute("INSERT OR IGNORE INTO student_guardians (student_id, guardian_id, is_primary) VALUES (?, ?, 1);", (w_sid, gid))

                    conn.commit()
                    return {"success": True, "status": "Approved", "message": "Parent verified! Both student and hostel administration approvals complete. Parent account is now Active."}
                else:
                    conn.commit()
                    msg = "You have confirmed your parent! Final activation is pending Hostel Warden / Administrator approval." if all_students_approved else "Your approval recorded! Waiting for remaining student ward approval(s)."
                    return {"success": True, "status": "Pending", "message": msg}

            # -------------------------------------------------------------
            # RULE 2: WARDEN, ASSISTANT WARDEN, HOSTEL CLERK ACTIVE ROLE
            # -------------------------------------------------------------
            if active_role in ("warden", "assistant_warden", "hostel_clerk"):
                linked_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
                if not linked_hid and current_user.get("id"):
                    cursor.execute("SELECT linked_hostel_id FROM users WHERE id = ?;", (current_user["id"],))
                    u_row = cursor.fetchone()
                    if u_row and u_row[0]:
                        linked_hid = u_row[0]
                    else:
                        cursor.execute("SELECT id FROM hostels WHERE warden_id = ? LIMIT 1;", (current_user["id"],))
                        hw = cursor.fetchone()
                        if hw:
                            linked_hid = hw[0]
                if not linked_hid:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access Denied: Warden has no assigned hostel facility."
                    )

                if target_role not in ("student", "parent_guardian"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Unauthorized: Only Administrators can approve staff member registrations."
                    )

                # Facility Scoping: Warden can only approve students/parents associated with their assigned hostel
                if target_role == "student":
                    req_hid = req.get("hostel_id")
                    student_hid = None
                    if req_hid:
                        student_hid = int(req_hid)
                    elif req.get("linked_student_id"):
                        cursor.execute("""
                            SELECT bld.hostel_id
                            FROM room_allocations ra
                            JOIN rooms rm ON rm.id = ra.room_id
                            JOIN floors fl ON fl.id = rm.floor_id
                            JOIN buildings bld ON bld.id = fl.building_id
                            WHERE ra.student_id = ? AND ra.allocation_status = 'Active' LIMIT 1;
                        """, (req["linked_student_id"],))
                        alloc_row = cursor.fetchone()
                        if alloc_row and alloc_row[0]:
                            student_hid = int(alloc_row[0])

                    if not student_hid:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Unauthorized: Unassigned student registrations must be processed by Central Admissions or Administrator."
                        )
                    if student_hid != int(linked_hid):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Unauthorized: Wardens can only approve registrations for their assigned hostel facility."
                        )

                if target_role == "student":
                    if action_normalized == "reject":
                        cursor.execute("""
                            UPDATE registration_requests
                            SET status = 'Rejected', admin_warden_approval_status = 'Rejected',
                                admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = 'warden',
                                rejection_reason = ?, updated_at = ?
                            WHERE id = ?;
                        """, (current_user["id"], now_str, reason or "Rejected by Warden", now_str, req_id))
                        cursor.execute("UPDATE users SET is_active = 0 WHERE id = ?;", (req["user_id"],))
                        cursor.execute("UPDATE students SET status = 'Withdrawn' WHERE user_id = ?;", (req["user_id"],))
                        conn.commit()
                        return {"success": True, "status": "Rejected", "message": "Student registration request rejected."}

                    cursor.execute("""
                        UPDATE registration_requests
                        SET status = 'Approved', admin_warden_approval_status = 'Approved',
                            admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = 'warden',
                            updated_at = ?
                        WHERE id = ?;
                    """, (current_user["id"], now_str, now_str, req_id))
                    cursor.execute("UPDATE users SET is_active = 1 WHERE id = ?;", (req["user_id"],))
                    cursor.execute("UPDATE students SET status = 'Active' WHERE user_id = ?;", (req["user_id"],))
                    conn.commit()
                    return {"success": True, "status": "Approved", "message": f"Student registration approved by warden! Student account is now Active."}

                elif target_role == "parent_guardian":
                    # Multi-Ward Per-Hostel Administrative Scoping:
                    # Query all wards associated with this parent registration request
                    cursor.execute("""
                        SELECT rw.id, rw.student_id, rw.relationship, rw.student_approval_status, rw.administrative_approval_status,
                               COALESCE(
                                   (SELECT bld.hostel_id FROM room_allocations ra
                                    JOIN rooms rm ON rm.id = ra.room_id
                                    JOIN floors fl ON fl.id = rm.floor_id
                                    JOIN buildings bld ON bld.id = fl.building_id
                                    WHERE ra.student_id = rw.student_id AND ra.allocation_status = 'Active' LIMIT 1),
                                   ?
                               ) as ward_hostel_id
                        FROM registration_request_wards rw
                        WHERE rw.registration_request_id = ?;
                    """, (req.get("hostel_id"), req_id))
                    wards = [dict(r) for r in cursor.fetchall()]

                    if not wards and req.get("linked_student_id"):
                        cursor.execute("""
                            SELECT bld.hostel_id FROM room_allocations ra
                            JOIN rooms rm ON rm.id = ra.room_id
                            JOIN floors fl ON fl.id = rm.floor_id
                            JOIN buildings bld ON bld.id = fl.building_id
                            WHERE ra.student_id = ? AND ra.allocation_status = 'Active' LIMIT 1;
                        """, (req["linked_student_id"],))
                        single_alloc = cursor.fetchone()
                        single_hid = single_alloc[0] if single_alloc else req.get("hostel_id")
                        wards = [{
                            "id": None,
                            "student_id": req["linked_student_id"],
                            "relationship": req.get("relationship", "Parent"),
                            "student_approval_status": req.get("student_approval_status", "Pending"),
                            "administrative_approval_status": req.get("admin_warden_approval_status", "Pending"),
                            "ward_hostel_id": single_hid
                        }]

                    # Filter wards belonging to this Warden's specific facility
                    my_wards = [w for w in wards if w["ward_hostel_id"] and int(w["ward_hostel_id"]) == int(linked_hid)]
                    if not my_wards:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Unauthorized: Wardens can only approve registrations for wards in their assigned hostel facility."
                        )

                    if action_normalized == "reject":
                        for w in my_wards:
                            if w["id"]:
                                cursor.execute("""
                                    UPDATE registration_request_wards
                                    SET administrative_approval_status = 'Rejected', administrative_approved_by = ?,
                                        administrative_approved_at = ?, rejection_reason = ?, updated_at = ?
                                    WHERE id = ?;
                                """, (current_user["id"], now_str, reason or "Rejected by Warden", now_str, w["id"]))
                        cursor.execute("""
                            UPDATE registration_requests
                            SET status = 'Rejected', admin_warden_approval_status = 'Rejected',
                                admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = 'warden',
                                rejection_reason = ?, updated_at = ?
                            WHERE id = ?;
                        """, (current_user["id"], now_str, reason or "Rejected by Warden", now_str, req_id))
                        conn.commit()
                        return {"success": True, "status": "Rejected", "message": "Parent registration request rejected for this hostel facility."}

                    # Approve this warden's wards ONLY
                    for w in my_wards:
                        if w["id"]:
                            cursor.execute("""
                                UPDATE registration_request_wards
                                SET administrative_approval_status = 'Approved', administrative_approved_by = ?,
                                    administrative_approved_at = ?, updated_at = ?
                                WHERE id = ?;
                            """, (current_user["id"], now_str, now_str, w["id"]))

                    # Check if ALL wards for this parent have completed BOTH student and administrative approvals
                    cursor.execute("""
                        SELECT COUNT(*) FROM registration_request_wards
                        WHERE registration_request_id = ?
                          AND (student_approval_status != 'Approved' OR administrative_approval_status != 'Approved');
                    """, (req_id,))
                    unapproved_count = cursor.fetchone()[0]

                    if unapproved_count == 0:
                        cursor.execute("""
                            UPDATE registration_requests
                            SET status = 'Approved', admin_warden_approval_status = 'Approved',
                                admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = 'warden',
                                updated_at = ?
                            WHERE id = ?;
                        """, (current_user["id"], now_str, now_str, req_id))
                        cursor.execute("UPDATE users SET is_active = 1, linked_student_id = ? WHERE id = ?;", (req["linked_student_id"], req["user_id"]))
                        cursor.execute("""
                            INSERT OR IGNORE INTO guardians (name, phone, email, relationship)
                            VALUES (?, ?, ?, ?);
                        """, (f"{req['first_name']} {req['last_name']}", req["phone"], req["email"], req["relationship"] or "Parent"))
                        gid = cursor.lastrowid
                        if not gid:
                            cursor.execute("SELECT id FROM guardians WHERE (phone = ? AND ? != '') OR (LOWER(email) = ? AND ? != '') LIMIT 1;",
                                           (req["phone"] or "", req["phone"] or "", (req["email"] or "").lower(), (req["email"] or "").lower()))
                            g_row = cursor.fetchone()
                            gid = g_row[0] if g_row else None

                        cursor.execute("SELECT student_id, relationship FROM registration_request_wards WHERE registration_request_id = ?;", (req_id,))
                        all_wards = cursor.fetchall()
                        if not all_wards and req["linked_student_id"]:
                            all_wards = [(req["linked_student_id"], req.get("relationship", "Parent"))]

                        for w in all_wards:
                            w_sid = w[0]
                            w_rel = w[1] or "Parent"
                            cursor.execute("""
                                INSERT INTO parent_student_links (parent_user_id, student_id, guardian_id, relationship, status)
                                VALUES (?, ?, ?, ?, 'Active')
                                ON CONFLICT(parent_user_id, student_id) DO UPDATE SET status = 'Active', updated_at = CURRENT_TIMESTAMP;
                            """, (req["user_id"], w_sid, gid, w_rel))
                            if gid and w_sid:
                                cursor.execute("INSERT OR IGNORE INTO student_guardians (student_id, guardian_id, is_primary) VALUES (?, ?, 1);", (w_sid, gid))

                        conn.commit()
                        return {"success": True, "status": "Approved", "message": "All student and facility approvals complete! Parent account is now Active."}
                    else:
                        conn.commit()
                        return {"success": True, "status": "Pending", "message": "Approval recorded for wards in your hostel facility. Parent account remains pending until remaining ward and facility approvals are completed."}

            # -------------------------------------------------------------
            # RULE 3: SUPER ADMIN, HOSTEL ADMIN, ADMISSION OFFICER ACTIVE ROLE
            # -------------------------------------------------------------
            if active_role in ("super_admin", "hostel_admin", "admission_officer"):
                is_staff_role = target_role in ("staff", "maintenance_staff", "warden", "security_guard", "mess_manager", "accountant")
                if active_role == "admission_officer" and is_staff_role:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Unauthorized: Admission officers can only verify student and parent registrations."
                    )
                if is_staff_role:
                    if action_normalized == "reject":
                        cursor.execute("""
                            UPDATE registration_requests
                            SET status = 'Rejected', admin_warden_approval_status = 'Rejected',
                                admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = 'admin',
                                rejection_reason = ?, updated_at = ?
                            WHERE id = ?;
                        """, (current_user["id"], now_str, reason or "Rejected by Administrator", now_str, req_id))
                        conn.commit()
                        return {"success": True, "status": "Rejected", "message": "Staff registration request rejected."}

                    req_hid = req["hostel_id"] if ("hostel_id" in req.keys() and req["hostel_id"]) else None
                    if (target_role in ("warden", "assistant_warden") or (req.get("specialization") or "").lower() in ("warden", "hostel_warden")) and req_hid:
                        cursor.execute("""
                            SELECT COUNT(DISTINCT u.id)
                            FROM users u
                            JOIN user_roles ur ON u.id = ur.user_id
                            JOIN roles r ON ur.role_id = r.id
                            WHERE r.name IN ('warden', 'assistant_warden')
                              AND u.linked_hostel_id = ?
                              AND u.is_active = 1
                              AND u.id != ?;
                        """, (req_hid, req["user_id"]))
                        if cursor.fetchone()[0] >= 2:
                            raise HTTPException(status_code=400, detail="Cannot approve: Selected hostel already has 2 active wardens assigned.")
                        cursor.execute("UPDATE users SET is_active = 1, linked_hostel_id = ? WHERE id = ?;", (req_hid, req["user_id"]))
                        cursor.execute("UPDATE hostels SET warden_id = ? WHERE id = ? AND warden_id IS NULL;", (req["user_id"], req_hid))
                    else:
                        cursor.execute("UPDATE users SET is_active = 1 WHERE id = ?;", (req["user_id"],))

                    cursor.execute("""
                        UPDATE registration_requests
                        SET status = 'Approved', admin_warden_approval_status = 'Approved',
                            admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = 'admin',
                            updated_at = ?
                        WHERE id = ?;
                    """, (current_user["id"], now_str, now_str, req_id))
                    conn.commit()
                    return {"success": True, "status": "Approved", "message": f"Staff registration approved! {req['first_name']} {req['last_name']} account is now Active."}

                elif target_role == "student":
                    if action_normalized == "reject":
                        cursor.execute("""
                            UPDATE registration_requests
                            SET status = 'Rejected', admin_warden_approval_status = 'Rejected',
                                admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = 'admin',
                                rejection_reason = ?, updated_at = ?
                            WHERE id = ?;
                        """, (current_user["id"], now_str, reason or "Rejected by Administrator", now_str, req_id))
                        cursor.execute("UPDATE users SET is_active = 0 WHERE id = ?;", (req["user_id"],))
                        cursor.execute("UPDATE students SET status = 'Withdrawn' WHERE user_id = ?;", (req["user_id"],))
                        conn.commit()
                        return {"success": True, "status": "Rejected", "message": "Student registration request rejected."}

                    cursor.execute("""
                        UPDATE registration_requests
                        SET status = 'Approved', admin_warden_approval_status = 'Approved',
                            admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = 'admin',
                            updated_at = ?
                        WHERE id = ?;
                    """, (current_user["id"], now_str, now_str, req_id))
                    cursor.execute("UPDATE users SET is_active = 1 WHERE id = ?;", (req["user_id"],))
                    cursor.execute("UPDATE students SET status = 'Active' WHERE user_id = ?;", (req["user_id"],))
                    conn.commit()
                    return {"success": True, "status": "Approved", "message": f"Student registration approved by Administrator! Student account is now Active."}

                elif target_role == "parent_guardian":
                    if action_normalized == "reject":
                        cursor.execute("""
                            UPDATE registration_requests
                            SET status = 'Rejected', admin_warden_approval_status = 'Rejected',
                                admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = 'admin',
                                rejection_reason = ?, updated_at = ?
                            WHERE id = ?;
                        """, (current_user["id"], now_str, reason or "Rejected by Administrator", now_str, req_id))
                        conn.commit()
                        return {"success": True, "status": "Rejected", "message": "Parent registration request rejected."}

                    cursor.execute("""
                        UPDATE registration_requests
                        SET admin_warden_approval_status = 'Approved',
                            admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = 'admin',
                            updated_at = ?
                        WHERE id = ?;
                    """, (current_user["id"], now_str, now_str, req_id))

                    cursor.execute("""
                        UPDATE registration_request_wards
                        SET administrative_approval_status = 'Approved',
                            administrative_approved_by = ?, administrative_approved_at = ?,
                            updated_at = ?
                        WHERE registration_request_id = ?;
                    """, (current_user["id"], now_str, now_str, req_id))

                    cursor.execute("""
                        SELECT COUNT(*) FROM registration_request_wards
                        WHERE registration_request_id = ? AND student_approval_status != 'Approved';
                    """, (req_id,))
                    unapproved_wards_count = cursor.fetchone()[0]

                    if unapproved_wards_count == 0 and req["student_approval_status"] == "Approved":
                        cursor.execute("UPDATE registration_requests SET status = 'Approved', updated_at = ? WHERE id = ?;", (now_str, req_id))
                        cursor.execute("UPDATE users SET is_active = 1, linked_student_id = ? WHERE id = ?;", (req["linked_student_id"], req["user_id"]))
                        cursor.execute("""
                            INSERT OR IGNORE INTO guardians (name, phone, email, relationship)
                            VALUES (?, ?, ?, ?);
                        """, (f"{req['first_name']} {req['last_name']}", req["phone"], req["email"], req["relationship"] or "Parent"))
                        gid = cursor.lastrowid
                        if not gid:
                            cursor.execute("SELECT id FROM guardians WHERE (phone = ? AND ? != '') OR (LOWER(email) = ? AND ? != '') LIMIT 1;",
                                           (req["phone"] or "", req["phone"] or "", (req["email"] or "").lower(), (req["email"] or "").lower()))
                            g_row = cursor.fetchone()
                            gid = g_row[0] if g_row else None

                        cursor.execute("SELECT student_id, relationship FROM registration_request_wards WHERE registration_request_id = ?;", (req_id,))
                        wards = cursor.fetchall()
                        if not wards and req["linked_student_id"]:
                            wards = [(req["linked_student_id"], req.get("relationship", "Parent"))]

                        for w in wards:
                            w_sid = w[0]
                            w_rel = w[1] or "Parent"
                            cursor.execute("""
                                INSERT INTO parent_student_links (parent_user_id, student_id, guardian_id, relationship, status)
                                VALUES (?, ?, ?, ?, 'Active')
                                ON CONFLICT(parent_user_id, student_id) DO UPDATE SET status = 'Active', updated_at = CURRENT_TIMESTAMP;
                            """, (req["user_id"], w_sid, gid, w_rel))
                            if gid and w_sid:
                                cursor.execute("INSERT OR IGNORE INTO student_guardians (student_id, guardian_id, is_primary) VALUES (?, ?, 1);", (w_sid, gid))

                        conn.commit()
                        return {"success": True, "status": "Approved", "message": "Parent approved by Administrator! Both child and admin approvals complete. Parent account is now Active."}
                    else:
                        conn.commit()
                        return {"success": True, "status": "Pending", "message": "Administrator approval recorded! Account will activate once all student wards confirm."}

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Your active role '{active_role}' is not authorized to review registrations."
            )
        finally:
            if should_close:
                conn.close()
