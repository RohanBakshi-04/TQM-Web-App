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


@router.get("/suggestions", response_model=List[Dict[str, Any]])
def get_allocation_suggestions(
    student_id: int = Query(..., description="ID of student needing allocation"),
    preferred_hostel_id: Optional[int] = Query(None),
    preferred_room_type: Optional[str] = Query(None),
    floor_preference: Optional[int] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Intelligent automated room and bed suggestion engine with multi-criteria scoring."""
    conn = get_db_connection()
    try:
        return AllocationService.get_allocation_suggestions(
            conn=conn,
            student_id=student_id,
            preferred_hostel_id=preferred_hostel_id,
            preferred_room_type=preferred_room_type,
            floor_preference=floor_preference
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


@router.post("/{allocation_id}/checkin")
def checkin_student(
    allocation_id: int,
    checkin_data: Optional[Dict[str, Any]] = None,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin", "warden", "assistant_warden"))
) -> Dict[str, Any]:
    """Verify and record student arrival and room check-in."""
    conn = get_db_connection()
    try:
        c_date = checkin_data.get("checkin_date") if checkin_data else None
        return AllocationService.checkin_allocation(conn, allocation_id, c_date, user_id=current_user["id"])
    finally:
        conn.close()


@router.post("/{allocation_id}/checkout")
def checkout_student(
    allocation_id: int,
    data: CheckoutRequest,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin", "warden", "assistant_warden"))
) -> Dict[str, Any]:
    """Release assigned bed and update occupancy upon student check-out (Poka-Yoke protected)."""
    conn = get_db_connection()
    try:
        return AllocationService.checkout_allocation(
            conn=conn,
            allocation_id=allocation_id,
            checkout_date=data.checkout_date,
            reason=data.reason,
            user_id=current_user["id"]
        )
    finally:
        conn.close()


@router.post("/{allocation_id}/transfer")
def request_or_perform_transfer(
    allocation_id: int,
    data: TransferRequestCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Initiate a student room transfer with atomic bed reallocation or staff approval workflow."""
    conn = get_db_connection()
    try:
        alloc = AllocationService.get_allocation_by_id(conn, allocation_id)
        verify_student_isolation(alloc["student_id"], current_user)
        return AllocationService.request_or_execute_transfer(
            conn=conn,
            allocation_id=allocation_id,
            to_bed_id=data.to_bed_id,
            reason=data.reason,
            user_id=current_user["id"],
            user_roles=current_user.get("roles", [])
        )
    finally:
        conn.close()


@router.post("/{allocation_id}/approve")
def approve_allocation(
    allocation_id: int,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin", "warden"))
) -> Dict[str, Any]:
    """Administrative approval of an allocation record."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        alloc = cursor.execute("SELECT id, approval_status FROM room_allocations WHERE id = ?;", (allocation_id,)).fetchone()
        if not alloc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found.")
        cursor.execute("UPDATE room_allocations SET approval_status = 'Approved', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (allocation_id,))
        conn.commit()
        return AllocationService.get_allocation_by_id(conn, allocation_id)
    finally:
        conn.close()


# Associated sub-routers
transfers_router = APIRouter(prefix="/api/v1/transfers", tags=["Room Transfer Operations"])


@transfers_router.get("", response_model=List[Dict[str, Any]])
def list_transfer_requests(
    status_filter: Optional[str] = Query(None, description="Pending, Approved, Rejected"),
    student_id: Optional[int] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """List pending and historical room transfer requests."""
    conn = get_db_connection()
    try:
        user_roles = set(current_user.get("roles", []))
        if "student" in user_roles and not user_roles.intersection({"super_admin", "hostel_admin", "warden", "assistant_warden", "auditor"}):
            student_id = current_user.get("linked_student_id")
        return AllocationService.get_transfers(conn, status_filter=status_filter, student_id=student_id)
    finally:
        conn.close()


@transfers_router.post("/{transfer_id}/review")
def review_transfer(
    transfer_id: int,
    data: TransferReview,
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin", "warden"))
) -> Dict[str, Any]:
    """Approve or reject a student room transfer request."""
    conn = get_db_connection()
    try:
        return AllocationService.review_transfer_request(conn, transfer_id, data, reviewer_id=current_user["id"])
    finally:
        conn.close()


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
