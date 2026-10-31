"""Attendance API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Fast Response Time (< 10ms)
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, status

from backend.app.models.attendance_dto import (
    AttendanceRecordCreate,
    AttendanceBulkMarkRequest,
    AttendanceCorrectionRequest
)
from backend.app.services.attendance_service import AttendanceService
from backend.app.services.auth_dependencies import get_current_user

router = APIRouter(prefix="/api/v1/attendance", tags=["Attendance Management"])


@router.post("", status_code=status.HTTP_201_CREATED)
def mark_single_attendance(
    payload: AttendanceRecordCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Record daily attendance for a single resident student."""
    return AttendanceService.mark_attendance(payload, current_user)


@router.post("/bulk", status_code=status.HTTP_200_OK)
def mark_bulk_attendance(
    payload: AttendanceBulkMarkRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Batch-record attendance across an entire floor, room, or hostel."""
    return AttendanceService.bulk_mark_attendance(payload, current_user)


@router.put("/{attendance_id}", status_code=status.HTTP_200_OK)
def correct_attendance(
    attendance_id: int,
    payload: AttendanceCorrectionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Correct an existing attendance entry with a mandatory audit justification."""
    return AttendanceService.correct_attendance(attendance_id, payload, current_user)


@router.get("", status_code=status.HTTP_200_OK)
def get_attendance_records(
    date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    start_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    student_id: Optional[int] = Query(None, gt=0),
    hostel_id: Optional[int] = Query(None, gt=0),
    building_id: Optional[int] = Query(None, gt=0),
    room_id: Optional[int] = Query(None, gt=0),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve filtered, paginated attendance entries with RBAC row-level isolation."""
    filters = {
        "date": date,
        "start_date": start_date,
        "end_date": end_date,
        "student_id": student_id,
        "hostel_id": hostel_id,
        "building_id": building_id,
        "room_id": room_id,
        "status": status,
        "limit": limit,
        "offset": offset
    }
    return AttendanceService.get_attendance_records(filters, current_user)


@router.get("/summary", status_code=status.HTTP_200_OK)
def get_daily_attendance_summary(
    date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    hostel_id: Optional[int] = Query(None, gt=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Daily attendance dashboard summary with counts, percentages, and repeated absentees."""
    return AttendanceService.get_daily_summary(date, hostel_id, current_user)


@router.get("/reports", status_code=status.HTTP_200_OK)
def get_attendance_reports(
    start_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    hostel_id: Optional[int] = Query(None, gt=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Generate date-range attendance reports with percentage calculations per student."""
    return AttendanceService.get_attendance_reports(start_date, end_date, hostel_id, current_user)


@router.get("/student/{student_id}", status_code=status.HTTP_200_OK)
def get_student_attendance_history(
    student_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve complete attendance history and percentage metrics for a specific student."""
    return AttendanceService.get_student_attendance_history(student_id, current_user)


@router.get("/students-for-marking", status_code=status.HTTP_200_OK)
def get_students_for_marking(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    hostel_id: Optional[int] = Query(None, gt=0),
    building_id: Optional[int] = Query(None, gt=0),
    floor_id: Optional[int] = Query(None, gt=0),
    room_id: Optional[int] = Query(None, gt=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Fetch all active resident students in a scope for daily roll call marking."""
    return AttendanceService.get_students_for_marking(
        date, hostel_id, building_id, floor_id, room_id, current_user
    )
