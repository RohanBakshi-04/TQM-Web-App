from backend.app.config import settings
from backend.app.services.security import create_access_token, create_refresh_token
"""Authentication and RBAC API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.app.database.connection import get_db_connection
from backend.app.models.auth_dto import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    RegistrationApprovalAction,
    MessageResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    UserProfileResponse,
    SwitchRoleRequest,
    SwitchRoleResponse
)
from backend.app.services.auth_dependencies import (
    get_current_user,
    require_roles,
    require_permissions,
    verify_student_isolation
)
from backend.app.services.auth_service import AuthService
from backend.app.services.rbac_data import ROLES_LIST

router = APIRouter(prefix="/api/v1", tags=["Authentication & RBAC"])


def get_client_ip_and_ua(request: Request) -> tuple[str, str]:
    """Helper to extract remote client IP and User-Agent."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    elif request.client and request.client.host:
        ip = request.client.host
    else:
        ip = "127.0.0.1"
    ua = request.headers.get("User-Agent", "Unknown-Client")
    return ip, ua


@router.post("/auth/login", response_model=AuthResponse)
def login(login_dto: LoginRequest, request: Request, response: Response) -> Dict[str, Any]:
    """Authenticate with username/email and password, issue token pair, and set HttpOnly cookie."""
    ip, ua = get_client_ip_and_ua(request)
    device = login_dto.device_info or ua

    user = AuthService.authenticate_user(
        username_or_email=login_dto.username_or_email,
        password=login_dto.password,
        ip_address=ip,
        user_agent=ua
    )

    token_data = AuthService.issue_token_pair(
        user=user,
        ip_address=ip,
        device_info=device
    )

    # Set secure HttpOnly cookie for refresh token rotation
    raw_refresh = token_data.pop("refresh_token", None)
    if raw_refresh:
        response.set_cookie(
            key="refresh_token",
            value=raw_refresh,
            httponly=True,
            secure=(settings.app_env == "production"),
            samesite="lax",
            max_age=settings.refresh_token_expire_days * 24 * 3600
        )

    return token_data


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(register_dto: RegisterRequest, request: Request, response: Response) -> Dict[str, Any]:
    """Register a new user account (Student, Staff, or Parent) requiring multi-party role approval."""
    ip, ua = get_client_ip_and_ua(request)
    auth_data = AuthService.register_user(register_dto, ip, ua)

    raw_refresh = auth_data.pop("refresh_token", None)
    if raw_refresh:
        response.set_cookie(
            key="refresh_token",
            value=raw_refresh,
            httponly=True,
            secure=(settings.app_env == "production"),
            samesite="lax",
            max_age=settings.refresh_token_expire_days * 24 * 3600
        )
    return auth_data


@router.post("/auth/refresh", response_model=AuthResponse)
def refresh_token(
    request: Request,
    response: Response,
    dto: Optional[RefreshTokenRequest] = None
) -> Dict[str, Any]:
    """Exchange unexpired refresh token for new access and refresh token pair."""
    ip, ua = get_client_ip_and_ua(request)
    raw_token = None
    if dto and dto.refresh_token:
        raw_token = dto.refresh_token
    elif "refresh_token" in request.cookies:
        raw_token = request.cookies.get("refresh_token")

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing from request body or cookie."
        )

    token_data = AuthService.rotate_refresh_token(
        raw_refresh_token=raw_token,
        ip_address=ip,
        device_info=ua
    )

    raw_new_refresh = token_data.pop("refresh_token", None)
    if raw_new_refresh:
        response.set_cookie(
            key="refresh_token",
            value=raw_new_refresh,
            httponly=True,
            secure=(settings.app_env == "production"),
            samesite="lax",
            max_age=settings.refresh_token_expire_days * 24 * 3600
        )

    return token_data


