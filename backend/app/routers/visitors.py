"""Visitor Management API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Fast Response Time (< 10ms)
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status

from backend.app.models.visitor_dto import (
    VisitorRegistrationRequest,
    VisitorApprovalRequest,
    VisitorRejectionRequest,
    VisitorCheckInRequest,
    VisitorCheckOutRequest
)
from backend.app.services.visitor_service import VisitorService
from backend.app.services.auth_dependencies import get_current_user

router = APIRouter(prefix="/api/v1/visitors", tags=["Visitor Management"])


@router.post("", status_code=status.HTTP_201_CREATED)
def register_visitor(
    payload: VisitorRegistrationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Register a new campus visitor with active duplicate prevention."""
    return VisitorService.register_visitor(payload, current_user)


@router.get("", status_code=status.HTTP_200_OK)
def get_visitor_logs(
    status: Optional[str] = Query(None),
    hostel_id: Optional[int] = Query(None, gt=0),
    date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve filtered visitor pass records with role-based privacy masking."""
    filters = {
        "status": status,
        "hostel_id": hostel_id,
        "date": date,
        "search": search,
        "limit": limit,
        "offset": offset
    }
    return VisitorService.get_visitor_logs(filters, current_user)


@router.get("/active", status_code=status.HTTP_200_OK)
def get_active_visitors(
    hostel_id: Optional[int] = Query(None, gt=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List all visitors currently checked in inside the campus."""
    return VisitorService.get_active_visitors(hostel_id, current_user)


@router.get("/reports", status_code=status.HTTP_200_OK)
def get_visitor_reports(
    start_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    hostel_id: Optional[int] = Query(None, gt=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Aggregate statistics of visitor traffic over a date range."""
    return VisitorService.get_visitor_reports(start_date, end_date, hostel_id, current_user)


@router.get("/{visitor_log_id}", status_code=status.HTTP_200_OK)
def get_visitor_log(
    visitor_log_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Fetch details of a single visitor pass."""
    return VisitorService.get_visitor_log(visitor_log_id, current_user)


@router.post("/{visitor_log_id}/approve", status_code=status.HTTP_200_OK)
def approve_visitor(
    visitor_log_id: int,
    payload: VisitorApprovalRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Authorize a visitor entry request."""
    return VisitorService.approve_visitor(visitor_log_id, payload, current_user)


@router.post("/{visitor_log_id}/reject", status_code=status.HTTP_200_OK)
def reject_visitor(
    visitor_log_id: int,
    payload: VisitorRejectionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Deny a visitor entry request with mandatory reason."""
    return VisitorService.reject_visitor(visitor_log_id, payload, current_user)


@router.post("/{visitor_log_id}/check-in", status_code=status.HTTP_200_OK)
def check_in_visitor(
    visitor_log_id: int,
    payload: VisitorCheckInRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Log visitor arrival at campus gate."""
    return VisitorService.check_in_visitor(visitor_log_id, payload, current_user)


@router.post("/{visitor_log_id}/check-out", status_code=status.HTTP_200_OK)
def check_out_visitor(
    visitor_log_id: int,
    payload: VisitorCheckOutRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Log visitor departure at campus gate."""
    return VisitorService.check_out_visitor(visitor_log_id, payload, current_user)
