"""Hostel and Building Management REST API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms)
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from backend.app.database.connection import get_db_connection
from backend.app.models.hostel_dto import (
    BuildingCreate,
    BuildingStatusUpdate,
    BuildingUpdate,
    HostelCreate,
    HostelStatusUpdate,
    HostelUpdate,
)
from backend.app.services.auth_dependencies import get_current_user, require_permissions, require_roles
from backend.app.services.hostel_service import HostelService

router = APIRouter(prefix="/api/v1/hostels", tags=["Hostel & Building Management"])


@router.get("", response_model=List[Dict[str, Any]])
def list_hostels(
    hostel_type: Optional[str] = Query(None, description="Filter by Boys, Girls, Co-Ed"),
    is_active: Optional[int] = Query(None, description="Filter by active status (1 or 0)"),
    search: Optional[str] = Query(None, description="Search term for name, code, address"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """List all hostels with dynamic room, bed, and occupancy statistics."""
    conn = get_db_connection()
    try:
        # If user has a linked hostel and is not super_admin or auditor, filter by linked_hostel_id
        user_hostel_id = None
        user_roles = set(current_user.get("roles", []))
        if not user_roles.intersection({"super_admin", "auditor", "accountant"}):
            user_hostel_id = current_user.get("linked_hostel_id")

        return HostelService.get_all_hostels(
            conn=conn,
            hostel_type=hostel_type,
            is_active=is_active,
            search=search,
            user_hostel_id=user_hostel_id
        )
    finally:
        conn.close()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_hostel(
    data: HostelCreate,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin"))
) -> Dict[str, Any]:
    """Create a new hostel with code and name uniqueness validation."""
    conn = get_db_connection()
    try:
        return HostelService.create_hostel(conn, data)
    finally:
        conn.close()


@router.get("/wardens/candidates", response_model=List[Dict[str, Any]])
def get_warden_candidates(
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin"))
) -> List[Dict[str, Any]]:
    """List staff members eligible for hostel administration/warden roles."""
    conn = get_db_connection()
    try:
        return HostelService.get_warden_candidates(conn)
    finally:
        conn.close()


@router.get("/{hostel_id}")
def get_hostel(
    hostel_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get full details of a specific hostel including its buildings."""
    conn = get_db_connection()
    try:
        return HostelService.get_hostel_by_id(conn, hostel_id)
    finally:
        conn.close()


@router.put("/{hostel_id}")
def update_hostel(
    hostel_id: int,
    data: HostelUpdate,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin"))
) -> Dict[str, Any]:
    """Update hostel properties."""
    conn = get_db_connection()
    try:
        return HostelService.update_hostel(conn, hostel_id, data)
    finally:
        conn.close()


@router.patch("/{hostel_id}/status")
def set_hostel_status(
    hostel_id: int,
    data: HostelStatusUpdate,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin"))
) -> Dict[str, Any]:
    """Activate or deactivate a hostel."""
    conn = get_db_connection()
    try:
        return HostelService.set_hostel_status(conn, hostel_id, data.is_active)
    finally:
        conn.close()


# ==================== BUILDINGS ====================

@router.get("/{hostel_id}/buildings", response_model=List[Dict[str, Any]])
def list_buildings_for_hostel(
    hostel_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """List all buildings under a given hostel."""
    conn = get_db_connection()
    try:
        return HostelService.get_buildings_for_hostel(conn, hostel_id)
    finally:
        conn.close()


@router.post("/{hostel_id}/buildings", status_code=status.HTTP_201_CREATED)
def create_building(
    hostel_id: int,
    data: BuildingCreate,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin"))
) -> Dict[str, Any]:
    """Add a new building to a hostel."""
    conn = get_db_connection()
    try:
        return HostelService.create_building(conn, hostel_id, data)
    finally:
        conn.close()


# Generic building routes
building_router = APIRouter(prefix="/api/v1/buildings", tags=["Building Operations"])


@building_router.get("/{building_id}")
def get_building(
    building_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Fetch building details."""
    conn = get_db_connection()
    try:
        return HostelService.get_building_by_id(conn, building_id)
    finally:
        conn.close()


@building_router.put("/{building_id}")
def update_building(
    building_id: int,
    data: BuildingUpdate,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin"))
) -> Dict[str, Any]:
    """Update building details."""
    conn = get_db_connection()
    try:
        return HostelService.update_building(conn, building_id, data)
    finally:
        conn.close()


@building_router.patch("/{building_id}/status")
def set_building_status(
    building_id: int,
    data: BuildingStatusUpdate,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin"))
) -> Dict[str, Any]:
    """Activate or deactivate a building."""
    conn = get_db_connection()
    try:
        return HostelService.update_building(conn, building_id, BuildingUpdate(is_active=data.is_active))
    finally:
        conn.close()