@router.post("/auth/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    dto: Optional[RefreshTokenRequest] = None
) -> Dict[str, Any]:
    """Revoke refresh token and clear session cookies."""
    raw_token = None
    if dto and dto.refresh_token:
        raw_token = dto.refresh_token
    elif "refresh_token" in request.cookies:
        raw_token = request.cookies.get("refresh_token")

    if raw_token:
        AuthService.revoke_refresh_token(raw_token)

    response.delete_cookie(key="refresh_token", httponly=True, secure=(settings.app_env == "production"), samesite="lax")
    return {"success": True, "message": "Successfully logged out. Refresh token revoked."}



@router.post("/auth/switch-role", response_model=SwitchRoleResponse)
def switch_role(
    dto: SwitchRoleRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Validate and switch active role for multi-role accounts with audit logging."""
    ip, ua = get_client_ip_and_ua(request)
    return AuthService.switch_user_role(
        user_id=current_user["id"],
        target_role=dto.role,
        ip_address=ip,
        user_agent=ua
    )


@router.get("/auth/authorized-hostels", response_model=List[Dict[str, Any]])
def get_authorized_hostels() -> List[Dict[str, Any]]:
    """Retrieve authorized active hostels and their real-time warden capacities."""
    return AuthService.get_authorized_hostels()


@router.get("/auth/me", response_model=UserProfileResponse)
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Return currently authenticated user profile, roles, and resolved permissions."""
    return current_user


@router.post("/auth/change-password")
def change_password(
    dto: ChangePasswordRequest,
    response: Response,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Change current user's password, rehash with bcrypt, and issue fresh access token for continuous login."""
    AuthService.change_user_password(
        user_id=current_user["id"],
        old_password=dto.current_password,
        new_password=dto.new_password
    )
    # Generate fresh access token and refresh token
    token_payload = {
        "sub": current_user["username"],
        "user_id": current_user["id"],
        "roles": current_user.get("roles", []),
        "active_role": current_user.get("role"),
        "linked_student_id": current_user.get("linked_student_id"),
        "linked_hostel_id": current_user.get("linked_hostel_id")
    }
    new_access_token = create_access_token(token_payload)
    raw_refresh, token_hash, exp_dt = create_refresh_token(current_user["id"])
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO refresh_tokens (user_id, token_hash, expires_at, is_revoked) VALUES (?, ?, ?, 0);",
                    (current_user["id"], token_hash, exp_dt.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    finally:
        conn.close()

    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=(settings.app_env == "production"),
        samesite="lax",
        max_age=7 * 86400
    )
    return {
        "success": True,
        "message": "Password changed successfully. Your security credentials have been updated.",
        "access_token": new_access_token,
        "token_type": "bearer"
    }


@router.post("/auth/forgot-password")
def forgot_password(dto: ForgotPasswordRequest) -> Dict[str, Any]:
    """Initiate self-service password reset."""
    result = AuthService.initiate_password_reset(dto.email)
    response_payload = {
        "success": True,
        "message": result.get("message", "If an account with that email exists, password reset instructions have been generated.")
    }
    # In non-production testing/dev mode, expose dev token for automated tests
    if settings.app_env != "production" and result.get("dev_token"):
        response_payload["dev_token"] = result["dev_token"]
        response_payload["reset_token"] = result["dev_token"]
    return response_payload


@router.post("/auth/reset-password", response_model=MessageResponse)
def reset_password(dto: ResetPasswordRequest) -> Dict[str, Any]:
    """Complete password reset using valid unexpired token."""
    AuthService.complete_password_reset(dto.reset_token, dto.new_password)
    return {"success": True, "message": "Password reset successfully. Please log in with your new credentials."}


@router.get("/roles")
def list_system_roles() -> List[Dict[str, Any]]:
    """Return the complete directory of 12 system roles."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, is_system FROM roles ORDER BY id ASC;")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/permissions")
def list_system_permissions(current_user: Dict[str, Any] = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """Return all available permissions in the system."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, module, action, description FROM permissions ORDER BY module, action ASC;")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/users")
def list_system_users(
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin"))
) -> List[Dict[str, Any]]:
    """List system users with their assigned roles (restricted to Super Admin & Hostel Admin)."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.is_active,
                   u.failed_login_attempts, u.locked_until, u.linked_student_id, u.linked_hostel_id, u.staff_id,
                   GROUP_CONCAT(r.name) as role_names
            FROM users u
            LEFT JOIN user_roles ur ON u.id = ur.user_id
            LEFT JOIN roles r ON ur.role_id = r.id
            GROUP BY u.id
            ORDER BY u.id ASC;
        """)
        users = []
        for row in cursor.fetchall():
            u = dict(row)
            u["roles"] = u["role_names"].split(",") if u["role_names"] else []
            del u["role_names"]
            users.append(u)
        return users
    finally:
        conn.close()


