"""FastAPI Authentication & RBAC Authorization Dependencies.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

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

        roles, permissions = AuthService.get_user_roles_and_permissions(conn, user_id)

        # Resolve active_role from token payload or default to primary assigned role
        active_role = payload.get("active_role")
        if not active_role or active_role not in roles:
            active_role = roles[0] if roles else "student"

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
    """Return all authorized student IDs linked to a parent/guardian user."""
    ward_ids = set()

    # 1. Check primary linked student ID on users record
    linked_sid = current_user.get("linked_student_id")
    if linked_sid:
        ward_ids.add(int(linked_sid))

    cursor = conn.cursor()

    # 2. Check student_guardians join via guardian email or phone
    user_email = (current_user.get("email") or "").strip().lower()
    user_phone = (current_user.get("phone") or "").strip()
    user_id = current_user.get("id") or current_user.get("user_id")

    if user_email or user_phone:
        cursor.execute("""
            SELECT DISTINCT sg.student_id
            FROM student_guardians sg
            JOIN guardians g ON g.id = sg.guardian_id
            WHERE (LOWER(g.email) = ? AND ? != '') OR (g.phone = ? AND ? != '');
        """, (user_email, user_email, user_phone, user_phone))
        for r in cursor.fetchall():
            ward_ids.add(r[0])

    # 3. Check registration_requests where parent was approved
    if user_id:
        cursor.execute("""
            SELECT DISTINCT linked_student_id
            FROM registration_requests
            WHERE user_id = ? AND status = 'Approved' AND linked_student_id IS NOT NULL;
        """, (user_id,))
        for r in cursor.fetchall():
            if r[0]:
                ward_ids.add(r[0])

    return sorted(list(ward_ids))


def require_roles(*allowed_roles):
    """Enforce that authenticated user belongs to at least one of the specified roles."""
    flat_roles = set()
    for r in allowed_roles:
        if isinstance(r, (list, tuple, set)):
            flat_roles.update(r)
        else:
            flat_roles.add(r)

    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        active_role = current_user.get("active_role") or current_user.get("role")
        user_roles = set(current_user.get("roles", []))
        if active_role:
            user_roles.add(active_role)

        # Super admin active role always has access
        if active_role == "super_admin" or "super_admin" in user_roles:
            return current_user

        if active_role in flat_roles or user_roles.intersection(flat_roles):
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Required role(s): {', '.join(sorted(flat_roles))}. Your active role: '{active_role}'."
        )
    return role_checker


def require_permissions(*required_permissions):
    """Enforce that authenticated user possesses all specified permissions."""
    flat_perms = set()
    for p in required_permissions:
        if isinstance(p, (list, tuple, set)):
            flat_perms.update(p)
        else:
            flat_perms.add(p)

    def permission_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_roles = set(current_user.get("roles", []))
        if current_user.get("role"):
            user_roles.add(current_user["role"])
        if "super_admin" in user_roles:
            return current_user

        user_perms = set(current_user.get("permissions", []))
        missing = flat_perms - user_perms
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Missing permission(s): {', '.join(sorted(missing))}"
            )
        return current_user
    return permission_checker


def verify_student_isolation(student_id: Union[str, int], current_user: Dict[str, Any]) -> None:
    """Enforce strict student-level and guardian-level data isolation and hostel-scoped staff oversight.

    A student must NEVER access another student's private records by changing an ID in an API request.
    Parents can only access their linked wards.
    Wardens and Assistant Wardens can only access students residing within their assigned hostel facility.
    """
    user_roles = set(current_user.get("roles", []))
    active_role = current_user.get("active_role") or current_user.get("role")
    s_val = str(student_id).strip()

    # Super Admin and global administrators have campus-wide access
    if "super_admin" in user_roles or active_role == "super_admin":
        return

    # Accountant and Auditor have read/accounting oversight
    if "accountant" in user_roles or "auditor" in user_roles:
        return

    # Hostel Warden & Assistant Warden: Must verify student belongs to warden's assigned hostel
    if "warden" in user_roles or "assistant_warden" in user_roles:
        user_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
        if user_hid:
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT bld.hostel_id
                    FROM room_allocations ra
                    JOIN rooms rm ON rm.id = ra.room_id
                    JOIN floors fl ON fl.id = rm.floor_id
                    JOIN buildings bld ON bld.id = fl.building_id
                    WHERE (ra.student_id = ? OR ra.student_id = (SELECT id FROM students WHERE student_id = ?))
                      AND ra.allocation_status = 'Active';
                """, (s_val, s_val))
                row = cursor.fetchone()
                if row and row[0] != int(user_hid):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access Denied: Student is allocated to hostel facility #{row[0]}, outside your assigned facility (#{user_hid})."
                    )
                return
            finally:
                conn.close()
        return

    # Student resident isolation check
    if "student" in user_roles or active_role == "student":
        linked_s_id = current_user.get("linked_student_id")
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

    # Parent/Guardian ward isolation check
    if "parent_guardian" in user_roles or "parent" in user_roles or active_role in ("parent_guardian", "parent"):
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

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
