"""Room Allocation and Poka-Yoke System REST API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms)
Poka-Yoke: Defect-Proof Relational Integrity & Concurrency Protection
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from backend.app.database.connection import get_db_connection
from backend.app.models.allocation_dto import (
    AllocationCreate,
    AllocationResponse,
    AvailableBedItem,
    CheckoutRequest,
    RoomOccupantItem,
    TransferRequestCreate,
    TransferReview,
)
from backend.app.services.allocation_service import AllocationService
from backend.app.services.auth_dependencies import (
    get_current_user,
    require_roles,
    verify_student_isolation,
)

router = APIRouter(prefix="/api/v1/allocations", tags=["Room Allocations & Poka-Yoke"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_room_allocation(
    data: AllocationCreate,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin", "warden", "assistant_warden"))
) -> Dict[str, Any]:
    """Allocate a student to a hostel room and bed with strict 10-layer Poka-Yoke error prevention."""
    conn = get_db_connection()
    try:
        return AllocationService.create_allocation(conn, data, allocated_by_user_id=current_user["id"])
    finally:
        conn.close()


@router.get("", response_model=List[Dict[str, Any]])
def list_allocations(
    hostel_id: Optional[int] = Query(None),
    building_id: Optional[int] = Query(None),
    floor_id: Optional[int] = Query(None),
    room_type: Optional[str] = Query(None),
    allocation_status: Optional[str] = Query(None),
    student_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """List allocations across hostels with sub-10ms query execution."""
    conn = get_db_connection()
    try:
        user_roles = set(current_user.get("roles", []))
        # If student role, isolate strictly to own allocations
        if "student" in user_roles and not user_roles.intersection({"super_admin", "hostel_admin", "warden", "assistant_warden", "accountant", "auditor"}):
            student_id = current_user.get("linked_student_id")

        return AllocationService.get_allocations(
            conn=conn,
            hostel_id=hostel_id,
            building_id=building_id,
            floor_id=floor_id,
            room_type=room_type,
            allocation_status=allocation_status,
            student_id=student_id,
            search=search,
            limit=limit,
            offset=offset
        )
    finally:
        conn.close()


@router.get("/available-beds", response_model=List[Dict[str, Any]])
def list_available_beds(
    hostel_id: Optional[int] = Query(None),
    building_id: Optional[int] = Query(None),
    floor_id: Optional[int] = Query(None),
    room_type: Optional[str] = Query(None),
    gender: Optional[str] = Query(None, description="Filter for Male or Female eligible hostels"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Explore all currently assignable beds in real-time."""
    conn = get_db_connection()
    try:
        return AllocationService.get_available_beds(
            conn=conn,
            hostel_id=hostel_id,
            building_id=building_id,
            floor_id=floor_id,
            room_type=room_type,
            gender_compatible=gender
        )
    finally:
        conn.close()


@router.get("/{allocation_id}")
def get_allocation_details(
    allocation_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Retrieve full details and confirmation slip for an allocation."""
    conn = get_db_connection()
    try:
        alloc = AllocationService.get_allocation_by_id(conn, allocation_id)
        verify_student_isolation(alloc["student_id"], current_user)
        return alloc
    finally:
        conn.close()


# Associated sub-routers
room_occupants_router = APIRouter(prefix="/api/v1/rooms", tags=["Room Operations"])


@room_occupants_router.get("/{room_id}/occupants", response_model=List[Dict[str, Any]])
def get_room_occupants(
    room_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """List active student residents occupying a given room."""
    conn = get_db_connection()
    try:
        return AllocationService.get_room_occupants(conn, room_id)
    finally:
        conn.close()


student_history_router = APIRouter(prefix="/api/v1/students", tags=["Student Allocations"])


@student_history_router.get("/{student_id}/allocation-history", response_model=List[Dict[str, Any]])
def get_student_history(
    student_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """View chronological room allocation, checkout, and transfer history for a student."""
    verify_student_isolation(student_id, current_user)
    conn = get_db_connection()
    try:
        return AllocationService.get_student_allocation_history(conn, student_id)
    finally:
        conn.close()
