"""FastAPI Authentication & RBAC Authorization Dependencies.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import sqlite3
from typing import Any, Dict, List, Optional, Union
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
                   linked_student_id, linked_hostel_id, staff_id, gender
            FROM users
            WHERE id = ?;
        """, (user_id,))
        user_row = cursor.fetchone()

        if not user_row or not user_row["is_active"]:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account inactive or not found.")

        roles, all_assigned_permissions = AuthService.get_user_roles_and_permissions(conn, user_id)

        # Resolve active_role from token payload or default to primary assigned role
        active_role = payload.get("active_role")
        if active_role:
            if active_role not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: Claimed active role '{active_role}' is not assigned to this user."
                )
        else:
            active_role = roles[0] if roles else "student"

        # Resolve permissions granted strictly by the ACTIVE role
        cursor.execute("""
            SELECT DISTINCT p.name
            FROM permissions p
            JOIN role_permissions rp ON p.id = rp.permission_id
            JOIN roles r ON rp.role_id = r.id
            WHERE r.name = ?;
        """, (active_role,))
        permissions = {row[0] for row in cursor.fetchall()}

        # Resolve student_id if linked to a student profile
        resolved_student_id = None
        if user_row["linked_student_id"]:
            cursor.execute("SELECT student_id FROM students WHERE id = ?;", (user_row["linked_student_id"],))
            st_row = cursor.fetchone()
            if st_row:
                resolved_student_id = st_row["student_id"] if isinstance(st_row, dict) or hasattr(st_row, 'keys') else st_row[0]

        # Resolve staff_id for any staff role
        staff_roles = {'super_admin', 'hostel_admin', 'warden', 'assistant_warden', 'accountant', 'mess_manager', 'maintenance_staff', 'security_guard', 'admission_officer', 'auditor'}
        staff_id_val = user_row["staff_id"]
        if not staff_id_val and any(r in roles for r in staff_roles):
            staff_id_val = f"STF-{user_row['id']:04d}"

        # Resolve linked hostel info if applicable
        hostel_name = None
        hostel_code = None
        hostel_type = None
        linked_hid = user_row["linked_hostel_id"]
        if not linked_hid and any(r in roles for r in ('warden', 'assistant_warden')):
            cursor.execute("SELECT id FROM hostels WHERE warden_id = ? LIMIT 1;", (user_row["id"],))
            hw = cursor.fetchone()
            if hw:
                linked_hid = hw["id"] if isinstance(hw, dict) or hasattr(hw, 'keys') else hw[0]

        if linked_hid:
            cursor.execute("SELECT name, code, hostel_type FROM hostels WHERE id = ?;", (linked_hid,))
            h_info = cursor.fetchone()
            if h_info:
                hostel_name = h_info["name"] if isinstance(h_info, dict) or hasattr(h_info, 'keys') else h_info[0]
                hostel_code = h_info["code"] if isinstance(h_info, dict) or hasattr(h_info, 'keys') else h_info[1]
                hostel_type = h_info["hostel_type"] if isinstance(h_info, dict) or hasattr(h_info, 'keys') else h_info[2]

        return {
            "id": user_row["id"],
            "user_id": user_row["id"],
            "username": user_row["username"],
            "email": user_row["email"],
            "first_name": user_row["first_name"],
            "last_name": user_row["last_name"],
            "phone": user_row["phone"],
            "gender": user_row["gender"] if "gender" in user_row.keys() else "Male",
            "roles": roles,
            "role": active_role,
            "active_role": active_role,
            "permissions": list(permissions),
            "linked_student_id": user_row["linked_student_id"],
            "linked_hostel_id": linked_hid,
            "hostel_id": linked_hid,
            "hostel_name": hostel_name,
            "hostel_code": hostel_code,
            "hostel_type": hostel_type,
            "staff_id": staff_id_val,
            "student_id": resolved_student_id
        }
    finally:
        conn.close()



def get_parent_authorized_ward_ids(conn: sqlite3.Connection, current_user: Dict[str, Any]) -> List[int]:
    """Return all authorized student IDs linked to a parent/guardian user.

    Authoritative source: parent_student_links table where parent_user_id = ? AND status = 'Active'.
    Strictly eliminates implicit access through unverified email/phone matching or user-submitted fields.
    """
    ward_ids = set()
    user_id = current_user.get("id") or current_user.get("user_id")
    if not user_id:
        return []

    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT student_id
            FROM parent_student_links
            WHERE parent_user_id = ? AND status = 'Active';
        """, (user_id,))
        for r in cursor.fetchall():
            if r[0]:
                ward_ids.add(int(r[0]))
    except sqlite3.OperationalError:
        pass

    return sorted(list(ward_ids))


def require_roles(*allowed_roles):
    """Enforce that authenticated user's ACTIVE ROLE matches at least one of the specified roles."""
    flat_roles = set()
    for r in allowed_roles:
        if isinstance(r, (list, tuple, set)):
            flat_roles.update(r)
        else:
            flat_roles.add(r)

    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        active_role = current_user.get("active_role") or current_user.get("role")

        # Super admin permission bypass applies ONLY when active_role is super_admin
        if active_role == "super_admin":
            return current_user

        if active_role in flat_roles:
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Required role(s): {', '.join(sorted(flat_roles))}. Your active role: '{active_role}'."
        )
    return role_checker