@router.get("/students/{student_id}/profile")
def get_student_profile(
    student_id: Union[str, int],
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Retrieve student profile with strict student data isolation enforcement.
    
    A student attempting to access another student's record triggers HTTP 403 Forbidden.
    """
    verify_student_isolation(student_id=student_id, current_user=current_user)

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        raw_key = str(student_id).strip()
        cursor.execute("""
            SELECT s.id, s.student_id, s.first_name, s.last_name, s.email, s.phone,
                   s.date_of_birth, s.gender, s.blood_group, s.branch, s.academic_year,
                   s.semester, s.status, s.admission_date, s.address
            FROM students s
            WHERE UPPER(TRIM(s.student_id)) = UPPER(?);
        """, (raw_key,))
        student = cursor.fetchone()
        if not student and raw_key.isdigit():
            cursor.execute("""
                SELECT s.id, s.student_id, s.first_name, s.last_name, s.email, s.phone,
                       s.date_of_birth, s.gender, s.blood_group, s.branch, s.academic_year,
                       s.semester, s.status, s.admission_date, s.address
                FROM students s
                WHERE s.id = ?;
            """, (int(raw_key),))
            student = cursor.fetchone()
        if not student:
            raise HTTPException(status_code=404, detail=f"Student record '{student_id}' not found.")

        # Also fetch active room allocation if any
        cursor.execute("""
            SELECT ra.id as allocation_id, ra.start_date, ra.allocation_status,
                   b.bed_number, r.room_number, r.room_type, fl.floor_number, bl.name as building_name,
                   bl.hostel_id as hostel_id, h.name as hostel_name, h.code as hostel_code
            FROM room_allocations ra
            JOIN beds b ON ra.bed_id = b.id
            JOIN rooms r ON b.room_id = r.id
            JOIN floors fl ON r.floor_id = fl.id
            JOIN buildings bl ON fl.building_id = bl.id
            JOIN hostels h ON bl.hostel_id = h.id
            WHERE ra.student_id = ? AND ra.allocation_status = 'Active'
            LIMIT 1;
        """, (student["id"],))
        alloc = cursor.fetchone()

        result = dict(student)
        if alloc:
            alloc_dict = dict(alloc)
            # Query assigned wardens for this hostel
            cursor.execute("""
                SELECT u.id, u.staff_id, u.first_name || ' ' || u.last_name as full_name,
                       u.email, u.phone, r.name as role_name
                FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                JOIN roles r ON ur.role_id = r.id
                WHERE u.linked_hostel_id = ? AND r.name IN ('warden', 'assistant_warden') AND u.is_active = 1
                ORDER BY r.name DESC;
            """, (alloc["hostel_id"],))
            alloc_dict["wardens"] = [dict(w) for w in cursor.fetchall()]
            result["allocation"] = alloc_dict
        else:
            result["allocation"] = None
        return result
    finally:
        conn.close()



@router.get("/registrations/pending", response_model=List[Dict[str, Any]])
def get_pending_registrations(current_user: Dict[str, Any] = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """Retrieve pending user registration requests filtered by role permissions."""
    return AuthService.get_pending_registrations(current_user)


@router.post("/registrations/{id}/action")
def process_registration_action(
    id: int,
    payload: RegistrationApprovalAction,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Approve or reject a registration request according to multi-party RBAC rules."""
    return AuthService.process_registration_action(id, payload.action, payload.reason, current_user)
