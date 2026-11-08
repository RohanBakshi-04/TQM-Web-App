"""Pydantic Data Transfer Objects for SA-02: Complete Institution, Campus & Hostel Management.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time, Poka-Yoke Error Proofing, Zero-Defect Delivery
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field


# ==========================================
# Module A: Institution Profile & Configuration
# ==========================================

class InstitutionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    code: Optional[str] = Field(None, min_length=2, max_length=30)
    legal_name: Optional[str] = Field(None, max_length=200)
    established_year: Optional[int] = Field(None, ge=1800, le=2100)
    affiliation: Optional[str] = Field(None, max_length=150)
    website: Optional[str] = Field(None, max_length=200)
    contact_email: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    logo_url: Optional[str] = Field(None, max_length=255)
    timezone: Optional[str] = Field(None, max_length=50)
    academic_year_start: Optional[str] = Field(None, max_length=10)
    academic_year_end: Optional[str] = Field(None, max_length=10)
    currency: Optional[str] = Field(None, max_length=10)
    is_active: Optional[int] = Field(None, ge=0, le=1)


class InstitutionConfigUpdate(BaseModel):
    timezone: Optional[str] = Field("Asia/Kolkata", max_length=50)
    academic_year_start: Optional[str] = Field("07-01", max_length=10)
    academic_year_end: Optional[str] = Field("06-30", max_length=10)
    currency: Optional[str] = Field("INR", max_length=10)


class InstitutionResponse(BaseModel):
    id: int
    name: str
    code: str
    legal_name: Optional[str] = None
    established_year: Optional[int] = None
    affiliation: Optional[str] = None
    website: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "India"
    postal_code: Optional[str] = None
    logo_url: Optional[str] = None
    timezone: Optional[str] = "Asia/Kolkata"
    academic_year_start: Optional[str] = "07-01"
    academic_year_end: Optional[str] = "06-30"
    currency: Optional[str] = "INR"
    is_active: int = 1
    total_campuses: int = 0
    total_hostels: int = 0
    total_capacity: int = 0
    total_occupancy: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==========================================
# Module B: Multi-Campus Management
# ==========================================

class CampusCreate(BaseModel):
    institution_id: Optional[int] = Field(1, description="Parent Institution ID")
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=2, max_length=30)
    address: str = Field(..., min_length=2, max_length=255)
    city: Optional[str] = Field("", max_length=100)
    state: Optional[str] = Field("", max_length=100)
    country: Optional[str] = Field("India", max_length=100)
    postal_code: Optional[str] = Field("", max_length=20)
    contact_person: Optional[str] = Field("", max_length=100)
    contact_email: Optional[str] = Field("", max_length=100)
    contact_phone: Optional[str] = Field("", max_length=30)
    admin_id: Optional[int] = None
    emergency_contact: Optional[str] = Field("", max_length=50)
    operating_status: Optional[str] = Field("Active", description="Active, Inactive, Under_Maintenance")
    is_active: int = Field(1, ge=0, le=1)


class CampusUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    code: Optional[str] = Field(None, min_length=2, max_length=30)
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    contact_person: Optional[str] = Field(None, max_length=100)
    contact_email: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=30)
    admin_id: Optional[int] = None
    emergency_contact: Optional[str] = Field(None, max_length=50)
    operating_status: Optional[str] = Field(None, description="Active, Inactive, Under_Maintenance")
    is_active: Optional[int] = Field(None, ge=0, le=1)


class CampusStatusUpdate(BaseModel):
    operating_status: str = Field(..., description="Active, Inactive, Under_Maintenance")
    is_active: Optional[int] = Field(1, ge=0, le=1)


class CampusAdminAssign(BaseModel):
    admin_id: Optional[int] = None
    contact_person: Optional[str] = Field(None, max_length=100)
    contact_email: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=30)


class CampusResponse(BaseModel):
    id: int
    institution_id: int
    institution_name: Optional[str] = None
    name: str
    code: str
    address: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "India"
    postal_code: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    admin_id: Optional[int] = None
    admin_name: Optional[str] = None
    emergency_contact: Optional[str] = None
    operating_status: str = "Active"
    is_active: int = 1
    hostels_count: int = 0
    buildings_count: int = 0
    total_capacity: int = 0
    operational_capacity: int = 0
    occupied_beds: int = 0
    available_beds: int = 0
    occupancy_rate_pct: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==========================================
# Module C: Hostel Management & Categories
# ==========================================

class HostelCreateExt(BaseModel):
    institution_id: Optional[int] = 1
    campus_id: int = Field(..., description="Parent Campus ID")
    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=2, max_length=20)
    hostel_type: str = Field("Co-Ed", description="Boys, Girls, Co-Ed")
    category: Optional[str] = Field("General", description="General, Engineering, Medical, Management, International, Postgraduate, Executive")
    address: Optional[str] = Field("", max_length=255)
    warden_id: Optional[int] = None
    assistant_warden_id: Optional[int] = None
    supervisor_id: Optional[int] = None
    contact_phone: Optional[str] = Field("", max_length=30)
    contact_email: Optional[str] = Field("", max_length=100)
    curfew_time: Optional[str] = Field("22:00", max_length=10)
    visitor_hours: Optional[str] = Field("16:00 - 19:00", max_length=30)
    mess_type: Optional[str] = Field("Veg and Non-Veg", max_length=50)
    amenities: Optional[str] = Field("[]")
    rules_policies: Optional[str] = Field("")
    is_active: int = Field(1, ge=0, le=1)


class HostelUpdateExt(BaseModel):
    campus_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    code: Optional[str] = Field(None, min_length=2, max_length=20)
    hostel_type: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    warden_id: Optional[int] = None
    assistant_warden_id: Optional[int] = None
    supervisor_id: Optional[int] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    curfew_time: Optional[str] = None
    visitor_hours: Optional[str] = None
    mess_type: Optional[str] = None
    amenities: Optional[str] = None
    rules_policies: Optional[str] = None
    is_active: Optional[int] = Field(None, ge=0, le=1)


class HostelLeadershipAssign(BaseModel):
    warden_id: Optional[int] = None
    assistant_warden_id: Optional[int] = None
    supervisor_id: Optional[int] = None


class HostelCategoryUpdate(BaseModel):
    category: str = Field(..., description="General, Engineering, Medical, Management, International, Postgraduate, Executive")


class HostelDetailResponse(BaseModel):
    id: int
    institution_id: Optional[int] = 1
    campus_id: Optional[int] = None
    campus_name: Optional[str] = None
    name: str
    code: str
    hostel_type: str
    category: str = "General"
    address: Optional[str] = None
    warden_id: Optional[int] = None
    warden_name: Optional[str] = None
    assistant_warden_id: Optional[int] = None
    assistant_warden_name: Optional[str] = None
    supervisor_id: Optional[int] = None
    supervisor_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    curfew_time: Optional[str] = "22:00"
    visitor_hours: Optional[str] = "16:00 - 19:00"
    mess_type: Optional[str] = "Veg and Non-Veg"
    amenities: Optional[str] = "[]"
    rules_policies: Optional[str] = ""
    is_active: int = 1
    buildings_count: int = 0
    blocks_count: int = 0
    rooms_count: int = 0
    physical_capacity: int = 0
    operational_capacity: int = 0
    occupied_beds: int = 0
    available_beds: int = 0
    occupancy_rate_pct: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==========================================
# Module D: Building Management
# ==========================================

class BuildingCreateExt(BaseModel):
    hostel_id: int
    campus_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    total_floors: int = Field(..., ge=1, le=50)
    construction_year: Optional[int] = Field(None, ge=1800, le=2100)
    condition_rating: Optional[str] = Field("Good", description="Excellent, Good, Fair, Poor, Under_Renovation")
    fire_safety_cert_date: Optional[str] = None
    emergency_exits_count: Optional[int] = Field(2, ge=1, le=20)
    elevators_count: Optional[int] = Field(0, ge=0, le=20)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: int = Field(1, ge=0, le=1)


class BuildingUpdateExt(BaseModel):
    hostel_id: Optional[int] = None
    campus_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    total_floors: Optional[int] = Field(None, ge=1, le=50)
    construction_year: Optional[int] = Field(None, ge=1800, le=2100)
    condition_rating: Optional[str] = Field(None, description="Excellent, Good, Fair, Poor, Under_Renovation")
    fire_safety_cert_date: Optional[str] = None
    emergency_exits_count: Optional[int] = Field(None, ge=1, le=20)
    elevators_count: Optional[int] = Field(None, ge=0, le=20)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[int] = Field(None, ge=0, le=1)


class BuildingResponse(BaseModel):
    id: int
    hostel_id: int
    hostel_name: Optional[str] = None
    campus_id: Optional[int] = None
    campus_name: Optional[str] = None
    name: str
    code: str
    total_floors: int
    construction_year: Optional[int] = None
    condition_rating: str = "Good"
    fire_safety_cert_date: Optional[str] = None
    emergency_exits_count: int = 2
    elevators_count: int = 0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: int = 1
    blocks_count: int = 0
    floors_count: int = 0
    rooms_count: int = 0
    physical_capacity: int = 0
    operational_capacity: int = 0
    occupied_beds: int = 0
    available_beds: int = 0
    occupancy_rate_pct: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==========================================
# Module E: Block Management
# ==========================================

class BlockCreate(BaseModel):
    building_id: int
    hostel_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = Field("", max_length=255)
    is_active: int = Field(1, ge=0, le=1)


class BlockUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[int] = Field(None, ge=0, le=1)


class BlockResponse(BaseModel):
    id: int
    building_id: int
    building_name: Optional[str] = None
    hostel_id: int
    hostel_name: Optional[str] = None
    name: str
    code: str
    description: Optional[str] = None
    is_active: int = 1
    floors_count: int = 0
    rooms_count: int = 0
    physical_capacity: int = 0
    operational_capacity: int = 0
    occupied_beds: int = 0
    available_beds: int = 0
    occupancy_rate_pct: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==========================================
# Module F: Floor Management
# ==========================================

class FloorCreate(BaseModel):
    building_id: int
    block_id: Optional[int] = None
    floor_number: int = Field(..., ge=0, le=50)
    floor_name: str = Field(..., min_length=1, max_length=50)
    is_active: int = Field(1, ge=0, le=1)


class FloorUpdate(BaseModel):
    block_id: Optional[int] = None
    floor_number: Optional[int] = Field(None, ge=0, le=50)
    floor_name: Optional[str] = Field(None, min_length=1, max_length=50)
    is_active: Optional[int] = Field(None, ge=0, le=1)


class FloorResponse(BaseModel):
    id: int
    building_id: int
    building_name: Optional[str] = None
    block_id: Optional[int] = None
    block_name: Optional[str] = None
    floor_number: int
    floor_name: str
    is_active: int = 1
    rooms_count: int = 0
    physical_capacity: int = 0
    operational_capacity: int = 0
    occupied_beds: int = 0
    available_beds: int = 0
    occupancy_rate_pct: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==========================================
# Module G: Room Management & Maintenance
# ==========================================

class RoomCreate(BaseModel):
    floor_id: int
    room_number: str = Field(..., min_length=1, max_length=30)
    room_type: str = Field("Double", description="Single, Double, Triple, Quad, Dormitory")
    capacity: int = Field(..., ge=1, le=10)
    base_fee: float = Field(0.0, ge=0.0)
    status: str = Field("Available", description="Available, Occupied, Under Maintenance, Reserved")
    maintenance_status: str = Field("Operational", description="Operational, Maintenance_Pending, Under_Repair, Decommissioned")
    condition_rating: Optional[str] = Field("Good", description="Excellent, Good, Fair, Poor")
    amenities: Optional[str] = Field("[]")
    is_ac: int = Field(0, ge=0, le=1)
    attached_washroom: int = Field(0, ge=0, le=1)
    is_active: int = Field(1, ge=0, le=1)


class RoomUpdate(BaseModel):
    room_number: Optional[str] = Field(None, min_length=1, max_length=30)
    room_type: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=1, le=10)
    base_fee: Optional[float] = Field(None, ge=0.0)
    status: Optional[str] = None
    maintenance_status: Optional[str] = None
    condition_rating: Optional[str] = None
    amenities: Optional[str] = None
    is_ac: Optional[int] = Field(None, ge=0, le=1)
    attached_washroom: Optional[int] = Field(None, ge=0, le=1)
    is_active: Optional[int] = Field(None, ge=0, le=1)


class RoomCapacityUpdate(BaseModel):
    capacity: int = Field(..., ge=1, le=10, description="New room capacity. Cannot be less than current active occupants.")


class RoomMaintenanceUpdate(BaseModel):
    maintenance_status: str = Field(..., description="Operational, Maintenance_Pending, Under_Repair, Decommissioned")
    status: Optional[str] = Field(None, description="Available, Occupied, Under Maintenance, Reserved")


class RoomResponse(BaseModel):
    id: int
    floor_id: int
    floor_name: Optional[str] = None
    floor_number: Optional[int] = None
    block_id: Optional[int] = None
    block_name: Optional[str] = None
    building_id: Optional[int] = None
    building_name: Optional[str] = None
    hostel_id: Optional[int] = None
    hostel_name: Optional[str] = None
    campus_id: Optional[int] = None
    campus_name: Optional[str] = None
    room_number: str
    room_type: str
    capacity: int
    base_fee: float
    status: str
    maintenance_status: str = "Operational"
    condition_rating: str = "Good"
    amenities: str = "[]"
    is_ac: int = 0
    attached_washroom: int = 0
    is_active: int = 1
    beds_count: int = 0
    occupied_beds: int = 0
    available_beds: int = 0
    occupants: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==========================================
# Module H: Bed Management & Allocation Locks
# ==========================================

class BedCreate(BaseModel):
    room_id: int
    bed_number: str = Field(..., min_length=1, max_length=20)
    status: str = Field("Available", description="Available, Occupied, Maintenance, Reserved")
    maintenance_status: str = Field("Operational", description="Operational, Under_Repair, Out_Of_Service")
    monthly_rate: Optional[float] = Field(0.0, ge=0.0)
    is_active: int = Field(1, ge=0, le=1)


class BedUpdate(BaseModel):
    bed_number: Optional[str] = Field(None, min_length=1, max_length=20)
    status: Optional[str] = None
    maintenance_status: Optional[str] = None
    monthly_rate: Optional[float] = Field(None, ge=0.0)
    is_active: Optional[int] = Field(None, ge=0, le=1)


class BedMaintenanceUpdate(BaseModel):
    maintenance_status: str = Field(..., description="Operational, Under_Repair, Out_Of_Service")
    status: Optional[str] = Field(None, description="Available, Occupied, Maintenance, Reserved")
    notes: Optional[str] = None


class BedResponse(BaseModel):
    id: int
    room_id: int
    room_number: Optional[str] = None
    floor_id: Optional[int] = None
    building_id: Optional[int] = None
    hostel_id: Optional[int] = None
    bed_number: str
    status: str
    maintenance_status: str = "Operational"
    monthly_rate: float = 0.0
    is_active: int = 1
    is_allocatable: bool = True
    occupant_student_id: Optional[str] = None
    occupant_student_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==========================================
# Module I: Hierarchy Tree Visualization
# ==========================================

class HierarchyNode(BaseModel):
    id: int
    name: str
    code: str
    node_type: str = Field(..., description="institution, campus, hostel, building, block, floor, room, bed")
    status: Optional[str] = "Active"
    is_active: int = 1
    capacity: int = 0
    operational_capacity: int = 0
    occupancy: int = 0
    occupancy_rate_pct: float = 0.0
    children: List["HierarchyNode"] = Field(default_factory=list)


# ==========================================
# Module J: Capacity & Occupancy Calculation Engine
# ==========================================

class CapacityBreakdownItem(BaseModel):
    id: int
    name: str
    code: str
    physical_capacity: int = 0
    operational_capacity: int = 0
    occupied_beds: int = 0
    available_beds: int = 0
    maintenance_beds: int = 0
    occupancy_rate_pct: float = 0.0


class CapacityMetrics(BaseModel):
    total_physical_capacity: int = 0
    total_operational_capacity: int = 0
    total_occupied_beds: int = 0
    total_available_beds: int = 0
    total_maintenance_beds: int = 0
    overall_occupancy_rate_pct: float = 0.0
    by_campus: List[CapacityBreakdownItem] = Field(default_factory=list)
    by_hostel: List[CapacityBreakdownItem] = Field(default_factory=list)
    by_room_type: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


# ==========================================
# Module L: Bulk Import & Export
# ==========================================

class BulkImportRequest(BaseModel):
    entity_type: str = Field(..., description="campuses, hostels, buildings, blocks, floors, rooms, beds")
    records: List[Dict[str, Any]] = Field(..., min_length=1)
    dry_run: bool = Field(True, description="When True, validates without committing changes")


class BulkImportResult(BaseModel):
    success: bool
    dry_run: bool
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: List[str] = Field(default_factory=list)
    created_count: int = 0
    updated_count: int = 0
