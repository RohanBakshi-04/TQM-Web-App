"""Leave Application and Gate Outpass Data Transfer Objects (DTOs).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms)
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class LeaveApplicationCreate(BaseModel):
    """Payload for submitting a new student leave application."""
    leave_type: str = Field(..., description="Home Leave, Personal Leave, Medical Leave, Emergency Leave, Other")
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Departure date (YYYY-MM-DD)")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Expected return date (YYYY-MM-DD)")
    departure_time: Optional[str] = Field(None, description="Expected departure time (HH:MM or ISO)")
    expected_return_time: Optional[str] = Field(None, description="Expected return time (HH:MM or ISO)")
    reason: str = Field(..., min_length=5, max_length=500)
    destination: str = Field(..., min_length=2, max_length=200)
    emergency_contact: str = Field(..., min_length=7, max_length=20)
    guardian_contact: Optional[str] = Field(None, max_length=20)
    document_url: Optional[str] = Field(None, max_length=500)
    is_draft: bool = Field(False, description="Save as Draft or submit immediately")


class LeaveApplicationUpdate(BaseModel):
    """Payload for updating an existing leave application (allowed when in Draft or Submitted)."""
    leave_type: Optional[str] = None
    start_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    departure_time: Optional[str] = None
    expected_return_time: Optional[str] = None
    reason: Optional[str] = None
    destination: Optional[str] = None
    emergency_contact: Optional[str] = None
    guardian_contact: Optional[str] = None
    document_url: Optional[str] = None
    submit_now: Optional[bool] = False


class LeaveApprovalRequest(BaseModel):
    """Payload for approving a leave application."""
    remarks: Optional[str] = Field("", max_length=255)


class LeaveRejectionRequest(BaseModel):
    """Payload for rejecting a leave application with mandatory reason."""
    reason: str = Field(..., min_length=5, max_length=500, description="Mandatory justification for leave denial")


class OutpassVerificationRequest(BaseModel):
    """Payload for security gate exit or return recording."""
    remarks: Optional[str] = Field("", max_length=255)


class OutpassResponse(BaseModel):
    """DTO for an issued gate outpass."""
    id: int
    outpass_number: str
    leave_request_id: int
    student_id: int
    student_name: str
    student_roll_no: str
    room_number: Optional[str] = None
    hostel_name: Optional[str] = None
    status: str
    expected_exit_time: str
    expected_return_time: str
    actual_exit_time: Optional[str] = None
    actual_return_time: Optional[str] = None
    exit_verified_by: Optional[int] = None
    exit_verified_by_name: Optional[str] = None
    return_verified_by: Optional[int] = None
    return_verified_by_name: Optional[str] = None
    exit_remarks: Optional[str] = ""
    return_remarks: Optional[str] = ""
    is_overdue: bool = False
    created_at: str


class LeaveResponse(BaseModel):
    """Comprehensive DTO for a student leave application and attached outpass."""
    id: int
    student_id: int
    student_name: str
    student_roll_no: str
    room_number: Optional[str] = None
    hostel_name: Optional[str] = None
    hostel_id: Optional[int] = None
    leave_type: str
    start_date: str
    end_date: str
    departure_time: Optional[str] = None
    expected_return_time: Optional[str] = None
    reason: str
    destination: str
    emergency_contact: str
    guardian_contact: Optional[str] = None
    document_url: Optional[str] = None
    status: str
    approved_by: Optional[int] = None
    approved_by_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[str] = None
    remarks: Optional[str] = ""
    outpass: Optional[OutpassResponse] = None
    created_at: str
