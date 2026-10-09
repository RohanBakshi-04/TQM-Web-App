"""Authentication and Role-Based Access Control (RBAC) Service.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException, status
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
                       is_active, failed_login_attempts, locked_until, linked_student_id, linked_hostel_id
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

            # Check if account is deactivated
            if not user["is_active"]:
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

            return {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "roles": roles,
                "permissions": list(permissions),
                "linked_student_id": user["linked_student_id"],
                "linked_hostel_id": user["linked_hostel_id"]
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
        token_payload = {
            "sub": user["username"],
            "user_id": user["id"],
            "roles": user["roles"],
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
            "expires_in": 1800, # 30 minutes in seconds
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
            cursor.execute("SELECT id, username, email, first_name, last_name, is_active, linked_student_id, linked_hostel_id FROM users WHERE id = ?;", (token_row["user_id"],))
            user = cursor.fetchone()
            if not user or not user["is_active"]:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account inactive.")

            # Generate new pair
            roles, permissions = cls.get_user_roles_and_permissions(conn, user["id"])
            user_dict = {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "roles": roles,
                "permissions": list(permissions),
                "linked_student_id": user["linked_student_id"],
                "linked_hostel_id": user["linked_hostel_id"]
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
                "expires_in": 1800,
                "user": user_dict
            }
        finally:
            if should_close:
                conn.close()

    @classmethod
    def revoke_refresh_token(cls, raw_refresh_token: str) -> bool:
        """Revoke a single refresh token during logout."""
        token_hash = hashlib.sha256(raw_refresh_token.encode("utf-8")).hexdigest()
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE refresh_tokens SET is_revoked = 1 WHERE token_hash = ?;", (token_hash,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if should_close:
                conn.close()

    @classmethod
    def change_user_password(cls, user_id: int, old_password: str, new_password: str) -> bool:
        """Change password, hash with bcrypt, and revoke all active refresh tokens."""
        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")

        conn = get_db_connection()
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
    def initiate_password_reset(cls, email: str) -> str:
        """Create a password reset token for the specified user email."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ? AND is_active = 1;", (email.strip().lower(),))
            user = cursor.fetchone()
            if not user:
                # Return dummy token or success message to prevent user enumeration
                return "reset-token-sent"

            raw_token = hashlib.sha256(f"{user['id']}-{time.time()}".encode()).hexdigest()[:32]
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

            cursor.execute("""
                INSERT INTO password_resets (user_id, reset_token_hash, expires_at)
                VALUES (?, ?, ?);
            """, (user["id"], token_hash, expires_at.isoformat()))
            conn.commit()
            return raw_token
        finally:
            if should_close:
                conn.close()

    @classmethod
    def complete_password_reset(cls, raw_token: str, new_password: str) -> bool:
        """Complete password reset using valid unexpired token."""
        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        conn = get_db_connection()
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
