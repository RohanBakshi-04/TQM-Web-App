"""Dashboard Telemetry & Aggregation API Router with Q05 In-Memory Cache.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from backend.app.database.connection import get_db_connection
from backend.app.services.auth_dependencies import get_current_user, require_roles
from backend.app.services.cache_service import cache_service
from backend.app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard Telemetry"])
metrics_router = APIRouter(prefix="/api/v1/metrics", tags=["Q05 Cached Metrics"])


@router.get("/executive-overview")
def get_executive_overview(
    academic_session: Optional[str] = Query(None, description="Academic Session (e.g. 2026-27)"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    campus: Optional[str] = Query(None, description="Campus filter (e.g. North Campus, South Campus)"),
    hostel_id: Optional[int] = Query(None, description="Facility ID filter"),
    department: Optional[str] = Query(None, description="Department code or name filter"),
    bypass_cache: bool = Query(False, description="Bypass in-memory Q05 cache and recompute"),
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin", "it_admin", "auditor"))
) -> Dict[str, Any]:
    """SA-01 Super Admin Executive Overview Telemetry with Q05 sub-10ms response guarantee."""
    conn = get_db_connection()
    try:
        # Enforce hostel scoping for non-global administrative roles
        user_roles = current_user.get("roles", [])
        effective_hostel_id = hostel_id
        if "super_admin" not in user_roles and "auditor" not in user_roles and "it_admin" not in user_roles:
            effective_hostel_id = current_user.get("linked_hostel_id") or hostel_id

        return DashboardService.get_super_admin_executive_metrics(
            conn=conn,
            user_roles=user_roles,
            user_id=current_user.get("user_id"),
            academic_session=academic_session,
            date_from=date_from,
            date_to=date_to,
            campus=campus,
            hostel_id=effective_hostel_id,
            department=department,
            bypass_cache=bypass_cache
        )
    finally:
        conn.close()


@router.get("/stats")
def get_dashboard_stats(
    hostel_id: Optional[int] = Query(None, description="Optional facility filter"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Return cached dashboard aggregation statistics across operational domains."""
    conn = get_db_connection()
    try:
        return DashboardService.get_dashboard_metrics(
            conn=conn,
            user_roles=current_user.get("roles", []),
            user_id=current_user.get("user_id"),
            linked_hostel_id=current_user.get("linked_hostel_id"),
            linked_student_id=current_user.get("linked_student_id"),
            requested_hostel_id=hostel_id,
            bypass_cache=False
        )
    finally:
        conn.close()


@metrics_router.get("/dashboard")
def get_metrics_dashboard(
    hostel_id: Optional[int] = Query(None, description="Facility filter (accessible to authorized roles)"),
    date_from: Optional[str] = Query(None, description="ISO format start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="ISO format end date (YYYY-MM-DD)"),
    bypass_cache: bool = Query(False, description="Set True to bypass in-memory cache and recompute from SQL"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Q05 Optimized Cached Dashboard Endpoint providing role-specific aggregate statistics (<1ms warm response)."""
    conn = get_db_connection()
    try:
        return DashboardService.get_dashboard_metrics(
            conn=conn,
            user_roles=current_user.get("roles", []),
            user_id=current_user.get("user_id"),
            linked_hostel_id=current_user.get("linked_hostel_id"),
            linked_student_id=current_user.get("linked_student_id"),
            requested_hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
            bypass_cache=bypass_cache
        )
    finally:
        conn.close()


@metrics_router.get("/cache/stats")
def get_cache_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Return in-memory cache operational telemetry including hits, misses, hit ratio, and active entries."""
    return cache_service.get_stats()


@metrics_router.post("/cache/clear", status_code=status.HTTP_200_OK)
def clear_cache(
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "auditor"))
) -> Dict[str, Any]:
    """Flush the entire in-memory dashboard and metrics cache (Administrators only)."""
    cache_service.clear()
    return {
        "status": "success",
        "message": "In-memory cache flushed successfully.",
        "stats": cache_service.get_stats()
    }
