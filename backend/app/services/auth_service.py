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
            if target_role not in roles:
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
            """, (target_role,))
            target_permissions = [row[0] for row in cursor.fetchall()]

            # Issue new token with updated active_role
            token_payload = {
                "sub": user_row["username"],
                "user_id": user_id,
                "roles": roles,
                "active_role": target_role
            }
            new_access_token = create_access_token(token_payload)

            # Record audit event
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, ip_address, latency_ms)
                VALUES (?, ?, 'ROLE_SWITCH', 'user_session', ?, ?, ?, 0.0);
            """, (user_id, user_row["username"], str(user_id), f"Switched active role to {target_role}", ip_address))
            conn.commit()

            return {
                "success": True,
                "active_role": target_role,
                "access_token": new_access_token,
                "permissions": target_permissions,
                "message": f"Successfully switched active context to {target_role}."
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
                if any(k in spec for k in ("warden", "hostel_warden")):
                    target_role = "warden"
                elif any(k in spec for k in ("mess", "chef", "cook", "kitchen", "dining")):
                    target_role = "mess_manager"
                elif any(k in spec for k in ("security", "guard", "gate")):
                    target_role = "security_guard"
                elif any(k in spec for k in ("account", "finance", "billing")):
                    target_role = "accountant"
                else:
                    target_role = "maintenance_staff"
            elif requested_role in ("student", "parent_guardian", "warden", "assistant_warden"):
                target_role = requested_role
            else:
                target_role = "student"

            # Check if username already exists in users or pending registrations
            # Poka-Yoke: Hostel selection and maximum 2 wardens constraint
            assigned_hostel_id = getattr(payload, "hostel_id", None)
            if target_role == "warden" or (payload.specialization or "").lower() in ("warden", "hostel_warden"):
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

            # If Parent: Resolve Child Student Record
            linked_student_id = None
            child_info = None
            if target_role == "parent_guardian":
                child_ident = (getattr(payload, 'child_identifier', None) or "").strip()
                if not child_ident:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Child Roll Number or University Email is required for Parent / Guardian registration."
                    )
                cursor.execute("""
                    SELECT s.id, s.student_id, s.first_name, s.last_name, s.user_id, s.email
                    FROM students s
                    WHERE s.student_id = ? OR s.email = ?;
                """, (child_ident, child_ident.lower()))
                child_info = cursor.fetchone()
                if not child_info:
                    cursor.execute("""
                        SELECT s.id, s.student_id, s.first_name, s.last_name, s.user_id, s.email
                        FROM students s
                        JOIN users u ON s.user_id = u.id
                        WHERE u.username = ?;
                    """, (child_ident.lower(),))
                    child_info = cursor.fetchone()
                if not child_info:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No enrolled student found matching identifier '{child_ident}'. Please check your child's roll number or email."
                    )
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
                cursor.execute("SELECT id FROM roles WHERE name = 'student';")
                role_row = cursor.fetchone()
                target_role = "student"
            role_id = role_row["id"] if isinstance(role_row, sqlite3.Row) else role_row[0]

            # Assign Role in user_roles
            cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?);", (user_id, role_id))

            # Unique Staff ID generation for staff members
            assigned_staff_id = None
            if target_role not in ("student", "parent_guardian"):
                assigned_staff_id = f"STF-{user_id:04d}"
                cursor.execute("SELECT id FROM users WHERE staff_id = ?;", (assigned_staff_id,))
                if cursor.fetchone():
                    assigned_staff_id = f"STF-{user_id:04d}-{uuid.uuid4().hex[:4].upper()}"
                cursor.execute("UPDATE users SET staff_id = ? WHERE id = ?;", (assigned_staff_id, user_id))

            # If Student: create linked student record with unique student_id
            if target_role == "student":
                enrollment = (payload.enrollment_no or "").strip()
                if enrollment:
                    # Strict Uniqueness Enforcement for Student ID (Poka-Yoke)
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

                cursor.execute("""
                    INSERT INTO students (
                        student_id, user_id, first_name, last_name, email, phone,
                        gender, branch, academic_year, admission_date, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '1st Year', date('now'), 'Active');
                """, (enrollment, user_id, first_name, last_name, email, phone, gender, branch))
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

            # Notifications
            if target_role == "parent_guardian" and child_info and child_info["user_id"]:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, category, priority, is_read, event_key, delivery_channel)
                    VALUES (?, 'Parent Verification Request', ?, 'security', 'Important', 0, ?, 'in_app');
                """, (
                    child_info["user_id"],
                    f"{first_name} {last_name} ({email}) has requested to link as your parent/guardian. Please confirm on your dashboard.",
                    f"reg_approval:{req_id}"
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
        """Retrieve pending registrations filtered by user role permissions."""
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            user_roles = set(current_user.get("roles", []))
            
            # 1. Student view: pending parent requests targeting this student
            if "student" in user_roles and not user_roles.intersection({"super_admin", "hostel_admin", "warden"}):
                linked_s_id = current_user.get("linked_student_id")
                cursor.execute("""
                    SELECT rr.*, s.first_name as student_first_name, s.last_name as student_last_name, s.student_id as student_roll_no_display, h.name as hostel_name, h.code as hostel_code, h.hostel_type
                    FROM registration_requests rr
                    LEFT JOIN students s ON rr.linked_student_id = s.id
                    LEFT JOIN hostels h ON rr.hostel_id = h.id
                    WHERE rr.linked_student_id = ? AND rr.status = 'Pending' AND rr.student_approval_status = 'Pending'
                    ORDER BY rr.id DESC;
                """, (linked_s_id,))
                return [dict(r) for r in cursor.fetchall()]

            # 2. Warden view: can approve Students and Parents (NOT Staff)
            if user_roles.intersection({"warden", "assistant_warden"}) and not user_roles.intersection({"super_admin", "hostel_admin"}):
                cursor.execute("""
                    SELECT rr.*, s.first_name as student_first_name, s.last_name as student_last_name, s.student_id as student_roll_no_display, h.name as hostel_name, h.code as hostel_code, h.hostel_type
                    FROM registration_requests rr
                    LEFT JOIN students s ON rr.linked_student_id = s.id
                    LEFT JOIN hostels h ON rr.hostel_id = h.id
                    WHERE rr.requested_role IN ('student', 'parent_guardian')
                      AND rr.status = 'Pending'
                      AND rr.admin_warden_approval_status = 'Pending'
                    ORDER BY rr.id DESC;
                """)
                return [dict(r) for r in cursor.fetchall()]

            # 3. Super Admin & Hostel Admin: all pending registrations
            if user_roles.intersection({"super_admin", "hostel_admin"}):
                cursor.execute("""
                    SELECT rr.*, s.first_name as student_first_name, s.last_name as student_last_name, s.student_id as student_roll_no_display, h.name as hostel_name, h.code as hostel_code, h.hostel_type
                    FROM registration_requests rr
                    LEFT JOIN students s ON rr.linked_student_id = s.id
                    LEFT JOIN hostels h ON rr.hostel_id = h.id
                    WHERE rr.status = 'Pending'
                    ORDER BY rr.id DESC;
                """)
                return [dict(r) for r in cursor.fetchall()]

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
        """Process approval or rejection on a registration request according to multi-party RBAC rules."""
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

            user_roles = set(current_user.get("roles", []))
            target_role = req["requested_role"]
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # -------------------------------------------------------------
            # RULE 1: STUDENT APPROVAL ON PARENT REGISTRATION
            # -------------------------------------------------------------
            if "student" in user_roles and not user_roles.intersection({"super_admin", "hostel_admin", "warden"}):
                if target_role != "parent_guardian":
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students can only verify parent/guardian registration requests.")
                
                if current_user.get("linked_student_id") != req["linked_student_id"]:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Security Violation: You can only approve verification requests for your own parent.")

                if action_normalized == "reject":
                    cursor.execute("""
                        UPDATE registration_requests
                        SET status = 'Rejected', student_approval_status = 'Rejected',
                            student_approved_by = ?, student_approved_at = ?,
                            rejection_reason = ?, updated_at = ?
                        WHERE id = ?;
                    """, (current_user["id"], now_str, reason or "Declined by student", now_str, req_id))
                    conn.commit()
                    return {"success": True, "status": "Rejected", "message": "Parent registration request rejected."}

                # Student approves:
                cursor.execute("""
                    UPDATE registration_requests
                    SET student_approval_status = 'Approved',
                        student_approved_by = ?, student_approved_at = ?,
                        updated_at = ?
                    WHERE id = ?;
                """, (current_user["id"], now_str, now_str, req_id))

                # Check if Admin/Warden has also approved:
                if req["admin_warden_approval_status"] == "Approved":
                    cursor.execute("UPDATE registration_requests SET status = 'Approved', updated_at = ? WHERE id = ?;", (now_str, req_id))
                    cursor.execute("UPDATE users SET is_active = 1, linked_student_id = ? WHERE id = ?;", (req["linked_student_id"], req["user_id"]))
                    cursor.execute("""
                        INSERT OR IGNORE INTO guardians (name, phone, email, relationship)
                        VALUES (?, ?, ?, ?);
                    """, (f"{req['first_name']} {req['last_name']}", req["phone"], req["email"], req["relationship"] or "Parent"))
                    gid = cursor.lastrowid
                    if gid and req["linked_student_id"]:
                        cursor.execute("INSERT OR IGNORE INTO student_guardians (student_id, guardian_id, is_primary) VALUES (?, ?, 1);", (req["linked_student_id"], gid))
                    conn.commit()
                    return {"success": True, "status": "Approved", "message": "Parent verified! Both student and hostel administration approvals complete. Parent account is now Active."}
                else:
                    conn.commit()
                    return {"success": True, "status": "Pending", "message": "You have confirmed your parent! Final activation is pending Hostel Warden / Administrator approval."}

            # -------------------------------------------------------------
            # RULE 2: STAFF REGISTRATION APPROVAL (ADMIN ONLY)
            # -------------------------------------------------------------
            is_staff_role = target_role in ("staff", "maintenance_staff", "warden", "security_guard", "mess_manager", "accountant")
            if is_staff_role:
                if not user_roles.intersection({"super_admin", "hostel_admin"}):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Unauthorized: Only Administrators can approve staff member registrations."
                    )
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

                # If staff member is a warden and hostel_id was selected:
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

            # -------------------------------------------------------------
            # RULE 3: STUDENT REGISTRATION APPROVAL (ADMIN OR WARDEN)
            # -------------------------------------------------------------
            if target_role == "student":
                if not user_roles.intersection({"super_admin", "hostel_admin", "warden", "assistant_warden"}):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Wardens or Administrators can approve student registrations.")

                actor_role = "admin" if user_roles.intersection({"super_admin", "hostel_admin"}) else "warden"
                if action_normalized == "reject":
                    cursor.execute("""
                        UPDATE registration_requests
                        SET status = 'Rejected', admin_warden_approval_status = 'Rejected',
                            admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = ?,
                            rejection_reason = ?, updated_at = ?
                        WHERE id = ?;
                    """, (current_user["id"], now_str, actor_role, reason or "Rejected by Warden/Admin", now_str, req_id))
                    cursor.execute("UPDATE users SET is_active = 0 WHERE id = ?;", (req["user_id"],))
                    cursor.execute("UPDATE students SET status = 'Withdrawn' WHERE user_id = ?;", (req["user_id"],))
                    conn.commit()
                    return {"success": True, "status": "Rejected", "message": "Student registration request rejected."}

                cursor.execute("""
                    UPDATE registration_requests
                    SET status = 'Approved', admin_warden_approval_status = 'Approved',
                        admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = ?,
                        updated_at = ?
                    WHERE id = ?;
                """, (current_user["id"], now_str, actor_role, now_str, req_id))
                cursor.execute("UPDATE users SET is_active = 1 WHERE id = ?;", (req["user_id"],))
                cursor.execute("UPDATE students SET status = 'Active' WHERE user_id = ?;", (req["user_id"],))
                conn.commit()
                return {"success": True, "status": "Approved", "message": f"Student registration approved by {actor_role}! Student account is now Active."}

            # -------------------------------------------------------------
            # RULE 4: PARENT REGISTRATION APPROVAL (ADMIN OR WARDEN SIDE)
            # -------------------------------------------------------------
            if target_role == "parent_guardian":
                if not user_roles.intersection({"super_admin", "hostel_admin", "warden", "assistant_warden"}):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Wardens or Administrators can approve parent registrations.")

                actor_role = "admin" if user_roles.intersection({"super_admin", "hostel_admin"}) else "warden"
                if action_normalized == "reject":
                    cursor.execute("""
                        UPDATE registration_requests
                        SET status = 'Rejected', admin_warden_approval_status = 'Rejected',
                            admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = ?,
                            rejection_reason = ?, updated_at = ?
                        WHERE id = ?;
                    """, (current_user["id"], now_str, actor_role, reason or f"Rejected by {actor_role}", now_str, req_id))
                    conn.commit()
                    return {"success": True, "status": "Rejected", "message": "Parent registration request rejected."}

                cursor.execute("""
                    UPDATE registration_requests
                    SET admin_warden_approval_status = 'Approved',
                        admin_warden_approved_by = ?, admin_warden_approved_at = ?, admin_warden_role = ?,
                        updated_at = ?
                    WHERE id = ?;
                """, (current_user["id"], now_str, actor_role, now_str, req_id))

                # Check if student child has already approved:
                if req["student_approval_status"] == "Approved":
                    cursor.execute("UPDATE registration_requests SET status = 'Approved', updated_at = ? WHERE id = ?;", (now_str, req_id))
                    cursor.execute("UPDATE users SET is_active = 1, linked_student_id = ? WHERE id = ?;", (req["linked_student_id"], req["user_id"]))
                    cursor.execute("""
                        INSERT OR IGNORE INTO guardians (name, phone, email, relationship)
                        VALUES (?, ?, ?, ?);
                    """, (f"{req['first_name']} {req['last_name']}", req["phone"], req["email"], req["relationship"] or "Parent"))
                    gid = cursor.lastrowid
                    if gid and req["linked_student_id"]:
                        cursor.execute("INSERT OR IGNORE INTO student_guardians (student_id, guardian_id, is_primary) VALUES (?, ?, 1);", (req["linked_student_id"], gid))
                    conn.commit()
                    return {"success": True, "status": "Approved", "message": f"Parent approved by {actor_role}! Both child and {actor_role} approvals complete. Parent account is now Active."}
                else:
                    conn.commit()
                    return {"success": True, "status": "Pending", "message": f"{actor_role.capitalize()} approval recorded! Account will activate once the child student confirms."}

            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported registration request role.")
        finally:
            if should_close:
                conn.close()
