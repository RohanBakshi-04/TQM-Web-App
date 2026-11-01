"""Authentication & RBAC Request/Response Data Transfer Objects (DTOs).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username_or_email: str = Field(..., min_length=2, description="Username or email address")
    password: str = Field(..., min_length=6, description="Plaintext password")
    device_info: Optional[str] = "Web Browser"


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: str = Field(..., min_length=5, max_length=100, description="Valid email address")
    password: str = Field(..., min_length=6, max_length=100, description="Plaintext password")
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    role: str = Field("student", description="Account type: student, staff, or parent_guardian")
    enrollment_no: Optional[str] = Field(None, max_length=50)
    branch: Optional[str] = Field(None, max_length=50)
    gender: Optional[str] = Field("Male", max_length=20)
    specialization: Optional[str] = Field(None, max_length=50, description="Staff specialty: warden, electrician, plumber, maintenance, mess, security, accountant")
    child_identifier: Optional[str] = Field(None, max_length=100, description="Child's student ID, roll number, or university email (required for parent registration)")
    relationship: Optional[str] = Field("Parent / Guardian", max_length=50, description="Relationship: Father, Mother, Guardian")
    hostel_id: Optional[int] = Field(None, description="Hostel ID assigned/applied for when registering as hostel warden")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        if not v or "@" not in v:
            raise ValueError("Invalid email: must contain '@' symbol.")
        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_regex, v.strip()):
            raise ValueError("Invalid email format (e.g. name@univ.edu).")
        return v.strip().lower()

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> str:
        if not v or v not in ("Male", "Female", "Other"):
            return "Male"
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        # Strict digits-only check (Poka-Yoke)
        if not re.match(r"^\d+$", v):
            raise ValueError("Invalid phone number: only numeric digits (0-9) are allowed, no alphabets or special characters.")
        if len(v) != 10:
            raise ValueError(f"Phone number must be exactly 10 digits. Provided: {len(v)} digits.")
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty.")
        if not re.match(r"^[a-zA-Z\s'-]{1,50}$", v):
            raise ValueError("Name must only contain alphabetic letters, spaces, or hyphens.")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[a-zA-Z0-9_.-]{3,30}$", v):
            raise ValueError("Username must be between 3 and 30 characters and contain only letters, numbers, hyphens, or underscores.")
        return v

    @field_validator("enrollment_no")
    @classmethod
    def validate_enrollment_no(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip()
        if not v:
            return None
        if not re.match(r"^[a-zA-Z0-9_-]{2,30}$", v):
            raise ValueError("Enrollment / Roll number must be alphanumeric.")
        return v


class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = Field(None, description="Raw refresh token (optional if sent via cookie)")


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=5)


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=8)


class UserProfileResponse(BaseModel):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = ""
    roles: List[str]
    permissions: List[str]
    active_role: Optional[str] = None
    linked_student_id: Optional[int] = None
    linked_hostel_id: Optional[int] = None
    staff_id: Optional[str] = None
    student_id: Optional[str] = None


class SwitchRoleRequest(BaseModel):
    role: str = Field(..., min_length=2, description="Target role to switch active context to")


class SwitchRoleResponse(BaseModel):
    success: bool
    active_role: str
    access_token: str
    permissions: List[str]
    message: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800
    user: UserProfileResponse


class MessageResponse(BaseModel):
    success: bool
    message: str


class RegisterResponse(BaseModel):
    status: str = "Pending_Approval"
    message: str
    access_token: Optional[str] = ""
    refresh_token: Optional[str] = ""
    token_type: str = "bearer"
    expires_in: int = 0
    user: UserProfileResponse
    requires_approval: bool = True
    requires_student_approval: bool = False
    requires_admin_warden_approval: bool = True


class RegistrationApprovalAction(BaseModel):
    action: str = Field(..., description="'approve' or 'reject'")
    reason: Optional[str] = Field(None, description="Optional rejection reason or approval remarks")
