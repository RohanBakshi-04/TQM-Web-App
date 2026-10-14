"""FastAPI Authentication & RBAC Authorization Dependencies.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

from typing import Any, Dict, List, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from backend.app.database.connection import get_db_connection
from backend.app.services.auth_service import AuthService
from backend.app.services.security import decode_access_token

security = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """Retrieve and validate the authenticated user from Bearer token."""
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(token)
    if not payload or "user_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload["user_id"]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, email, first_name, last_name, phone, is_active,
                   linked_student_id, linked_hostel_id
            FROM users
            WHERE id = ?;
        """, (user_id,))
        user_row = cursor.fetchone()

        if not user_row or not user_row["is_active"]:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account inactive or not found.")

        roles, permissions = AuthService.get_user_roles_and_permissions(conn, user_id)

        return {
            "id": user_row["id"],
            "username": user_row["username"],
            "email": user_row["email"],
            "first_name": user_row["first_name"],
            "last_name": user_row["last_name"],
            "phone": user_row["phone"],
            "roles": roles,
            "permissions": list(permissions),
            "linked_student_id": user_row["linked_student_id"],
            "linked_hostel_id": user_row["linked_hostel_id"]
        }
    finally:
        conn.close()


def require_roles(*allowed_roles: str):
    """Enforce that authenticated user belongs to at least one of the specified roles."""
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_roles = set(current_user.get("roles", []))
        # Super admin always has access
        if "super_admin" in user_roles:
            return current_user

        if not user_roles.intersection(set(allowed_roles)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(allowed_roles)}. Your role(s): {', '.join(user_roles)}"
            )
        return current_user
    return role_checker


def require_permissions(*required_permissions: str):
    """Enforce that authenticated user possesses all specified permissions."""
    def permission_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_roles = set(current_user.get("roles", []))
        if "super_admin" in user_roles:
            return current_user

        user_perms = set(current_user.get("permissions", []))
        missing = set(required_permissions) - user_perms
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Missing permission(s): {', '.join(missing)}"
            )
        return current_user
    return permission_checker


def verify_student_isolation(student_id: int, current_user: Dict[str, Any]) -> None:
    """Enforce strict student-level and guardian-level data isolation.

    A student must NEVER access another student's private records by changing an ID in an API request.
    """
    user_roles = set(current_user.get("roles", []))

    # Super Admin, Hostel Admin, Warden, Assistant Warden, and Accountant have oversight
    privileged_roles = {"super_admin", "hostel_admin", "warden", "assistant_warden", "accountant", "auditor"}
    if user_roles.intersection(privileged_roles):
        return

    # Student can only access their own linked record
    if "student" in user_roles:
        linked_s_id = current_user.get("linked_student_id")
        if linked_s_id is None or int(linked_s_id) != int(student_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security Violation: You are not authorized to access another student's private records."
            )
        return

    # Parent/Guardian can only access their linked ward
    if "parent_guardian" in user_roles:
        linked_s_id = current_user.get("linked_student_id")
        if linked_s_id is None or int(linked_s_id) != int(student_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security Violation: You are not authorized to view this student's records."
            )
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
