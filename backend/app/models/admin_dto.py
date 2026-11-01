"""System Administration Data Transfer Objects (DTOs).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ==================== SYSTEM SETTINGS DTOs ====================

class SystemSettingItem(BaseModel):
    setting_key: str = Field(..., min_length=2, max_length=100)
    setting_value: str = Field(..., max_length=1000)
    category: str = Field("general", max_length=50)
    description: Optional[str] = Field("", max_length=255)
    is_encrypted: bool = False
    updated_at: Optional[str] = None


class SystemSettingsBulkUpdate(BaseModel):
    settings: Dict[str, str] = Field(..., description="Key-value mapping of settings to update")
    reason: Optional[str] = Field("Administrative update", max_length=255)


class SystemSettingHistoryResponse(BaseModel):
    id: int
    setting_key: str
    old_value: Optional[str] = None
    new_value: str
    changed_by: Optional[int] = None
    changed_by_name: Optional[str] = None
    reason: Optional[str] = ""
    created_at: str


# ==================== USER ADMINISTRATION DTOs ====================

class UserAdminSummary(BaseModel):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = ""
    is_active: bool
    roles: List[str] = Field(default_factory=list)
    linked_student_id: Optional[int] = None
    linked_hostel_id: Optional[int] = None
    failed_login_attempts: int = 0
    locked_until: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


class UserAdminDetail(UserAdminSummary):
    recent_logins: List[Dict[str, Any]] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)


class UserAdminListResponse(BaseModel):
    items: List[UserAdminSummary]
    total: int
    page: int
    page_size: int


class UserStatusUpdate(BaseModel):
    is_active: bool
    reason: Optional[str] = Field("Administrative status toggle", max_length=255)


class UserRolesUpdate(BaseModel):
    roles: List[str] = Field(..., min_items=1, description="List of role names to assign")
    reason: Optional[str] = Field("Role reassignment", max_length=255)


class UserPasswordResetAdmin(BaseModel):
    temporary_password: Optional[str] = Field(None, min_length=8, max_length=100)
    require_change_on_next_login: bool = True
    reason: Optional[str] = Field("Administrative password reset", max_length=255)


# ==================== ROLES & PERMISSIONS DTOs ====================

class PermissionResponse(BaseModel):
    id: int
    name: str
    module: str
    description: Optional[str] = ""
    created_at: Optional[str] = None


class RoleDetailResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = ""
    is_system: bool
    user_count: int = 0
    permissions: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None


class RolePermissionsUpdate(BaseModel):
    permission_names: List[str] = Field(..., description="Complete list of permission names to assign to role")
    reason: Optional[str] = Field("Role permissions reconfiguration", max_length=255)


# ==================== AUDIT LOGS DTOs ====================

class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: str
    action: str
    entity_name: str
    entity_id: Optional[str] = ""
    details: str
    ip_address: Optional[str] = ""
    latency_ms: Optional[float] = 0.0
    created_at: str


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
