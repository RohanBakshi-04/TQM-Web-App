"""System Administration REST API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Response, status

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
    RoleCreateRequest,
    RoleUpdateRequest,
    RolePermissionsUpdate,
    AuditLogResponse,
    AuditLogListResponse
)
from backend.app.services.auth_dependencies import (
    get_current_user,
    require_roles,
    require_permissions
)
from backend.app.services.admin_service import AdminService
from backend.app.services.backup_service import BackupService

admin_router = APIRouter(prefix="/api/v1/admin", tags=["System Administration"])


# ==================== 1. SYSTEM SETTINGS ====================

@admin_router.get("/settings", response_model=List[SystemSettingItem])
def get_system_settings(
    category: Optional[str] = Query(None, description="Filter settings by category"),
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin"))
) -> List[SystemSettingItem]:
    """Retrieve system settings configurations."""
    return AdminService.get_settings(category=category)


@admin_router.put("/settings", response_model=List[SystemSettingItem])
def update_system_settings(
    payload: SystemSettingsBulkUpdate,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin"))
) -> List[SystemSettingItem]:
    """Update system settings with audit history tracking."""
    return AdminService.update_settings(payload=payload, current_user=current_user)


@admin_router.get("/settings/history", response_model=List[SystemSettingHistoryResponse])
def get_settings_change_history(
    limit: int = Query(50, ge=1, le=200, description="Max history items"),
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin", "auditor"))
) -> List[SystemSettingHistoryResponse]:
    """Inspect history of settings changes."""
    return AdminService.get_settings_history(limit=limit)


# ==================== 2. USER ADMINISTRATION ====================

@admin_router.get("/users", response_model=UserAdminListResponse)
def list_users(
    search: Optional[str] = Query(None, description="Search username, name, email"),
    role: Optional[str] = Query(None, description="Filter by assigned role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    hostel_id: Optional[int] = Query(None, description="Filter by linked hostel"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin"))
) -> UserAdminListResponse:
    """Paginated user directory with role and status filtering."""
    return AdminService.get_users(
        search=search,
        role=role,
        is_active=is_active,
        hostel_id=hostel_id,
        page=page,
        page_size=page_size
    )


@admin_router.get("/users/{user_id}", response_model=UserAdminDetail)
def get_user_detail(
    user_id: int,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin"))
) -> UserAdminDetail:
    """Fetch user profile, assigned roles, permissions, and login history."""
    return AdminService.get_user_detail(user_id=user_id)


@admin_router.put("/users/{user_id}/status", response_model=UserAdminSummary)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin"))
) -> UserAdminSummary:
    """Activate or deactivate a user account with Super Admin protection."""
    return AdminService.update_user_status(user_id=user_id, payload=payload, current_user=current_user)


@admin_router.put("/users/{user_id}/roles", response_model=UserAdminSummary)
def update_user_roles(
    user_id: int,
    payload: UserRolesUpdate,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin"))
) -> UserAdminSummary:
    """Assign or modify user roles with privilege escalation prevention."""
    return AdminService.update_user_roles(user_id=user_id, payload=payload, current_user=current_user)


@admin_router.post("/users/{user_id}/password-reset")
def admin_password_reset(
    user_id: int,
    payload: UserPasswordResetAdmin,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin"))
) -> Dict[str, Any]:
    """Initiate administrative password reset for a user account."""
    return AdminService.admin_reset_password(user_id=user_id, payload=payload, current_user=current_user)


# ==================== 3. ROLES & PERMISSIONS ====================

@admin_router.get("/roles", response_model=List[RoleDetailResponse])
def get_roles(
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin", "auditor"))
) -> List[RoleDetailResponse]:
    """List all system and custom roles with permission counts."""
    return AdminService.get_roles()


@admin_router.post("/roles", response_model=RoleDetailResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreateRequest,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin"))
) -> RoleDetailResponse:
    """Create a new custom system role with assigned permissions."""
    return AdminService.create_role(payload=payload, current_user=current_user)


@admin_router.delete("/roles/{role_id}")
def delete_role(
    role_id: int,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin"))
) -> Dict[str, Any]:
    """Delete a custom non-system role."""
    return AdminService.delete_role(role_id=role_id, current_user=current_user)


@admin_router.get("/permissions", response_model=List[PermissionResponse])
def get_permissions(
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin", "auditor"))
) -> List[PermissionResponse]:
    """List all 173 system permissions."""
    return AdminService.get_permissions()


@admin_router.put("/roles/{role_id}/permissions", response_model=RoleDetailResponse)
def update_role_permissions(
    role_id: int,
    payload: RolePermissionsUpdate,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin"))
) -> RoleDetailResponse:
    """Update permissions assigned to a role."""
    return AdminService.update_role_permissions(role_id=role_id, payload=payload, current_user=current_user)


# ==================== 4. AUDIT LOGS ====================

@admin_router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    username: Optional[str] = Query(None, description="Filter by username"),
    action: Optional[str] = Query(None, description="Filter by action code"),
    module: Optional[str] = Query(None, description="Filter by entity / module name"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="Search action, details, username"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=200, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin", "auditor"))
) -> AuditLogListResponse:
    """Search and inspect immutable audit trail logs with Q05 < 10ms SLA."""
    return AdminService.get_audit_logs(
        user_id=user_id,
        username=username,
        action=action,
        module=module,
        start_date=start_date,
        end_date=end_date,
        search=search,
        page=page,
        page_size=page_size
    )


@admin_router.get("/audit-logs/export")
def export_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action"),
    module: Optional[str] = Query(None, description="Filter by entity name"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="Search term"),
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "auditor"))
) -> Response:
    """Stream RFC 4180 CSV export of system audit trail."""
    csv_content = AdminService.export_audit_logs_csv(
        action=action,
        module=module,
        start_date=start_date,
        end_date=end_date,
        search=search
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"tqm_audit_logs_{timestamp}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"",
            "Cache-Control": "no-cache"
        }
    )


@admin_router.get("/audit-logs/{log_id}", response_model=AuditLogResponse)
def get_audit_log_detail(
    log_id: int,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin", "auditor"))
) -> AuditLogResponse:
    """Retrieve detailed metadata of single audit record."""
    return AdminService.get_audit_log_by_id(log_id=log_id)


# ==================== 5. BACKUP & RESTORE ====================

@admin_router.post("/backups")
def create_database_backup(
    note: Optional[str] = Query(None, description="Optional note for the backup"),
    current_user: Dict[str, Any] = Depends(require_roles("super_admin"))
) -> Dict[str, Any]:
    """Trigger a timestamped SQLite-safe online backup with integrity verification."""
    return BackupService.create_backup(note=note)


@admin_router.get("/backups")
def list_database_backups(
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "auditor"))
) -> List[Dict[str, Any]]:
    """List all available database backup files and their integrity status."""
    return BackupService.list_backups()


@admin_router.post("/backups/restore")
def restore_database_backup(
    backup_filename: str = Query(..., description="Backup filename to restore from"),
    current_user: Dict[str, Any] = Depends(require_roles("super_admin"))
) -> Dict[str, Any]:
    """Safely restore database from a verified backup with pre-restore safety snapshot."""
    return BackupService.restore_backup(backup_filename=backup_filename)

