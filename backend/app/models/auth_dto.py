"""Authentication & RBAC Request/Response Data Transfer Objects (DTOs).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

import re
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


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
    # Student Profile Details
    date_of_birth: Optional[str] = Field(None, max_length=20, description="Student date of birth (YYYY-MM-DD)")
    course: Optional[str] = Field(None, max_length=50, description="Student course or program")
    academic_year: Optional[str] = Field(None, max_length=50, description="Academic year")
    semester: Optional[int] = Field(None, description="Semester number")
    permanent_address: Optional[str] = Field(None, max_length=255)
    current_address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field("India", max_length=100)
    guardian_name: Optional[str] = Field(None, max_length=100)
    guardian_relation: Optional[str] = Field(None, max_length=50)
    guardian_phone: Optional[str] = Field(None, max_length=20)
    guardian_email: Optional[str] = Field(None, max_length=100)
    emergency_contact_name: Optional[str] = Field(None, max_length=100)
    emergency_contact_phone: Optional[str] = Field(None, max_length=20)
    # Staff Profile Details
    employee_id: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=50, description="Warden, Maintenance, Security, Mess, Accounts, Faculty")
    designation: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    employment_type: Optional[str] = Field("Full-Time", max_length=50)
    date_of_joining: Optional[str] = Field(None, max_length=50)
    assigned_location: Optional[str] = Field(None, max_length=100)
    work_location: Optional[str] = Field(None, max_length=100, description="Alias for assigned_location")
    # Parent Multi-Ward & Profile Details
    child_identifiers: Optional[Union[List[str], str]] = Field(None, description="Multiple child roll numbers or emails")
    ward_identifiers: Optional[Union[List[str], str]] = Field(None, description="Alias for child_identifiers")
    ward_identifier: Optional[str] = Field(None, max_length=100, description="Alias for child_identifier")
    occupation: Optional[str] = Field(None, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def harmonize_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "work_location" in data and not data.get("assigned_location"):
                data["assigned_location"] = data["work_location"]
            elif "assigned_location" in data and not data.get("work_location"):
                data["work_location"] = data["assigned_location"]

            if "ward_identifiers" in data and not data.get("child_identifiers"):
                data["child_identifiers"] = data["ward_identifiers"]
            elif "child_identifiers" in data and not data.get("ward_identifiers"):
                data["ward_identifiers"] = data["child_identifiers"]

            if "ward_identifier" in data and not data.get("child_identifier"):
                data["child_identifier"] = data["ward_identifier"]
            elif "child_identifier" in data and not data.get("ward_identifier"):
                data["ward_identifier"] = data["child_identifier"]
        return data

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip()
        if not v:
            return None
        from datetime import datetime, date
        try:
            dob_date = datetime.strptime(v, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Invalid date_of_birth format. Must be YYYY-MM-DD.")
        today = date.today()
        if dob_date >= today:
            raise ValueError("Date of birth cannot be in the future or today.")
        age = (today - dob_date).days // 365
        if age < 14 or age > 100:
            raise ValueError(f"Age calculated from date of birth ({age} years) is outside eligible range (14-100).")
        return v

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
    role_code: Optional[str] = None
    stakeholder_category: Optional[str] = None
    can_switch_roles: Optional[bool] = False
    user_scopes: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    linked_student_id: Optional[int] = None
    linked_hostel_id: Optional[int] = None
    staff_id: Optional[str] = None
    student_id: Optional[str] = None


class SwitchRoleRequest(BaseModel):
    role: str = Field(..., min_length=2, description="Target role to switch active context to")


class SwitchRoleResponse(BaseModel):
    success: bool
    active_role: str
    role_code: Optional[str] = None
    access_token: str
    permissions: List[str]
    message: str


class AuthResponse(BaseModel):
    access_token: str
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
    token_type: str = "bearer"
    expires_in: int = 0
    user: UserProfileResponse
    requires_approval: bool = True
    requires_student_approval: bool = False
    requires_admin_warden_approval: bool = True


class RegistrationApprovalAction(BaseModel):
    action: str = Field(..., description="'approve' or 'reject'")
    reason: Optional[str] = Field(None, description="Optional rejection reason or approval remarks")
