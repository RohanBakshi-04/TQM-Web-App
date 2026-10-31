"""Complaint and Grievance Management REST API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from backend.app.database.connection import get_db_connection
from backend.app.models.complaint_dto import (
    ComplaintAssign,
    ComplaintClose,
    ComplaintCommentAdd,
    ComplaintCreate,
    ComplaintEscalate,
    ComplaintFeedback,
    ComplaintReject,
    ComplaintReopen,
)
from backend.app.services.auth_dependencies import get_current_user, require_roles
from backend.app.services.complaint_service import ComplaintService

router = APIRouter(prefix="/api/v1/complaints", tags=["Complaint Management"])


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_complaint(
    data: ComplaintCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Submit a new student complaint/grievance."""
    student_id = current_user.get("linked_student_id")
    if not student_id:
        # If user is admin/staff testing or student without linked id, resolve from user_id or default student
        student_id = current_user.get("user_id")

    conn = get_db_connection()
    try:
        return ComplaintService.submit_complaint(
            conn=conn,
            student_id=student_id,
            data=data,
            submitted_by_user_id=current_user.get("user_id")
        )
    finally:
        conn.close()


@router.get("/my", response_model=List[Dict[str, Any]])
def get_my_complaints(
    status_filter: Optional[str] = Query(None, description="Optional status filter"),
    category: Optional[str] = Query(None, description="Optional category filter"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Retrieve all complaints submitted by the authenticated student."""
    student_id = current_user.get("linked_student_id") or current_user.get("user_id")
    conn = get_db_connection()
    try:
        return ComplaintService.get_student_complaints(
            conn=conn,
            student_id=student_id,
            status_filter=status_filter,
            category=category
        )
    finally:
        conn.close()


@router.get("/{complaint_id}")
def get_complaint_details(
    complaint_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Retrieve complete complaint record with update history and linked task."""
    roles = set(current_user.get("roles", []))
    is_student_only = "student" in roles and not roles.intersection({"super_admin", "hostel_admin", "warden", "assistant_warden", "maintenance_staff", "auditor"})

    student_restriction = current_user.get("linked_student_id") if is_student_only else None

    conn = get_db_connection()
    try:
        return ComplaintService.get_complaint_by_id(
            conn=conn,
            complaint_id=complaint_id,
            student_id_restriction=student_restriction
        )
    finally:
        conn.close()


@router.post("/{complaint_id}/comments")
def add_complaint_comment(
    complaint_id: int,
    data: ComplaintCommentAdd,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Add a query or update comment to an existing complaint."""
    roles = set(current_user.get("roles", []))
    is_student_only = "student" in roles and not roles.intersection({"super_admin", "hostel_admin", "warden", "assistant_warden", "maintenance_staff"})
    student_restriction = current_user.get("linked_student_id") if is_student_only else None

    conn = get_db_connection()
    try:
        return ComplaintService.add_comment(
            conn=conn,
            complaint_id=complaint_id,
            user_id=current_user.get("user_id", 1),
            comment=data.comment,
            student_id_restriction=student_restriction
        )
    finally:
        conn.close()


@router.post("/{complaint_id}/reopen")
def reopen_resolved_complaint(
    complaint_id: int,
    data: ComplaintReopen,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Reopen a resolved or closed complaint if the issue persists."""
    student_id = current_user.get("linked_student_id") or current_user.get("user_id")
    conn = get_db_connection()
    try:
        return ComplaintService.reopen_complaint(
            conn=conn,
            complaint_id=complaint_id,
            student_id=student_id,
            data=data,
            user_id=current_user.get("user_id", 1)
        )
    finally:
        conn.close()


@router.post("/{complaint_id}/feedback")
def submit_complaint_feedback(
    complaint_id: int,
    data: ComplaintFeedback,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Submit post-resolution satisfaction feedback rating (1-5 stars) and comment."""
    student_id = current_user.get("linked_student_id") or current_user.get("user_id")
    conn = get_db_connection()
    try:
        return ComplaintService.submit_feedback(
            conn=conn,
            complaint_id=complaint_id,
            student_id=student_id,
            data=data
        )
    finally:
        conn.close()


@router.get("", response_model=Dict[str, Any])
def list_all_complaints(
    hostel_id: Optional[int] = Query(None, description="Filter by hostel ID"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    search: Optional[str] = Query(None, description="Search keyword across complaints/students"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_roles(["super_admin", "hostel_admin", "warden", "assistant_warden", "maintenance_staff", "auditor"]))
) -> Dict[str, Any]:
    """Warden and Admin overview of student grievances with filtering and search."""
    conn = get_db_connection()
    try:
        return ComplaintService.get_complaints_list(
            conn=conn,
            hostel_id=hostel_id,
            status_filter=status_filter,
            category=category,
            severity=severity,
            search=search,
            page=page,
            page_size=page_size
        )
    finally:
        conn.close()


@router.get("/analytics", response_model=Dict[str, Any])
def get_complaint_analytics(
    hostel_id: Optional[int] = Query(None, description="Filter by hostel"),
    current_user: Dict[str, Any] = Depends(require_roles(["super_admin", "hostel_admin", "warden", "assistant_warden", "auditor"]))
) -> Dict[str, Any]:
    """Retrieve statistical complaint counts and performance KPIs."""
    conn = get_db_connection()
    try:
        return ComplaintService.get_complaint_analytics(conn=conn, hostel_id=hostel_id)
    finally:
        conn.close()


@router.post("/{complaint_id}/assign")
def assign_complaint(
    complaint_id: int,
    data: ComplaintAssign,
    current_user: Dict[str, Any] = Depends(require_roles(["super_admin", "hostel_admin", "warden", "assistant_warden"]))
) -> Dict[str, Any]:
    """Warden assigns complaint to a technician with room/bed lock and work-order generation."""
    conn = get_db_connection()
    try:
        return ComplaintService.assign_complaint(
            conn=conn,
            complaint_id=complaint_id,
            user_id=current_user.get("user_id", 1),
            data=data
        )
    finally:
        conn.close()


@router.post("/{complaint_id}/escalate")
def escalate_complaint(
    complaint_id: int,
    data: ComplaintEscalate,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Escalate urgent grievance to senior administration with broadcast notifications."""
    conn = get_db_connection()
    try:
        return ComplaintService.escalate_complaint(
            conn=conn,
            complaint_id=complaint_id,
            user_id=current_user.get("user_id", 1),
            reason=data.reason
        )
    finally:
        conn.close()


@router.post("/{complaint_id}/reject")
def reject_complaint(
    complaint_id: int,
    data: ComplaintReject,
    current_user: Dict[str, Any] = Depends(require_roles(["super_admin", "hostel_admin", "warden", "assistant_warden"]))
) -> Dict[str, Any]:
    """Warden rejects non-actionable complaint with mandatory rationale."""
    conn = get_db_connection()
    try:
        return ComplaintService.reject_complaint(
            conn=conn,
            complaint_id=complaint_id,
            user_id=current_user.get("user_id", 1),
            reason=data.reason
        )
    finally:
        conn.close()


@router.post("/{complaint_id}/close")
def close_complaint(
    complaint_id: int,
    data: ComplaintClose,
    current_user: Dict[str, Any] = Depends(require_roles(["super_admin", "hostel_admin", "warden", "assistant_warden"]))
) -> Dict[str, Any]:
    """Warden inspects and approves closure of resolved complaint."""
    conn = get_db_connection()
    try:
        return ComplaintService.close_complaint(
            conn=conn,
            complaint_id=complaint_id,
            user_id=current_user.get("user_id", 1),
            notes=data.notes
        )
    finally:
        conn.close()
