"""Authentication & RBAC Request/Response Data Transfer Objects (DTOs).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username_or_email: str = Field(..., min_length=2, description="Username or email address")
    password: str = Field(..., min_length=6, description="Plaintext password")
    device_info: Optional[str] = "Web Browser"


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
    roles: List[str]
    permissions: List[str]
    linked_student_id: Optional[int] = None
    linked_hostel_id: Optional[int] = None


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800
    user: UserProfileResponse


class MessageResponse(BaseModel):
    success: bool
    message: str
