"""Visitor Management Data Transfer Objects (DTOs) and Validation Schemas.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms)
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class VisitorRegistrationRequest(BaseModel):
    """Payload for registering a new campus visitor and logging their visit."""
    name: str = Field(..., min_length=2, max_length=100, description="Visitor's full legal name")
    phone: str = Field(..., min_length=7, max_length=20, description="Contact phone number")
    id_proof_type: str = Field("Aadhaar", description="Aadhaar, Passport, Driving_License, Voter_ID, Other")
    id_proof_number: str = Field(..., min_length=4, max_length=50, description="Government identity document number")
    address: Optional[str] = Field("", max_length=255)
    student_id: int = Field(..., gt=0, description="Hostel resident student being visited")
    hostel_id: Optional[int] = Field(None, gt=0)
    room_id: Optional[int] = Field(None, gt=0)
    purpose: str = Field(..., min_length=3, max_length=255, description="Purpose of the visit")
    expected_exit_time: Optional[str] = Field(None, description="Expected exit timestamp (YYYY-MM-DD HH:MM)")
    immediate_checkin: bool = Field(True, description="Immediately check in upon registration at gate")


class VisitorApprovalRequest(BaseModel):
    """Payload for warden approving a pending visitor pass."""
    remarks: Optional[str] = Field("", max_length=255)


class VisitorRejectionRequest(BaseModel):
    """Payload for rejecting a visitor entry request with mandatory reason."""
    reason: str = Field(..., min_length=5, max_length=500, description="Mandatory justification for denying entry")


class VisitorCheckInRequest(BaseModel):
    """Payload for logging visitor arrival and gate ingress."""
    expected_exit_time: Optional[str] = Field(None)
    remarks: Optional[str] = Field("", max_length=255)


class VisitorCheckOutRequest(BaseModel):
    """Payload for logging visitor departure and gate egress."""
    remarks: Optional[str] = Field("", max_length=255)


class VisitorResponse(BaseModel):
    """Secure DTO for a visitor entry log (masks identity document for unauthorized users)."""
    id: int
    pass_number: str
    visitor_id: int
    name: str
    phone: str
    id_proof_type: str
    id_proof_number: str
    student_id: int
    student_name: str
    student_roll_no: str
    hostel_id: Optional[int] = None
    hostel_name: Optional[str] = None
    room_number: Optional[str] = None
    purpose: str
    approval_status: str
    status: str
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    expected_exit_time: Optional[str] = None
    is_overdue: bool = False
    approved_by: Optional[int] = None
    approved_by_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    remarks: Optional[str] = ""
    created_at: str
