"""Pydantic Data Transfer Objects for Room Allocations, Transfers & Poka-Yoke.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms)
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class AllocationCreate(BaseModel):
    student_id: Union[str, int] = Field(..., description="Student ID (e.g. STU-202611-0089) or internal database ID of the eligible student")
    bed_id: int = Field(..., description="ID of the target bed")
    start_date: str = Field(..., description="Allocation start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Expected checkout date (YYYY-MM-DD)")
    fee_status: Optional[str] = Field("Pending", description="Fee status: Paid, Pending, Overdue, Waived")
    remarks: Optional[str] = Field("", max_length=255)


class AllocationResponse(BaseModel):
    id: int
    student_id: int
    student_name: str
    student_enrollment: str
    student_gender: str
    student_branch: str
    student_academic_year: str
    bed_id: int
    bed_number: str
    room_id: int
    room_number: str
    room_type: str
    room_capacity: int
    room_base_fee: float
    floor_id: int
    floor_number: int
    floor_name: str
    building_id: int
    building_name: str
    hostel_id: int
    hostel_name: str
    hostel_code: str
    start_date: str
    end_date: Optional[str] = None
    checkin_date: Optional[str] = None
    checkout_date: Optional[str] = None
    checkout_reason: Optional[str] = None
    fee_status: str
    allocation_status: str
    approval_status: str
    remarks: Optional[str] = ""
    allocated_by: Optional[int] = None
    created_at: str


class AllocationConfirmationSlip(BaseModel):
    confirmation_number: str
    allocation_id: int
    student_name: str
    student_id: str
    hostel_name: str
    building_name: str
    floor_name: str
    room_number: str
    bed_number: str
    room_type: str
    start_date: str
    expected_checkout: Optional[str]
    fee_status: str
    allocated_at: str
    verification_hash: str


class AvailableBedItem(BaseModel):
    bed_id: int
    bed_number: str
    room_id: int
    room_number: str
    room_type: str
    capacity: int
    occupied_count: int
    available_in_room: int
    base_fee: float
    floor_id: int
    floor_number: int
    floor_name: str
    building_id: int
    building_name: str
    hostel_id: int
    hostel_name: str
    hostel_code: str
    hostel_type: str


class RoomOccupantItem(BaseModel):
    allocation_id: int
    student_id: int
    student_name: str
    student_enrollment: str
    gender: str
    branch: str
    academic_year: str
    bed_id: int
    bed_number: str
    start_date: str
    fee_status: str
    allocation_status: str


class TransferRequestCreate(BaseModel):
    to_bed_id: int = Field(..., description="Target bed ID for transfer")
    reason: str = Field(..., min_length=5, max_length=500, description="Reason for transfer request")


class TransferReview(BaseModel):
    action: str = Field(..., pattern="^(Approved|Rejected)$", description="Approved or Rejected")
    remarks: Optional[str] = Field("", max_length=255)


class CheckoutRequest(BaseModel):
    checkout_date: Optional[str] = Field(None, description="Actual checkout date (YYYY-MM-DD)")
    reason: str = Field("Academic Completion", min_length=3, max_length=255)


class CheckinRequest(BaseModel):
    checkin_date: Optional[str] = Field(None, description="Actual check-in date (YYYY-MM-DD)")


class AllocationSuggestion(BaseModel):
    bed_id: int
    bed_number: str
    room_id: int
    room_number: str
    room_type: str
    base_fee: float
    floor_number: int
    floor_name: str
    building_name: str
    hostel_id: int
    hostel_name: str
    hostel_type: str
    match_score: int
    reasons: List[str]
    existing_occupants: List[Dict[str, Any]]
