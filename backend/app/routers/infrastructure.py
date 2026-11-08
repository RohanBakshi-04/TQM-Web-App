"""REST API Router for Enterprise Infrastructure & Hostels (SA-02).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA), Poka-Yoke Error Proofing, Zero-Defect Delivery
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import PlainTextResponse

from backend.app.database.connection import get_db_connection
from backend.app.models.infrastructure_dto import (
    BedCreate,
    BedMaintenanceUpdate,
    BedUpdate,
    BlockCreate,
    BlockUpdate,
    BuildingCreateExt,
    BuildingUpdateExt,
    BulkImportRequest,
    CampusAdminAssign,
    CampusCreate,
    CampusStatusUpdate,
    CampusUpdate,
    FloorCreate,
    FloorUpdate,
    HostelCategoryUpdate,
    HostelCreateExt,
    HostelLeadershipAssign,
    HostelUpdateExt,
    InstitutionConfigUpdate,
    InstitutionUpdate,
    RoomCapacityUpdate,
    RoomCreate,
    RoomMaintenanceUpdate,
    RoomUpdate,
)
from backend.app.services.auth_dependencies import get_current_user, require_permissions, verify_infrastructure_scope
from backend.app.services.infrastructure_service import InfrastructureService

router = APIRouter(prefix="/api/v1", tags=["Infrastructure & Campus Management"])


# =============================================================
# Module A: Institution Profile & Configuration
# =============================================================

@router.get("/institutions", summary="Get Institution Profile & Institutional Summary")
def get_institution(
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("institution:read", "infrastructure:read")),
):
    try:
        return InfrastructureService.get_institution(conn)
    finally:
        conn.close()


@router.put("/institutions", summary="Update Institution Profile")
def update_institution(
    payload: InstitutionUpdate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("institution:update", "infrastructure:manage")),
):
    try:
        verify_infrastructure_scope(current_user, institution_id=1)
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.update_institution(conn, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.put("/institutions/config", summary="Update Institution Configuration (Timezone, Academic Year, Currency)")
def update_institution_config(
    payload: InstitutionConfigUpdate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("institutions.config.update", "infrastructure:manage")),
):
    try:
        verify_infrastructure_scope(current_user, institution_id=1)
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.update_institution_config(conn, payload, user_id=user_id, username=username)
    finally:
        conn.close()


# =============================================================
# Module B: Multi-Campus Management
# =============================================================

@router.get("/campuses", summary="List Campuses with Aggregated Metrics")
def list_campuses(
    operating_status: Optional[str] = Query(None, description="Active, Inactive, Under_Maintenance"),
    is_active: Optional[int] = Query(None, ge=0, le=1),
    search: Optional[str] = Query(None, description="Search by name, code or city"),
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("campuses:read", "infrastructure:read")),
):
    try:
        return InfrastructureService.list_campuses(
            conn, operating_status=operating_status, is_active=is_active, search=search
        )
    finally:
        conn.close()


@router.get("/campuses/{campus_id}", summary="Get Campus Details by ID")
def get_campus(
    campus_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("campuses:read", "infrastructure:read")),
):
    try:
        return InfrastructureService.get_campus_by_id(conn, campus_id)
    finally:
        conn.close()


@router.post("/campuses", status_code=status.HTTP_201_CREATED, summary="Create New Campus")
def create_campus(
    payload: CampusCreate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("campuses:create", "campuses:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.create_campus(conn, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.put("/campuses/{campus_id}", summary="Update Campus Details")
def update_campus(
    campus_id: int,
    payload: CampusUpdate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("campuses:update", "campuses:manage")),
):
    try:
        verify_infrastructure_scope(current_user, campus_id=campus_id)
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.update_campus(conn, campus_id, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.patch("/campuses/{campus_id}/status", summary="Update Campus Operating & Active Status")
def set_campus_status(
    campus_id: int,
    payload: CampusStatusUpdate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("campuses:manage")),
):
    verify_infrastructure_scope(current_user, campus_id=campus_id)
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.set_campus_status(
            conn, campus_id, payload.operating_status, payload.is_active or 1, user_id=user_id, username=username
        )
    finally:
        conn.close()


@router.post("/campuses/{campus_id}/admin", summary="Assign Campus Administrator")
def assign_campus_admin(
    campus_id: int,
    payload: CampusAdminAssign,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("campuses:manage")),
):
    verify_infrastructure_scope(current_user, campus_id=campus_id)
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.assign_campus_admin(conn, campus_id, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.delete("/campuses/{campus_id}", summary="Delete Campus (Poka-Yoke Protected)")
def delete_campus(
    campus_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("campuses:delete", "campuses:manage")),
):
    verify_infrastructure_scope(current_user, campus_id=campus_id)
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.delete_campus(conn, campus_id, user_id=user_id, username=username)
    finally:
        conn.close()


# =============================================================
# Module C: Hostel Management Extended
# =============================================================

@router.get("/infrastructure/hostels", summary="List Hostels Extended (with Campus & Capacity)")
def list_hostels_extended(
    campus_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    hostel_type: Optional[str] = Query(None),
    is_active: Optional[int] = Query(None, ge=0, le=1),
    search: Optional[str] = Query(None),
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("hostels:read", "infrastructure:read")),
):
    try:
        return InfrastructureService.list_hostels_extended(
            conn, campus_id=campus_id, category=category, hostel_type=hostel_type,
            is_active=is_active, search=search
        )
    finally:
        conn.close()


@router.get("/infrastructure/hostels/{hostel_id}", summary="Get Detailed Hostel Profile")
def get_hostel_detail(
    hostel_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("hostels:read", "infrastructure:read")),
):
    try:
        return InfrastructureService.get_hostel_detail(conn, hostel_id)
    finally:
        conn.close()


@router.post("/infrastructure/hostels", status_code=status.HTTP_201_CREATED, summary="Create Hostel Extended")
def create_hostel_extended(
    payload: HostelCreateExt,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("hostels:create")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.create_hostel_extended(conn, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.put("/infrastructure/hostels/{hostel_id}", summary="Update Hostel Extended")
def update_hostel_extended(
    hostel_id: int,
    payload: HostelUpdateExt,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("hostels:update")),
):
    try:
        verify_infrastructure_scope(current_user, hostel_id=hostel_id, conn=conn)
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.update_hostel_extended(conn, hostel_id, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.patch("/infrastructure/hostels/{hostel_id}/leadership", summary="Assign Hostel Leadership Team")
def assign_hostel_leadership(
    hostel_id: int,
    payload: HostelLeadershipAssign,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("hostels:manage")),
):
    verify_infrastructure_scope(current_user, hostel_id=hostel_id, conn=conn)
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.assign_hostel_leadership(conn, hostel_id, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.patch("/infrastructure/hostels/{hostel_id}/category", summary="Update Hostel Category")
def update_hostel_category(
    hostel_id: int,
    payload: HostelCategoryUpdate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("hostels:update")),
):
    verify_infrastructure_scope(current_user, hostel_id=hostel_id, conn=conn)
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.update_hostel_category(conn, hostel_id, payload.category, user_id=user_id, username=username)
    finally:
        conn.close()


@router.delete("/infrastructure/hostels/{hostel_id}", summary="Delete Hostel (Poka-Yoke Protected)")
def delete_hostel(
    hostel_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("hostels:delete")),
):
    verify_infrastructure_scope(current_user, hostel_id=hostel_id, conn=conn)
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.delete_hostel(conn, hostel_id, user_id=user_id, username=username)
    finally:
        conn.close()


# =============================================================
# Module D: Building Management
# =============================================================

@router.get("/infrastructure/buildings", summary="List Buildings Extended")
def list_buildings_extended(
    hostel_id: Optional[int] = Query(None),
    campus_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("buildings:read", "infrastructure:read")),
):
    try:
        return InfrastructureService.list_buildings_extended(
            conn, hostel_id=hostel_id, campus_id=campus_id, search=search
        )
    finally:
        conn.close()


@router.get("/infrastructure/buildings/{building_id}", summary="Get Building Details by ID")
def get_building(
    building_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("buildings:read", "infrastructure:read")),
):
    try:
        return InfrastructureService.get_building_by_id(conn, building_id)
    finally:
        conn.close()


@router.post("/infrastructure/buildings", status_code=status.HTTP_201_CREATED, summary="Create Building Extended")
def create_building_extended(
    payload: BuildingCreateExt,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("buildings:create")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.create_building_extended(conn, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.put("/infrastructure/buildings/{building_id}", summary="Update Building Extended")
def update_building_extended(
    building_id: int,
    payload: BuildingUpdateExt,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("buildings:update")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.update_building_extended(conn, building_id, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.delete("/infrastructure/buildings/{building_id}", summary="Delete Building (Poka-Yoke Protected)")
def delete_building(
    building_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("buildings:delete")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.delete_building(conn, building_id, user_id=user_id, username=username)
    finally:
        conn.close()


# =============================================================
# Module E: Block Management
# =============================================================

@router.get("/blocks", summary="List Blocks")
def list_blocks(
    building_id: Optional[int] = Query(None),
    hostel_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("blocks:manage", "infrastructure:read")),
):
    try:
        return InfrastructureService.list_blocks(conn, building_id=building_id, hostel_id=hostel_id, search=search)
    finally:
        conn.close()


@router.get("/blocks/{block_id}", summary="Get Block Details by ID")
def get_block(
    block_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("blocks:manage", "infrastructure:read")),
):
    try:
        return InfrastructureService.get_block_by_id(conn, block_id)
    finally:
        conn.close()


@router.post("/blocks", status_code=status.HTTP_201_CREATED, summary="Create Block")
def create_block(
    payload: BlockCreate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("blocks:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.create_block(conn, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.put("/blocks/{block_id}", summary="Update Block")
def update_block(
    block_id: int,
    payload: BlockUpdate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("blocks:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.update_block(conn, block_id, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.delete("/blocks/{block_id}", summary="Delete Block (Poka-Yoke Protected)")
def delete_block(
    block_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("blocks:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.delete_block(conn, block_id, user_id=user_id, username=username)
    finally:
        conn.close()


# =============================================================
# Module F: Floor Management
# =============================================================

@router.get("/floors", summary="List Floors")
def list_floors(
    building_id: Optional[int] = Query(None),
    block_id: Optional[int] = Query(None),
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("floors:manage", "infrastructure:read")),
):
    try:
        return InfrastructureService.list_floors(conn, building_id=building_id, block_id=block_id)
    finally:
        conn.close()


@router.get("/floors/{floor_id}", summary="Get Floor Details by ID")
def get_floor(
    floor_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("floors:manage", "infrastructure:read")),
):
    try:
        return InfrastructureService.get_floor_by_id(conn, floor_id)
    finally:
        conn.close()


@router.post("/floors", status_code=status.HTTP_201_CREATED, summary="Create Floor")
def create_floor(
    payload: FloorCreate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("floors:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.create_floor(conn, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.put("/floors/{floor_id}", summary="Update Floor")
def update_floor(
    floor_id: int,
    payload: FloorUpdate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("floors:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.update_floor(conn, floor_id, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.delete("/floors/{floor_id}", summary="Delete Floor (Poka-Yoke Protected)")
def delete_floor(
    floor_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("floors:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.delete_floor(conn, floor_id, user_id=user_id, username=username)
    finally:
        conn.close()


# =============================================================
# Module G: Room Management & Maintenance
# =============================================================

@router.get("/rooms", summary="List Rooms with Pagination & Filter Scopes")
def list_rooms(
    floor_id: Optional[int] = Query(None),
    building_id: Optional[int] = Query(None),
    hostel_id: Optional[int] = Query(None),
    campus_id: Optional[int] = Query(None),
    room_type: Optional[str] = Query(None),
    maintenance_status: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("rooms:read", "infrastructure:read")),
):
    try:
        return InfrastructureService.list_rooms(
            conn, floor_id=floor_id, building_id=building_id, hostel_id=hostel_id,
            campus_id=campus_id, room_type=room_type, maintenance_status=maintenance_status,
            status=status, search=search, page=page, limit=limit
        )
    finally:
        conn.close()


@router.get("/rooms/{room_id}", summary="Get Room Details & Current Occupants")
def get_room(
    room_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("rooms:read", "infrastructure:read")),
):
    try:
        return InfrastructureService.get_room_by_id(conn, room_id)
    finally:
        conn.close()


@router.post("/rooms", status_code=status.HTTP_201_CREATED, summary="Create Room (with auto bed generation)")
def create_room(
    payload: RoomCreate,
    auto_create_beds: bool = Query(True, description="Automatically generate beds matching room capacity"),
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("rooms:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.create_room(
            conn, payload, user_id=user_id, username=username, auto_create_beds=auto_create_beds
        )
    finally:
        conn.close()


@router.put("/rooms/{room_id}", summary="Update Room Details")
def update_room(
    room_id: int,
    payload: RoomUpdate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("rooms:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.update_room(conn, room_id, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.patch("/rooms/{room_id}/capacity", summary="Update Room Capacity (Poka-Yoke Protected)")
def update_room_capacity(
    room_id: int,
    payload: RoomCapacityUpdate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("rooms:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.update_room_capacity(
            conn, room_id, payload.capacity, user_id=user_id, username=username
        )
    finally:
        conn.close()


@router.patch("/rooms/{room_id}/maintenance", summary="Update Room Maintenance Status (Auto Syncs Beds)")
def update_room_maintenance(
    room_id: int,
    payload: RoomMaintenanceUpdate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("rooms:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.update_room_maintenance(
            conn, room_id, payload.maintenance_status, payload.status, user_id=user_id, username=username
        )
    finally:
        conn.close()


@router.delete("/rooms/{room_id}", summary="Delete Room (Poka-Yoke Protected)")
def delete_room(
    room_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("rooms:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.delete_room(conn, room_id, user_id=user_id, username=username)
    finally:
        conn.close()


# =============================================================
# Module H: Bed Management & Allocation Locks
# =============================================================

@router.get("/beds", summary="List Beds with Allocation & Maintenance Status")
def list_beds(
    room_id: Optional[int] = Query(None),
    hostel_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    maintenance_status: Optional[str] = Query(None),
    is_active: Optional[int] = Query(None, ge=0, le=1),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("beds:manage", "infrastructure:read")),
):
    try:
        return InfrastructureService.list_beds(
            conn, room_id=room_id, hostel_id=hostel_id, status=status,
            maintenance_status=maintenance_status, is_active=is_active,
            search=search, page=page, limit=limit
        )
    finally:
        conn.close()


@router.get("/beds/{bed_id}", summary="Get Bed Details by ID")
def get_bed(
    bed_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("beds:manage", "infrastructure:read")),
):
    try:
        return InfrastructureService.get_bed_by_id(conn, bed_id)
    finally:
        conn.close()


@router.post("/beds", status_code=status.HTTP_201_CREATED, summary="Create Bed")
def create_bed(
    payload: BedCreate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("beds:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.create_bed(conn, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.put("/beds/{bed_id}", summary="Update Bed")
def update_bed(
    bed_id: int,
    payload: BedUpdate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("beds:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.update_bed(conn, bed_id, payload, user_id=user_id, username=username)
    finally:
        conn.close()


@router.patch("/beds/{bed_id}/maintenance", summary="Update Bed Maintenance Status (Locks Bed from Allocation)")
def update_bed_maintenance(
    bed_id: int,
    payload: BedMaintenanceUpdate,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("beds:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.update_bed_maintenance(
            conn, bed_id, payload.maintenance_status, payload.status, payload.notes,
            user_id=user_id, username=username
        )
    finally:
        conn.close()


@router.delete("/beds/{bed_id}", summary="Delete Bed (Poka-Yoke Protected)")
def delete_bed(
    bed_id: int,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("beds:manage")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.delete_bed(conn, bed_id, user_id=user_id, username=username)
    finally:
        conn.close()


# =============================================================
# Module I: Hierarchy Tree Visualization
# =============================================================

@router.get("/infrastructure/hierarchy", summary="Get 8-Tier Infrastructure Tree")
def get_hierarchy(
    campus_id: Optional[int] = Query(None),
    hostel_id: Optional[int] = Query(None),
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("infrastructure:read", "infrastructure.hierarchy.read")),
):
    try:
        return InfrastructureService.get_hierarchy(conn, campus_id=campus_id, hostel_id=hostel_id)
    finally:
        conn.close()


# =============================================================
# Module J: Capacity & Occupancy Calculation Engine
# =============================================================

@router.get("/infrastructure/capacity", summary="Get Reconciled Capacity & Occupancy Analytics")
def get_capacity(
    campus_id: Optional[int] = Query(None),
    hostel_id: Optional[int] = Query(None),
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("infrastructure:read", "infrastructure.capacity.read")),
):
    try:
        return InfrastructureService.get_capacity_metrics(conn, campus_id=campus_id, hostel_id=hostel_id)
    finally:
        conn.close()


# =============================================================
# Module L: Bulk Import & Export
# =============================================================

@router.post("/infrastructure/import", summary="Bulk Import Entities with Dry-Run Pre-Flight Validation")
def bulk_import(
    payload: BulkImportRequest,
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("infrastructure:import", "infrastructure.data.import")),
):
    try:
        user_id = current_user.get("id")
        username = current_user.get("username")
        return InfrastructureService.bulk_import(
            conn, payload.entity_type, payload.records, dry_run=payload.dry_run,
            user_id=user_id, username=username
        )
    finally:
        conn.close()


@router.get("/infrastructure/export", summary="Export Infrastructure Entities as CSV or JSON")
def bulk_export(
    entity_type: str = Query(..., description="campuses, hostels, buildings, blocks, floors, rooms, beds"),
    campus_id: Optional[int] = Query(None),
    hostel_id: Optional[int] = Query(None),
    format: str = Query("json", description="json or csv"),
    conn=Depends(get_db_connection),
    current_user: Dict[str, Any] = Depends(require_permissions("infrastructure:export", "infrastructure.data.export")),
):
    try:
        data = InfrastructureService.bulk_export(
            conn, entity_type, campus_id=campus_id, hostel_id=hostel_id, export_format=format
        )
        if format.lower() == "csv":
            return PlainTextResponse(
                content=data,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={entity_type}_export.csv"},
            )
        return data
    finally:
        conn.close()
