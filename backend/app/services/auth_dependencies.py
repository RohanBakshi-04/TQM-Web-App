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
from backend.app.services.rbac_data import (
    ROLE_METADATA,
    ROLE_ALIASES,
    normalize_role_name,
    get_equivalent_permission
)
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
            norm_active = normalize_role_name(active_role)
            assigned_norms = [normalize_role_name(r) for r in roles]
            if active_role not in roles and norm_active not in assigned_norms:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: Claimed active role '{active_role}' is not assigned to this user."
                )
            active_role = norm_active if norm_active in roles else active_role
        else:
            active_role = roles[0] if roles else "student"

        # Resolve role metadata (code, category)
        cursor.execute("SELECT code, stakeholder_category FROM roles WHERE name = ?;", (active_role,))
        role_meta_row = cursor.fetchone()
        role_code = (role_meta_row["code"] if (role_meta_row and role_meta_row["code"])
                     else ROLE_METADATA.get(active_role, {}).get("code", active_role.upper()))
        role_cat = (role_meta_row["stakeholder_category"] if (role_meta_row and role_meta_row["stakeholder_category"])
                    else ROLE_METADATA.get(active_role, {}).get("category", "Operational / Student Life"))

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
        staff_roles = {
            'super_admin', 'hostel_admin', 'warden', 'assistant_warden',
            'hostel_clerk', 'accountant', 'mess_manager', 'maintenance_staff',
            'security_supervisor', 'security_guard', 'admission_officer',
            'it_admin', 'auditor'
        }
        staff_id_val = user_row["staff_id"]
        if not staff_id_val and any(r in roles for r in staff_roles):
            staff_id_val = f"STF-{user_row['id']:04d}"

        # Resolve linked hostel info if applicable
        hostel_name = None
        hostel_code = None
        hostel_type = None
        linked_hid = user_row["linked_hostel_id"]
        if not linked_hid and any(r in roles for r in ('warden', 'assistant_warden', 'hostel_clerk', 'security_supervisor')):
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

        # Resolve explicit data scope assignments
        user_scopes = []
        try:
            cursor.execute("SELECT scope_type, scope_id FROM user_scope_assignments WHERE user_id = ?;", (user_id,))
            user_scopes = [{"type": r[0], "id": r[1]} for r in cursor.fetchall()]
        except sqlite3.OperationalError:
            pass

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
            "role_code": role_code,
            "stakeholder_category": role_cat,
            "can_switch_roles": len(roles) > 1,
            "permissions": list(permissions),
            "linked_student_id": user_row["linked_student_id"],
            "linked_hostel_id": linked_hid,
            "hostel_id": linked_hid,
            "hostel_name": hostel_name,
            "hostel_code": hostel_code,
            "hostel_type": hostel_type,
            "staff_id": staff_id_val,
            "student_id": resolved_student_id,
            "user_scopes": user_scopes
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
    """Enforce that authenticated user's ACTIVE ROLE matches at least one of the specified roles.

    Accepts role names ('hostel_admin', 'warden'), canonical codes ('HOSTEL_DIRECTOR', 'CHIEF_WARDEN'),
    or aliases ('hostel_director', 'sec_supervisor').
    """
    raw_allowed = set()
    for r in allowed_roles:
        if isinstance(r, (list, tuple, set)):
            raw_allowed.update(r)
        else:
            raw_allowed.add(r)

    # Build comprehensive accepted role set
    accepted_roles = set()
    for r in raw_allowed:
        cleaned = str(r).strip()
        accepted_roles.add(cleaned)
        accepted_roles.add(cleaned.lower())
        norm = normalize_role_name(cleaned)
        accepted_roles.add(norm)
        meta = ROLE_METADATA.get(norm, {})
        if meta.get("code"):
            accepted_roles.add(meta["code"])

    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        active_role = (current_user.get("active_role") or current_user.get("role") or "").strip()
        norm_active = normalize_role_name(active_role)
        role_code = current_user.get("role_code") or norm_active.upper()

        # Super admin permission bypass applies ONLY when active_role is super_admin
        if norm_active == "super_admin" or role_code == "SUPER_ADMIN":
            return current_user

        if active_role in accepted_roles or norm_active in accepted_roles or role_code in accepted_roles:
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Required role(s): {', '.join(sorted(raw_allowed))}. Your active role: '{active_role}'."
        )
    return role_checker


def require_permissions(*required_permissions):
    """Enforce that authenticated user possesses all specified permissions via their ACTIVE ROLE.

    Supports both standardized module.resource.action and legacy module:action formats.
    """
    raw_perms = set()
    for p in required_permissions:
        if isinstance(p, (list, tuple, set)):
            raw_perms.update(p)
        else:
            raw_perms.add(p)

    def permission_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        active_role = (current_user.get("active_role") or current_user.get("role") or "").strip()
        norm_active = normalize_role_name(active_role)
        role_code = current_user.get("role_code") or norm_active.upper()

        if norm_active == "super_admin" or role_code == "SUPER_ADMIN":
            return current_user

        user_perms = set(current_user.get("permissions", []))
        missing = set()
        for p in raw_perms:
            equiv = get_equivalent_permission(p)
            if p not in user_perms and equiv not in user_perms:
                missing.add(p)

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
    - Super Admin and Hostel Director have campus-wide administrative oversight.
    - Students are isolated to their own records.
    - Parents/Guardians are isolated to their linked wards.
    - Wardens, Assistant Wardens, and Clerks must have an assigned hostel facility, the student
      must exist, and have an active room allocation in that facility.
    - IT Administrator is strictly restricted from private student personal records.
    - Accountants/Auditors must possess relevant read permissions.
    """
    s_val = str(student_id).strip()
    active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()
    norm_active = normalize_role_name(active_role)
    user_roles = {r.strip().lower() for r in current_user.get("roles", []) if r}
    if active_role:
        user_roles.add(active_role)
    if norm_active:
        user_roles.add(norm_active)
    user_perms = {p.strip().lower() for p in current_user.get("permissions", []) if p}

    # 1. Super Admin, Hostel Director, and Admission Officer: Campus-wide / Administrative oversight
    if norm_active in ("super_admin", "hostel_admin", "admission_officer"):
        return

    # 2. IT Administrator: Restricted from private student records
    if norm_active == "it_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security Violation: IT Administrator accounts are restricted from accessing student personal records."
        )

    # 3. Student Role (takes precedence if active_role is student)
    if norm_active == "student":
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

    # 4. Parent / Guardian Role
    if norm_active in ("parent_guardian", "parent"):
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

    # 5. Warden / Assistant Warden / Hostel Clerk Role
    if norm_active in ("warden", "assistant_warden", "hostel_clerk"):
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
            cursor.execute("SELECT id FROM students WHERE id = ? OR student_id = ?;", (s_val, s_val))
            st = cursor.fetchone()
            if not st:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: Student record not found or inaccessible."
                )
            db_student_id = st[0]

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

    # 6. Financial / Audit Roles
    if norm_active in ("accountant", "auditor"):
        has_perm = bool(user_perms.intersection({
            "finance:read", "audit:read", "billing:read", "reports:read",
            "finance.invoice.read", "audit.log.read"
        }))
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Active role '{active_role}' lacks required read permissions."
            )
        return

    # 7. Operational Staff Roles (Security, Maintenance, Mess)
    if norm_active in ("security_guard", "guard", "security_supervisor", "maintenance_staff", "mess_manager"):
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
