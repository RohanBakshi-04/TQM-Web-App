from backend.app.services.auth_dependencies import get_parent_authorized_ward_ids, verify_student_isolation
"""Room Allocation and Poka-Yoke System REST API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms)
Poka-Yoke: Defect-Proof Relational Integrity & Concurrency Protection
"""

from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
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
        # Check hostel scope for warden and assistant warden (fail-closed)
        active_role = current_user.get("active_role") or current_user.get("role")
        user_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
        if active_role in ("warden", "assistant_warden"):
            if not user_hid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: Staff member has no assigned hostel facility."
                )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT bld.hostel_id
                FROM beds b
                JOIN rooms r ON r.id = b.room_id
                JOIN floors f ON f.id = r.floor_id
                JOIN buildings bld ON bld.id = f.building_id
                WHERE b.id = ?;
            """, (data.bed_id,))
            row = cursor.fetchone()
            if not row or row[0] != int(user_hid):
                assigned_h = row[0] if row else "unknown"
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access Denied: Bed #{data.bed_id} belongs to hostel facility #{assigned_h}, which is outside your assigned facility (#{user_hid})."
                )
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
    student_id: Optional[Union[str, int]] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """List allocations across hostels with sub-10ms query execution."""
    conn = get_db_connection()
    try:
        user_roles = set(current_user.get("roles", []))
        active_role = current_user.get("active_role") or current_user.get("role")

        # Student role isolation
        if active_role == "student":
            student_id = current_user.get("linked_student_id")

        # Parent / Guardian role isolation
        elif active_role in ("parent_guardian", "parent"):
            wards = get_parent_authorized_ward_ids(conn, current_user)
            if not wards:
                return []
            if student_id:
                if int(student_id) not in wards:
                    raise HTTPException(status_code=403, detail="Access Denied: You are not authorized to view allocations for this student.")
            elif len(wards) == 1:
                student_id = wards[0]

        # Warden and Assistant Warden hostel scope enforcement (fail-closed)
        if active_role in ("warden", "assistant_warden"):
            user_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
            if not user_hid:
                raise HTTPException(status_code=403, detail="Access Denied: Staff member has no assigned hostel facility.")
            if hostel_id and int(hostel_id) != int(user_hid):
                raise HTTPException(status_code=403, detail=f"Access Denied: Unauthorized hostel #{hostel_id}. Your assigned facility is #{user_hid}.")
            hostel_id = int(user_hid)

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
    """Explore all currently assignable beds in real-time with strict hostel scoping."""
    active_role = current_user.get("active_role") or current_user.get("role")
    if active_role in ("warden", "assistant_warden"):
        user_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
        if not user_hid:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access Denied: Staff member has no assigned hostel facility.")
        if hostel_id and int(hostel_id) != int(user_hid):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access Denied: Unauthorized hostel #{hostel_id}. Your assigned facility is #{user_hid}.")
        hostel_id = int(user_hid)
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
    student_id: Union[str, int] = Query(..., description="Student ID (e.g. STU-202611-0089) or internal student database ID"),
    preferred_hostel_id: Optional[int] = Query(None),
    preferred_room_type: Optional[str] = Query(None),
    floor_preference: Optional[int] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Intelligent automated room and bed suggestion engine with multi-criteria scoring."""
    verify_student_isolation(student_id, current_user)
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
        active_role = current_user.get("active_role") or current_user.get("role")
        if active_role in ("warden", "assistant_warden"):
            alloc = AllocationService.get_allocation_by_id(conn, allocation_id)
            user_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
            if not user_hid or int(user_hid) != int(alloc["hostel_id"]):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access Denied: Allocation belongs to a hostel outside your assigned facility.")
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
        active_role = current_user.get("active_role") or current_user.get("role")
        if active_role in ("warden", "assistant_warden"):
            alloc = AllocationService.get_allocation_by_id(conn, allocation_id)
            user_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
            if not user_hid or int(user_hid) != int(alloc["hostel_id"]):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access Denied: Allocation belongs to a hostel outside your assigned facility.")
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
        active_role = current_user.get("active_role") or current_user.get("role")
        if active_role in ("warden", "assistant_warden"):
            alloc_full = AllocationService.get_allocation_by_id(conn, allocation_id)
            user_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
            if not user_hid or int(user_hid) != int(alloc_full["hostel_id"]):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access Denied: Allocation belongs to a hostel outside your assigned facility.")
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
        active_role = current_user.get("active_role") or current_user.get("role")
        if active_role in ("warden", "assistant_warden"):
            user_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
            if not user_hid:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access Denied: Staff member has no assigned hostel facility.")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT bld.hostel_id
                FROM room_transfers rt
                JOIN room_allocations ra ON ra.id = rt.allocation_id
                JOIN rooms r ON r.id = ra.room_id
                JOIN floors f ON f.id = r.floor_id
                JOIN buildings bld ON bld.id = f.building_id
                WHERE rt.id = ?;
            """, (transfer_id,))
            t_row = cursor.fetchone()
            if not t_row or int(t_row[0]) != int(user_hid):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access Denied: Transfer request belongs to a hostel outside your assigned facility.")
        return AllocationService.review_transfer_request(conn, transfer_id, data, reviewer_id=current_user["id"])
    finally:
        conn.close()


room_occupants_router = APIRouter(prefix="/api/v1/rooms", tags=["Room Operations"])


@room_occupants_router.get("/{room_id}/occupants", response_model=List[Dict[str, Any]])
def get_room_occupants(
    room_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """List active student residents occupying a given room with resident & staff isolation."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT bld.hostel_id
            FROM rooms r
            JOIN floors f ON f.id = r.floor_id
            JOIN buildings bld ON bld.id = f.building_id
            WHERE r.id = ?;
        """, (room_id,))
        r_info = cursor.fetchone()
        if not r_info:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.")

        room_hostel_id = r_info[0]
        active_role = current_user.get("active_role") or current_user.get("role")

        # Student: can only view occupants of their own allocated room
        if active_role == "student":
            student_id = current_user.get("linked_student_id")
            cursor.execute("""
                SELECT room_id FROM room_allocations
                WHERE student_id = ? AND allocation_status = 'Active';
            """, (student_id,))
            st_alloc = cursor.fetchone()
            if not st_alloc or st_alloc[0] != room_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: You can only view occupants of your own allocated room."
                )

        # Warden: must be assigned to this hostel
        elif active_role in ("warden", "assistant_warden"):
            user_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
            if not user_hid or int(user_hid) != room_hostel_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: Room belongs to a hostel outside your assigned facility."
                )

        # Parent: can only view if linked ward is in this room
        elif active_role in ("parent", "parent_guardian"):
            wards = get_parent_authorized_ward_ids(conn, current_user)
            if not wards:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access Denied.")
            placeholders = ",".join("?" for _ in wards)
            cursor.execute(f"""
                SELECT room_id FROM room_allocations
                WHERE student_id IN ({placeholders}) AND allocation_status = 'Active';
            """, list(wards))
            ward_rooms = {row[0] for row in cursor.fetchall()}
            if room_id not in ward_rooms:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: None of your linked wards are allocated to this room."
                )

        return AllocationService.get_room_occupants(conn, room_id)
    finally:
        conn.close()


student_history_router = APIRouter(prefix="/api/v1/students", tags=["Student Allocations"])


@student_history_router.get("/{student_id}/allocation-history", response_model=List[Dict[str, Any]])
def get_student_history(
    student_id: Union[str, int],
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """View chronological room allocation, checkout, and transfer history for a student."""
    verify_student_isolation(student_id, current_user)
    conn = get_db_connection()
    try:
        return AllocationService.get_student_allocation_history(conn, student_id)
    finally:
        conn.close()
