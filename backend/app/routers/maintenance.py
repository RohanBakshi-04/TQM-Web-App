"""Maintenance Task and Work-Order REST API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from backend.app.database.connection import get_db_connection
from backend.app.models.maintenance_dto import (
    MaintenanceTaskComplete,
    MaintenanceTaskCreate,
    MaintenanceTaskHold,
    MaintenanceTaskProgress,
    MaintenanceTaskVerify,
)
from backend.app.services.auth_dependencies import get_current_user, require_roles
from backend.app.services.maintenance_service import MaintenanceService

router = APIRouter(prefix="/api/v1/maintenance", tags=["Maintenance Work-Orders"])


@router.get("/tasks", response_model=List[Dict[str, Any]])
def list_maintenance_tasks(
    status_filter: Optional[str] = Query(None, description="Filter by task status"),
    priority_filter: Optional[str] = Query(None, description="Filter by priority level"),
    assigned_to: Optional[int] = Query(None, description="Filter by assigned worker ID"),
    hostel_id: Optional[int] = Query(None, description="Filter by hostel ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Retrieve maintenance tasks with optional status, priority, and worker filters."""
    # If technician, default to their tasks unless admin
    roles = set(current_user.get("roles", []))
    is_worker = "maintenance_staff" in roles and not roles.intersection({"super_admin", "hostel_admin", "warden", "assistant_warden", "auditor"})
    if is_worker and not assigned_to:
        assigned_to = current_user.get("user_id")

    conn = get_db_connection()
    try:
        return MaintenanceService.get_maintenance_tasks(
            conn=conn,
            status_filter=status_filter,
            priority_filter=priority_filter,
            assigned_to=assigned_to,
            hostel_id=hostel_id
        )
    finally:
        conn.close()


@router.get("/tasks/{task_id}")
def get_maintenance_task(
    task_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Retrieve complete maintenance task details with progress update history."""
    conn = get_db_connection()
    try:
        return MaintenanceService.get_task_by_id(conn=conn, task_id=task_id)
    finally:
        conn.close()


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_maintenance_task(
    data: MaintenanceTaskCreate,
    current_user: Dict[str, Any] = Depends(require_roles(["super_admin", "hostel_admin", "warden", "assistant_warden"]))
) -> Dict[str, Any]:
    """Create a new work-order task with technician assignment and Poka-Yoke room status lock."""
    conn = get_db_connection()
    try:
        return MaintenanceService.create_maintenance_task(
            conn=conn,
            data=data,
            created_by_user_id=current_user.get("user_id")
        )
    finally:
        conn.close()


@router.post("/tasks/{task_id}/accept")
def accept_maintenance_task(
    task_id: int,
    current_user: Dict[str, Any] = Depends(require_roles("maintenance_staff", "super_admin", "hostel_admin"))
) -> Dict[str, Any]:
    """Technician accepts an assigned maintenance work-order."""
    conn = get_db_connection()
    try:
        return MaintenanceService.accept_task(
            conn=conn,
            task_id=task_id,
            worker_user_id=current_user.get("user_id", 1)
        )
    finally:
        conn.close()


@router.post("/tasks/{task_id}/start")
def start_maintenance_task(
    task_id: int,
    current_user: Dict[str, Any] = Depends(require_roles("maintenance_staff", "super_admin", "hostel_admin"))
) -> Dict[str, Any]:
    """Technician starts repair work on-site."""
    conn = get_db_connection()
    try:
        return MaintenanceService.start_task(
            conn=conn,
            task_id=task_id,
            worker_user_id=current_user.get("user_id", 1)
        )
    finally:
        conn.close()


@router.post("/tasks/{task_id}/progress")
def update_task_progress(
    task_id: int,
    data: MaintenanceTaskProgress,
    current_user: Dict[str, Any] = Depends(require_roles("maintenance_staff", "super_admin", "hostel_admin"))
) -> Dict[str, Any]:
    """Technician logs progress or spare parts updates."""
    conn = get_db_connection()
    try:
        return MaintenanceService.update_task_progress(
            conn=conn,
            task_id=task_id,
            worker_user_id=current_user.get("user_id", 1),
            data=data
        )
    finally:
        conn.close()


@router.post("/tasks/{task_id}/hold")
def hold_maintenance_task(
    task_id: int,
    data: MaintenanceTaskHold,
    current_user: Dict[str, Any] = Depends(require_roles("maintenance_staff", "super_admin", "hostel_admin"))
) -> Dict[str, Any]:
    """Put task on hold with stated reason (e.g. awaiting spare parts)."""
    conn = get_db_connection()
    try:
        return MaintenanceService.hold_task(
            conn=conn,
            task_id=task_id,
            worker_user_id=current_user.get("user_id", 1),
            data=data
        )
    finally:
        conn.close()


@router.post("/tasks/{task_id}/complete")
def complete_maintenance_task(
    task_id: int,
    data: MaintenanceTaskComplete,
    current_user: Dict[str, Any] = Depends(require_roles("maintenance_staff", "super_admin", "hostel_admin"))
) -> Dict[str, Any]:
    """Technician submits work completion with resolution notes, actual cost, and photo."""
    conn = get_db_connection()
    try:
        return MaintenanceService.complete_task(
            conn=conn,
            task_id=task_id,
            worker_user_id=current_user.get("user_id", 1),
            data=data
        )
    finally:
        conn.close()


@router.post("/tasks/{task_id}/verify")
def verify_maintenance_task(
    task_id: int,
    data: MaintenanceTaskVerify,
    current_user: Dict[str, Any] = Depends(require_roles(["super_admin", "hostel_admin", "warden", "assistant_warden"]))
) -> Dict[str, Any]:
    """Warden or Facility Manager inspects repairs, restores infrastructure status, and approves closure."""
    conn = get_db_connection()
    try:
        return MaintenanceService.verify_task(
            conn=conn,
            task_id=task_id,
            verified_by_user_id=current_user.get("user_id", 1),
            data=data
        )
    finally:
        conn.close()


@router.get("/staff-availability", response_model=List[Dict[str, Any]])
def get_staff_availability(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Retrieve maintenance staff workload and availability matrix."""
    conn = get_db_connection()
    try:
        return MaintenanceService.get_staff_availability(conn=conn)
    finally:
        conn.close()
