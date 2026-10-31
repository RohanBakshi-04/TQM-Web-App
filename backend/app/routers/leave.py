"""Leave Application and Gate Outpass API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Fast Response Time (< 10ms)
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status

from backend.app.models.leave_dto import (
    LeaveApplicationCreate,
    LeaveApplicationUpdate,
    LeaveApprovalRequest,
    LeaveRejectionRequest,
    OutpassVerificationRequest
)
from backend.app.services.leave_service import LeaveService
from backend.app.services.auth_dependencies import get_current_user

router = APIRouter(prefix="/api/v1/leave", tags=["Leave Management"])
outpass_router = APIRouter(prefix="/api/v1/outpasses", tags=["Gate Outpass Verification"])


# ==================== LEAVE APPLICATION ENDPOINTS ====================

@router.post("", status_code=status.HTTP_201_CREATED)
def submit_leave_application(
    payload: LeaveApplicationCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Submit a new leave application or save as draft."""
    return LeaveService.create_leave_application(payload, current_user)


@router.get("", status_code=status.HTTP_200_OK)
def get_leave_applications(
    status: Optional[str] = Query(None),
    leave_type: Optional[str] = Query(None),
    hostel_id: Optional[int] = Query(None, gt=0),
    start_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve filtered leave applications with strict RBAC data isolation."""
    filters = {
        "status": status,
        "leave_type": leave_type,
        "hostel_id": hostel_id,
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
        "offset": offset
    }
    return LeaveService.get_leave_applications(filters, current_user)


@router.get("/{leave_id}", status_code=status.HTTP_200_OK)
def get_leave_application(
    leave_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Fetch details of a single leave application and attached outpass."""
    return LeaveService.get_leave_application(leave_id, current_user)


@router.put("/{leave_id}", status_code=status.HTTP_200_OK)
def update_leave_application(
    leave_id: int,
    payload: LeaveApplicationUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Modify a draft or submitted leave application."""
    return LeaveService.update_leave_application(leave_id, payload, current_user)


@router.post("/{leave_id}/approve", status_code=status.HTTP_200_OK)
def approve_leave_application(
    leave_id: int,
    payload: LeaveApprovalRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Approve a leave request and automatically generate a digital gate outpass."""
    return LeaveService.approve_leave_application(leave_id, payload, current_user)


@router.post("/{leave_id}/reject", status_code=status.HTTP_200_OK)
def reject_leave_application(
    leave_id: int,
    payload: LeaveRejectionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Reject a leave request with mandatory audit justification."""
    return LeaveService.reject_leave_application(leave_id, payload, current_user)


# ==================== GATE OUTPASS ENDPOINTS ====================

@outpass_router.get("", status_code=status.HTTP_200_OK)
def get_outpasses(
    status: Optional[str] = Query(None),
    outpass_number: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List issued, departed, and returned gate outpasses."""
    filters = {
        "status": status,
        "outpass_number": outpass_number,
        "limit": limit,
        "offset": offset
    }
    return LeaveService.get_outpasses(filters, current_user)


@outpass_router.get("/overdue", status_code=status.HTTP_200_OK)
def get_overdue_outpasses(
    hostel_id: Optional[int] = Query(None, gt=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Identify students who exited campus and are overdue beyond curfew."""
    return LeaveService.get_overdue_outpasses(hostel_id, current_user)


@outpass_router.get("/{outpass_ref}", status_code=status.HTTP_200_OK)
def get_outpass_by_reference(
    outpass_ref: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve details for a specific gate outpass number or ID."""
    conn = get_current_user
    # Fetch through service
    res = LeaveService.get_outpasses({"outpass_number": outpass_ref, "limit": 1}, current_user)
    if not res["records"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Outpass not found.")
    return res["records"][0]


@outpass_router.post("/{outpass_ref}/verify-exit", status_code=status.HTTP_200_OK)
def verify_gate_exit(
    outpass_ref: str,
    payload: OutpassVerificationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Record physical exit through campus gate with duplicate prevention."""
    return LeaveService.verify_outpass_exit(outpass_ref, payload, current_user)


@outpass_router.post("/{outpass_ref}/verify-return", status_code=status.HTTP_200_OK)
def verify_gate_return(
    outpass_ref: str,
    payload: OutpassVerificationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Record physical return through campus gate with duplicate prevention."""
    return LeaveService.verify_outpass_return(outpass_ref, payload, current_user)
