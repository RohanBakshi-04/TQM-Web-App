"""Attendance Data Transfer Objects (DTOs) and Validation Schemas.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms)
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class AttendanceRecordCreate(BaseModel):
    """Schema for marking attendance for a single student."""
    student_id: int = Field(..., gt=0, description="Unique ID of the student")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Attendance date (YYYY-MM-DD)")
    status: str = Field("Present", description="Attendance status: Present, Absent, On Leave, Late, Not Marked")
    remarks: Optional[str] = Field("", max_length=255)


class AttendanceBulkItem(BaseModel):
    """Single student item in a bulk attendance marking payload."""
    student_id: int = Field(..., gt=0)
    status: str = Field("Present", description="Present, Absent, On Leave, Late, Not Marked")
    remarks: Optional[str] = Field("", max_length=255)


class AttendanceBulkMarkRequest(BaseModel):
    """Payload for batch attendance marking across a room, floor, or hostel."""
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    records: List[AttendanceBulkItem] = Field(..., min_items=1)
    hostel_id: Optional[int] = Field(None, gt=0)


class AttendanceCorrectionRequest(BaseModel):
    """Payload for authorized attendance status correction with mandatory audit reason."""
    new_status: str = Field(..., description="Target status: Present, Absent, On Leave, Late, Not Marked")
    reason: str = Field(..., min_length=5, max_length=500, description="Mandatory reason for audit trail")
    remarks: Optional[str] = Field("", max_length=255)


class AttendanceCorrectionResponse(BaseModel):
    """DTO for an attendance correction audit record."""
    id: int
    attendance_id: int
    student_id: int
    student_name: Optional[str] = None
    previous_status: str
    new_status: str
    reason: str
    corrected_by: int
    corrected_by_name: Optional[str] = None
    corrected_at: str


class AttendanceResponse(BaseModel):
    """DTO for a single attendance record."""
    id: int
    student_id: int
    student_name: str
    student_roll_no: str
    room_number: Optional[str] = None
    bed_code: Optional[str] = None
    hostel_name: Optional[str] = None
    hostel_id: Optional[int] = None
    date: str
    status: str
    marked_by: Optional[int] = None
    marked_by_name: Optional[str] = None
    remarks: Optional[str] = ""
    marked_at: Optional[str] = None
    created_at: Optional[str] = None


class StudentAttendanceSummary(BaseModel):
    """Summary metrics for an individual student."""
    student_id: int
    student_name: str
    student_roll_no: str
    room_number: Optional[str] = None
    total_days: int
    present_days: int
    absent_days: int
    on_leave_days: int
    attendance_percentage: float
    is_repeated_absentee: bool


class AttendanceDailySummary(BaseModel):
    """Hostel/system-wide daily attendance dashboard metrics."""
    date: str
    total_students: int
    present_students: int
    absent_students: int
    students_on_leave: int
    not_marked_students: int
    attendance_percentage: float
    repeated_absentees: List[StudentAttendanceSummary] = []