def require_permissions(*required_permissions):
    """Enforce that authenticated user possesses all specified permissions via their ACTIVE ROLE."""
    flat_perms = set()
    for p in required_permissions:
        if isinstance(p, (list, tuple, set)):
            flat_perms.update(p)
        else:
            flat_perms.add(p)

    def permission_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        active_role = current_user.get("active_role") or current_user.get("role")
        if active_role == "super_admin":
            return current_user

        user_perms = set(current_user.get("permissions", []))
        missing = flat_perms - user_perms
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Missing permission(s): {', '.join(sorted(missing))} for active role '{active_role}'."
            )
        return current_user
    return permission_checker


def verify_student_isolation(student_id: Union[str, int], current_user: Dict[str, Any]) -> None:
    """Enforce strict student-level and guardian-level data isolation and hostel-scoped staff oversight.

    - Active role takes absolute precedence.
    - Super Admin has campus-wide oversight.
    - Students are isolated to their own records.
    - Parents/Guardians are isolated to their linked wards.
    - Wardens and Assistant Wardens MUST have an assigned hostel facility, the student MUST exist,
      and the student MUST have an active room allocation in the warden's assigned facility.
    - Accountants/Auditors must possess relevant read permissions.
    """
    s_val = str(student_id).strip()
    active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()
    user_roles = {r.strip().lower() for r in current_user.get("roles", []) if r}
    if active_role:
        user_roles.add(active_role)
    user_perms = {p.strip().lower() for p in current_user.get("permissions", []) if p}

    # 1. Super Admin and Hostel Admin: Campus-wide / Administrative oversight
    if active_role in ("super_admin", "hostel_admin"):
        return

    # 2. Student Role (takes precedence if active_role is student)
    if active_role == "student":
        linked_s_id = current_user.get("linked_student_id")
        if linked_s_id is None and current_user.get("user_id"):
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM students WHERE user_id = ?;", (current_user["user_id"],))
                st_row = cursor.fetchone()
                if st_row:
                    linked_s_id = st_row[0]
            finally:
                conn.close()
        user_student_id = current_user.get("student_id")
        is_match = False
        if linked_s_id is not None and str(linked_s_id) == s_val:
            is_match = True
        elif user_student_id and user_student_id.strip().upper() == s_val.upper():
            is_match = True

        if not is_match:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security Violation: You are not authorized to access another student's private records."
            )
        return

    # 3. Parent / Guardian Role
    if active_role in ("parent_guardian", "parent"):
        conn = get_db_connection()
        try:
            wards = get_parent_authorized_ward_ids(conn, current_user)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM students WHERE id = ? OR student_id = ?;", (s_val, s_val))
            st_row = cursor.fetchone()
            target_id = st_row[0] if st_row else None

            if not target_id or target_id not in wards:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Security Violation: You are not authorized to view this student's records."
                )
            return
        finally:
            conn.close()

    # 4. Warden / Assistant Warden Role
    if active_role in ("warden", "assistant_warden"):
        user_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
        if not user_hid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Staff member has no assigned hostel facility."
            )

        try:
            user_hid_int = int(user_hid)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Staff member has an invalid assigned hostel facility."
            )

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Verify student existence
            cursor.execute("SELECT id FROM students WHERE id = ? OR student_id = ?;", (s_val, s_val))
            st = cursor.fetchone()
            if not st:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: Student record not found or inaccessible."
                )
            db_student_id = st[0]

            # Verify active room allocation in the assigned hostel facility
            cursor.execute("""
                SELECT bld.hostel_id
                FROM room_allocations ra
                JOIN rooms rm ON rm.id = ra.room_id
                JOIN floors fl ON fl.id = rm.floor_id
                JOIN buildings bld ON bld.id = fl.building_id
                WHERE ra.student_id = ? AND ra.allocation_status = 'Active';
            """, (db_student_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: Student has no active room allocation in your assigned hostel."
                )

            if row[0] != user_hid_int:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access Denied: Student is allocated to hostel facility #{row[0]}, outside your assigned facility (#{user_hid_int})."
                )
            return
        finally:
            conn.close()

    # 5. Financial / Audit Roles
    if active_role in ("accountant", "auditor"):
        has_perm = bool(user_perms.intersection({"finance:read", "audit:read", "billing:read", "reports:read"}))
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Active role '{active_role}' lacks required read permissions."
            )
        return

    # 6. Operational Staff Roles (Security, Maintenance, Mess)
    if active_role in ("security_guard", "guard", "maintenance_staff", "mess_manager"):
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
