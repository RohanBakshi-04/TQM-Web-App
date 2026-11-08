"""Infrastructure Business Logic Service (SA-02).

Implements end-to-end administration for Institutions, Campuses, Hostels,
Buildings, Blocks, Floors, Rooms, and Beds.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA), Poka-Yoke Error Proofing, Zero-Defect Delivery
"""

import csv
import io
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status

from backend.app.models.infrastructure_dto import (
    BedCreate,
    BedMaintenanceUpdate,
    BedUpdate,
    BlockCreate,
    BlockUpdate,
    BuildingCreateExt,
    BuildingUpdateExt,
    CampusAdminAssign,
    CampusCreate,
    CampusUpdate,
    FloorCreate,
    FloorUpdate,
    HostelCreateExt,
    HostelLeadershipAssign,
    HostelUpdateExt,
    InstitutionConfigUpdate,
    InstitutionUpdate,
    RoomCreate,
    RoomUpdate,
)
from backend.app.services.cache_invalidation import CacheInvalidator
from backend.app.utils.logger import logger


class InfrastructureService:
    """Enterprise Infrastructure Management Service."""

    # -------------------------------------------------------------
    # Helper: Audit Logger
    # -------------------------------------------------------------
    @staticmethod
    def _log_audit(
        conn: sqlite3.Connection,
        user_id: Optional[int],
        username: Optional[str],
        action: str,
        entity_name: str,
        entity_id: Any,
        details: str,
        latency_ms: float = 0.5,
    ) -> None:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (user_id, username or "system", action, entity_name, str(entity_id), details, latency_ms),
            )
        except Exception as e:
            logger.warning(f"Failed to record audit log: {e}")

    # =============================================================
    # Module A: Institution Profile & Configuration
    # =============================================================
    @classmethod
    def get_institution(cls, conn: sqlite3.Connection) -> Dict[str, Any]:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM institutions WHERE is_active = 1 LIMIT 1;")
        row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT * FROM institutions LIMIT 1;")
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Institution profile not configured")

        col_names = [col[0] for col in cursor.description]
        inst = dict(zip(col_names, row))

        # Calculate high-level aggregates
        cursor.execute("SELECT COUNT(*) FROM campuses WHERE is_active = 1;")
        total_campuses = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM hostels WHERE is_active = 1;")
        total_hostels = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT 
                COUNT(*) as physical_beds,
                COUNT(CASE WHEN is_active = 1 AND maintenance_status != 'Out_Of_Service' THEN 1 END) as operational_beds
            FROM beds;
            """
        )
        bed_stats = cursor.fetchone()
        total_capacity = bed_stats[1] if bed_stats else 0

        cursor.execute("SELECT COUNT(*) FROM room_allocations WHERE allocation_status = 'Active';")
        total_occupancy = cursor.fetchone()[0]

        inst["total_campuses"] = total_campuses
        inst["total_hostels"] = total_hostels
        inst["total_capacity"] = total_capacity
        inst["total_occupancy"] = total_occupancy
        return inst

    @classmethod
    def update_institution(
        cls,
        conn: sqlite3.Connection,
        data: InstitutionUpdate,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM institutions LIMIT 1;")
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Institution not found")
        inst_id = row[0]

        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return cls.get_institution(conn)

        set_clauses = []
        params = []
        for key, val in update_dict.items():
            set_clauses.append(f"{key} = ?")
            params.append(val)

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(inst_id)

        sql = f"UPDATE institutions SET {', '.join(set_clauses)} WHERE id = ?;"
        cursor.execute(sql, tuple(params))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "UPDATE_INSTITUTION", "institutions", inst_id,
            f"Updated fields: {list(update_dict.keys())}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return cls.get_institution(conn)

    @classmethod
    def update_institution_config(
        cls,
        conn: sqlite3.Connection,
        data: InstitutionConfigUpdate,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM institutions LIMIT 1;")
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Institution not found")
        inst_id = row[0]

        cursor.execute(
            """
            UPDATE institutions 
            SET timezone = ?, academic_year_start = ?, academic_year_end = ?, currency = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (data.timezone, data.academic_year_start, data.academic_year_end, data.currency, inst_id),
        )
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "UPDATE_INSTITUTION_CONFIG", "institutions", inst_id,
            f"Config updated: timezone={data.timezone}, currency={data.currency}", latency_ms
        )
        return cls.get_institution(conn)

    # =============================================================
    # Module B: Multi-Campus Management
    # =============================================================
    @classmethod
    def list_campuses(
        cls,
        conn: sqlite3.Connection,
        operating_status: Optional[str] = None,
        is_active: Optional[int] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        cursor = conn.cursor()
        where_clauses = []
        params = []

        if operating_status:
            where_clauses.append("c.operating_status = ?")
            params.append(operating_status)
        if is_active is not None:
            where_clauses.append("c.is_active = ?")
            params.append(is_active)
        if search:
            where_clauses.append("(c.name LIKE ? OR c.code LIKE ? OR c.city LIKE ?)")
            term = f"%{search.strip()}%"
            params.extend([term, term, term])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            SELECT 
                c.id, c.institution_id, c.name, c.code, c.address, c.city, c.state, c.country,
                c.postal_code, c.contact_person, c.contact_email, c.contact_phone, c.admin_id,
                (u.first_name || ' ' || u.last_name) as admin_name, c.emergency_contact, c.operating_status, c.is_active,
                c.created_at, c.updated_at,
                COUNT(DISTINCT h.id) as hostels_count,
                COUNT(DISTINCT b.id) as buildings_count,
                COUNT(DISTINCT bd.id) as total_capacity,
                COUNT(DISTINCT CASE WHEN bd.is_active = 1 AND bd.maintenance_status != 'Out_Of_Service' THEN bd.id END) as operational_capacity,
                COUNT(DISTINCT CASE WHEN ra.allocation_status = 'Active' THEN ra.id END) as occupied_beds,
                COUNT(DISTINCT CASE WHEN bd.status = 'Available' AND bd.is_active = 1 AND bd.maintenance_status = 'Operational' THEN bd.id END) as available_beds
            FROM campuses c
            LEFT JOIN users u ON c.admin_id = u.id
            LEFT JOIN hostels h ON c.id = h.campus_id
            LEFT JOIN buildings b ON h.id = b.hostel_id
            LEFT JOIN floors f ON b.id = f.building_id
            LEFT JOIN rooms r ON f.id = r.floor_id
            LEFT JOIN beds bd ON r.id = bd.room_id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            {where_sql}
            GROUP BY c.id
            ORDER BY c.name ASC;
        """
        cursor.execute(query, tuple(params))
        col_names = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            item = dict(zip(col_names, row))
            op_cap = item.get("operational_capacity") or 0
            occ = item.get("occupied_beds") or 0
            item["occupancy_rate_pct"] = round((occ / op_cap * 100.0), 2) if op_cap > 0 else 0.0
            results.append(item)
        return results

    @classmethod
    def get_campus_by_id(cls, conn: sqlite3.Connection, campus_id: int) -> Dict[str, Any]:
        campuses = cls.list_campuses(conn)
        for c in campuses:
            if c["id"] == campus_id:
                return c
        raise HTTPException(status_code=404, detail=f"Campus with ID {campus_id} not found")

    @classmethod
    def create_campus(
        cls,
        conn: sqlite3.Connection,
        data: CampusCreate,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Check unique code
        cursor.execute("SELECT id FROM campuses WHERE code = ?;", (data.code,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Campus code '{data.code}' already exists")

        # Check unique name
        cursor.execute("SELECT id FROM campuses WHERE name = ?;", (data.name,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Campus name '{data.name}' already exists")

        cursor.execute(
            """
            INSERT INTO campuses (
                institution_id, name, code, address, city, state, country, postal_code,
                contact_person, contact_email, contact_phone, admin_id, emergency_contact,
                operating_status, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                data.institution_id or 1,
                data.name,
                data.code,
                data.address,
                data.city,
                data.state,
                data.country or "India",
                data.postal_code,
                data.contact_person,
                data.contact_email,
                data.contact_phone,
                data.admin_id,
                data.emergency_contact,
                data.operating_status or "Active",
                data.is_active,
            ),
        )
        new_id = cursor.lastrowid
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "CREATE_CAMPUS", "campuses", new_id,
            f"Created campus {data.name} ({data.code})", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return cls.get_campus_by_id(conn, new_id)

    @classmethod
    def update_campus(
        cls,
        conn: sqlite3.Connection,
        campus_id: int,
        data: CampusUpdate,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM campuses WHERE id = ?;", (campus_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Campus with ID {campus_id} not found")

        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return cls.get_campus_by_id(conn, campus_id)

        if "code" in update_dict:
            cursor.execute("SELECT id FROM campuses WHERE code = ? AND id != ?;", (update_dict["code"], campus_id))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail=f"Campus code '{update_dict['code']}' already in use")

        set_clauses = []
        params = []
        for k, v in update_dict.items():
            set_clauses.append(f"{k} = ?")
            params.append(v)
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(campus_id)

        cursor.execute(f"UPDATE campuses SET {', '.join(set_clauses)} WHERE id = ?;", tuple(params))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "UPDATE_CAMPUS", "campuses", campus_id,
            f"Updated campus fields: {list(update_dict.keys())}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return cls.get_campus_by_id(conn, campus_id)

    @classmethod
    def set_campus_status(
        cls,
        conn: sqlite3.Connection,
        campus_id: int,
        operating_status: str,
        is_active: int,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM campuses WHERE id = ?;", (campus_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Campus with ID {campus_id} not found")

        cursor.execute(
            """
            UPDATE campuses 
            SET operating_status = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?;
            """,
            (operating_status, is_active, campus_id),
        )
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "SET_CAMPUS_STATUS", "campuses", campus_id,
            f"Set status to operating_status={operating_status}, is_active={is_active}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return cls.get_campus_by_id(conn, campus_id)

    @classmethod
    def assign_campus_admin(
        cls,
        conn: sqlite3.Connection,
        campus_id: int,
        data: CampusAdminAssign,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM campuses WHERE id = ?;", (campus_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Campus with ID {campus_id} not found")

        if data.admin_id:
            cursor.execute("SELECT id, first_name, last_name, email, phone FROM users WHERE id = ?;", (data.admin_id,))
            u_row = cursor.fetchone()
            if not u_row:
                raise HTTPException(status_code=404, detail=f"Admin user with ID {data.admin_id} not found")
            contact_p = data.contact_person or f"{u_row[1]} {u_row[2]}".strip()
            contact_e = data.contact_email or u_row[3]
            contact_ph = data.contact_phone or u_row[4]
        else:
            contact_p = data.contact_person
            contact_e = data.contact_email
            contact_ph = data.contact_phone

        cursor.execute(
            """
            UPDATE campuses 
            SET admin_id = ?, contact_person = COALESCE(?, contact_person),
                contact_email = COALESCE(?, contact_email), contact_phone = COALESCE(?, contact_phone),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (data.admin_id, contact_p, contact_e, contact_ph, campus_id),
        )
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "ASSIGN_CAMPUS_ADMIN", "campuses", campus_id,
            f"Assigned admin_id={data.admin_id}", latency_ms
        )
        return cls.get_campus_by_id(conn, campus_id)

    @classmethod
    def delete_campus(
        cls,
        conn: sqlite3.Connection,
        campus_id: int,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Poka-Yoke: Check if hostels exist under campus
        cursor.execute("SELECT COUNT(*) FROM hostels WHERE campus_id = ?;", (campus_id,))
        hostels_count = cursor.fetchone()[0]
        if hostels_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete campus. {hostels_count} hostels are currently associated with this campus.",
            )

        cursor.execute("DELETE FROM campuses WHERE id = ?;", (campus_id,))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "DELETE_CAMPUS", "campuses", campus_id,
            f"Deleted campus ID {campus_id}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return {"success": True, "message": f"Campus {campus_id} deleted successfully"}

    # =============================================================
    # Module C: Hostel Management Extended
    # =============================================================
    @classmethod
    def list_hostels_extended(
        cls,
        conn: sqlite3.Connection,
        campus_id: Optional[int] = None,
        category: Optional[str] = None,
        hostel_type: Optional[str] = None,
        is_active: Optional[int] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        cursor = conn.cursor()
        where_clauses = []
        params = []

        if campus_id:
            where_clauses.append("h.campus_id = ?")
            params.append(campus_id)
        if category:
            where_clauses.append("h.category = ?")
            params.append(category)
        if hostel_type:
            where_clauses.append("h.hostel_type = ?")
            params.append(hostel_type)
        if is_active is not None:
            where_clauses.append("h.is_active = ?")
            params.append(is_active)
        if search:
            where_clauses.append("(h.name LIKE ? OR h.code LIKE ?)")
            term = f"%{search.strip()}%"
            params.extend([term, term])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            SELECT 
                h.id, h.institution_id, h.campus_id, c.name as campus_name,
                h.name, h.code, h.hostel_type, h.category, h.address,
                h.warden_id, (w.first_name || ' ' || w.last_name) as warden_name,
                h.assistant_warden_id, (aw.first_name || ' ' || aw.last_name) as assistant_warden_name,
                h.supervisor_id, (sup.first_name || ' ' || sup.last_name) as supervisor_name,
                h.contact_phone, h.contact_email, h.curfew_time, h.visitor_hours,
                h.mess_type, h.amenities, h.rules_policies, h.is_active,
                h.created_at, h.updated_at,
                COUNT(DISTINCT b.id) as buildings_count,
                COUNT(DISTINCT blk.id) as blocks_count,
                COUNT(DISTINCT r.id) as rooms_count,
                COUNT(DISTINCT bd.id) as physical_capacity,
                COUNT(DISTINCT CASE WHEN bd.is_active = 1 AND bd.maintenance_status != 'Out_Of_Service' THEN bd.id END) as operational_capacity,
                COUNT(DISTINCT CASE WHEN ra.allocation_status = 'Active' THEN ra.id END) as occupied_beds,
                COUNT(DISTINCT CASE WHEN bd.status = 'Available' AND bd.is_active = 1 AND bd.maintenance_status = 'Operational' THEN bd.id END) as available_beds
            FROM hostels h
            LEFT JOIN campuses c ON h.campus_id = c.id
            LEFT JOIN users w ON h.warden_id = w.id
            LEFT JOIN users aw ON h.assistant_warden_id = aw.id
            LEFT JOIN users sup ON h.supervisor_id = sup.id
            LEFT JOIN buildings b ON h.id = b.hostel_id
            LEFT JOIN blocks blk ON h.id = blk.hostel_id
            LEFT JOIN floors f ON b.id = f.building_id
            LEFT JOIN rooms r ON f.id = r.floor_id
            LEFT JOIN beds bd ON r.id = bd.room_id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            {where_sql}
            GROUP BY h.id
            ORDER BY h.name ASC;
        """
        cursor.execute(query, tuple(params))
        col_names = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            item = dict(zip(col_names, row))
            op_cap = item.get("operational_capacity") or 0
            occ = item.get("occupied_beds") or 0
            item["occupancy_rate_pct"] = round((occ / op_cap * 100.0), 2) if op_cap > 0 else 0.0
            results.append(item)
        return results

    @classmethod
    def get_hostel_detail(cls, conn: sqlite3.Connection, hostel_id: int) -> Dict[str, Any]:
        hostels = cls.list_hostels_extended(conn)
        for h in hostels:
            if h["id"] == hostel_id:
                return h
        raise HTTPException(status_code=404, detail=f"Hostel with ID {hostel_id} not found")

    @classmethod
    def create_hostel_extended(
        cls,
        conn: sqlite3.Connection,
        data: HostelCreateExt,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Check unique code
        cursor.execute("SELECT id FROM hostels WHERE code = ?;", (data.code,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Hostel code '{data.code}' already exists")

        # Verify campus exists
        cursor.execute("SELECT id FROM campuses WHERE id = ?;", (data.campus_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Campus with ID {data.campus_id} does not exist")

        cursor.execute(
            """
            INSERT INTO hostels (
                institution_id, campus_id, name, code, hostel_type, category, address,
                warden_id, assistant_warden_id, supervisor_id, contact_phone, contact_email,
                curfew_time, visitor_hours, mess_type, amenities, rules_policies, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                data.institution_id or 1,
                data.campus_id,
                data.name,
                data.code,
                data.hostel_type,
                data.category or "General",
                data.address or "",
                data.warden_id,
                data.assistant_warden_id,
                data.supervisor_id,
                data.contact_phone or "",
                data.contact_email or "",
                data.curfew_time or "22:00",
                data.visitor_hours or "16:00 - 19:00",
                data.mess_type or "Veg and Non-Veg",
                data.amenities or "[]",
                data.rules_policies or "",
                data.is_active,
            ),
        )
        new_id = cursor.lastrowid
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "CREATE_HOSTEL", "hostels", new_id,
            f"Created hostel {data.name} ({data.code})", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation(new_id)
        return cls.get_hostel_detail(conn, new_id)

    @classmethod
    def update_hostel_extended(
        cls,
        conn: sqlite3.Connection,
        hostel_id: int,
        data: HostelUpdateExt,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM hostels WHERE id = ?;", (hostel_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Hostel with ID {hostel_id} not found")

        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return cls.get_hostel_detail(conn, hostel_id)

        if "code" in update_dict:
            cursor.execute("SELECT id FROM hostels WHERE code = ? AND id != ?;", (update_dict["code"], hostel_id))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail=f"Hostel code '{update_dict['code']}' already exists")

        set_clauses = []
        params = []
        for k, v in update_dict.items():
            set_clauses.append(f"{k} = ?")
            params.append(v)
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(hostel_id)

        cursor.execute(f"UPDATE hostels SET {', '.join(set_clauses)} WHERE id = ?;", tuple(params))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "UPDATE_HOSTEL", "hostels", hostel_id,
            f"Updated fields: {list(update_dict.keys())}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation(hostel_id)
        return cls.get_hostel_detail(conn, hostel_id)

    @classmethod
    def assign_hostel_leadership(
        cls,
        conn: sqlite3.Connection,
        hostel_id: int,
        data: HostelLeadershipAssign,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM hostels WHERE id = ?;", (hostel_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Hostel with ID {hostel_id} not found")

        cursor.execute(
            """
            UPDATE hostels 
            SET warden_id = ?, assistant_warden_id = ?, supervisor_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (data.warden_id, data.assistant_warden_id, data.supervisor_id, hostel_id),
        )
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "ASSIGN_HOSTEL_LEADERSHIP", "hostels", hostel_id,
            f"Updated leadership: warden={data.warden_id}, asst={data.assistant_warden_id}, sup={data.supervisor_id}",
            latency_ms,
        )
        return cls.get_hostel_detail(conn, hostel_id)

    @classmethod
    def update_hostel_category(
        cls,
        conn: sqlite3.Connection,
        hostel_id: int,
        category: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM hostels WHERE id = ?;", (hostel_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Hostel with ID {hostel_id} not found")

        cursor.execute(
            "UPDATE hostels SET category = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
            (category, hostel_id),
        )
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "UPDATE_HOSTEL_CATEGORY", "hostels", hostel_id,
            f"Category updated to {category}", latency_ms
        )
        return cls.get_hostel_detail(conn, hostel_id)

    @classmethod
    def delete_hostel(
        cls,
        conn: sqlite3.Connection,
        hostel_id: int,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Check for active allocations
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM room_allocations ra
            JOIN beds bd ON ra.bed_id = bd.id
            JOIN rooms r ON bd.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            WHERE b.hostel_id = ? AND ra.allocation_status = 'Active';
            """,
            (hostel_id,),
        )
        active_allocs = cursor.fetchone()[0]
        if active_allocs > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete hostel. {active_allocs} active student room allocations exist.",
            )

        cursor.execute("DELETE FROM hostels WHERE id = ?;", (hostel_id,))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "DELETE_HOSTEL", "hostels", hostel_id,
            f"Deleted hostel ID {hostel_id}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation(hostel_id)
        return {"success": True, "message": f"Hostel {hostel_id} deleted successfully"}

    # =============================================================
    # Module D: Building Management
    # =============================================================
    @classmethod
    def list_buildings_extended(
        cls,
        conn: sqlite3.Connection,
        hostel_id: Optional[int] = None,
        campus_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        cursor = conn.cursor()
        where_clauses = []
        params = []

        if hostel_id:
            where_clauses.append("b.hostel_id = ?")
            params.append(hostel_id)
        if campus_id:
            where_clauses.append("b.campus_id = ?")
            params.append(campus_id)
        if search:
            where_clauses.append("(b.name LIKE ? OR b.code LIKE ?)")
            term = f"%{search.strip()}%"
            params.extend([term, term])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            SELECT 
                b.id, b.hostel_id, h.name as hostel_name, b.campus_id, c.name as campus_name,
                b.name, b.code, b.total_floors, b.construction_year, b.condition_rating,
                b.fire_safety_cert_date, b.emergency_exits_count, b.elevators_count,
                b.latitude, b.longitude, b.is_active, b.created_at, b.updated_at,
                COUNT(DISTINCT blk.id) as blocks_count,
                COUNT(DISTINCT f.id) as floors_count,
                COUNT(DISTINCT r.id) as rooms_count,
                COUNT(DISTINCT bd.id) as physical_capacity,
                COUNT(DISTINCT CASE WHEN bd.is_active = 1 AND bd.maintenance_status != 'Out_Of_Service' THEN bd.id END) as operational_capacity,
                COUNT(DISTINCT CASE WHEN ra.allocation_status = 'Active' THEN ra.id END) as occupied_beds,
                COUNT(DISTINCT CASE WHEN bd.status = 'Available' AND bd.is_active = 1 AND bd.maintenance_status = 'Operational' THEN bd.id END) as available_beds
            FROM buildings b
            LEFT JOIN hostels h ON b.hostel_id = h.id
            LEFT JOIN campuses c ON b.campus_id = c.id
            LEFT JOIN blocks blk ON b.id = blk.building_id
            LEFT JOIN floors f ON b.id = f.building_id
            LEFT JOIN rooms r ON f.id = r.floor_id
            LEFT JOIN beds bd ON r.id = bd.room_id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            {where_sql}
            GROUP BY b.id
            ORDER BY b.name ASC;
        """
        cursor.execute(query, tuple(params))
        col_names = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            item = dict(zip(col_names, row))
            op_cap = item.get("operational_capacity") or 0
            occ = item.get("occupied_beds") or 0
            item["occupancy_rate_pct"] = round((occ / op_cap * 100.0), 2) if op_cap > 0 else 0.0
            results.append(item)
        return results

    @classmethod
    def get_building_by_id(cls, conn: sqlite3.Connection, building_id: int) -> Dict[str, Any]:
        blds = cls.list_buildings_extended(conn)
        for b in blds:
            if b["id"] == building_id:
                return b
        raise HTTPException(status_code=404, detail=f"Building with ID {building_id} not found")

    @classmethod
    def create_building_extended(
        cls,
        conn: sqlite3.Connection,
        data: BuildingCreateExt,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Check unique code
        cursor.execute("SELECT id FROM buildings WHERE code = ?;", (data.code,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Building code '{data.code}' already exists")

        # Resolve campus_id from hostel if not provided
        cursor.execute("SELECT campus_id FROM hostels WHERE id = ?;", (data.hostel_id,))
        h_row = cursor.fetchone()
        if not h_row:
            raise HTTPException(status_code=400, detail=f"Hostel with ID {data.hostel_id} does not exist")
        campus_id = data.campus_id or h_row[0] or 1

        cursor.execute(
            """
            INSERT INTO buildings (
                hostel_id, campus_id, name, code, total_floors, construction_year,
                condition_rating, fire_safety_cert_date, emergency_exits_count,
                elevators_count, latitude, longitude, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                data.hostel_id,
                campus_id,
                data.name,
                data.code,
                data.total_floors,
                data.construction_year,
                data.condition_rating or "Good",
                data.fire_safety_cert_date,
                data.emergency_exits_count or 2,
                data.elevators_count or 0,
                data.latitude,
                data.longitude,
                data.is_active,
            ),
        )
        new_id = cursor.lastrowid

        # Auto-create default primary block for the building
        cursor.execute(
            """
            INSERT OR IGNORE INTO blocks (building_id, hostel_id, name, code, description, is_active)
            VALUES (?, ?, ?, ?, ?, 1);
            """,
            (new_id, data.hostel_id, f"{data.name} - Main Wing", "BLK-MAIN", "Primary residential wing"),
        )
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "CREATE_BUILDING", "buildings", new_id,
            f"Created building {data.name} ({data.code})", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation(data.hostel_id)
        return cls.get_building_by_id(conn, new_id)

    @classmethod
    def update_building_extended(
        cls,
        conn: sqlite3.Connection,
        building_id: int,
        data: BuildingUpdateExt,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id, hostel_id FROM buildings WHERE id = ?;", (building_id,))
        b_row = cursor.fetchone()
        if not b_row:
            raise HTTPException(status_code=404, detail=f"Building with ID {building_id} not found")
        hostel_id = b_row[1]

        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return cls.get_building_by_id(conn, building_id)

        if "code" in update_dict:
            cursor.execute("SELECT id FROM buildings WHERE code = ? AND id != ?;", (update_dict["code"], building_id))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail=f"Building code '{update_dict['code']}' already exists")

        set_clauses = []
        params = []
        for k, v in update_dict.items():
            set_clauses.append(f"{k} = ?")
            params.append(v)
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(building_id)

        cursor.execute(f"UPDATE buildings SET {', '.join(set_clauses)} WHERE id = ?;", tuple(params))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "UPDATE_BUILDING", "buildings", building_id,
            f"Updated fields: {list(update_dict.keys())}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation(hostel_id)
        return cls.get_building_by_id(conn, building_id)

    @classmethod
    def delete_building(
        cls,
        conn: sqlite3.Connection,
        building_id: int,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Check for active allocations
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM room_allocations ra
            JOIN beds bd ON ra.bed_id = bd.id
            JOIN rooms r ON bd.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            WHERE f.building_id = ? AND ra.allocation_status = 'Active';
            """,
            (building_id,),
        )
        active_allocs = cursor.fetchone()[0]
        if active_allocs > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete building. {active_allocs} active student room allocations exist.",
            )

        cursor.execute("DELETE FROM buildings WHERE id = ?;", (building_id,))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "DELETE_BUILDING", "buildings", building_id,
            f"Deleted building ID {building_id}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return {"success": True, "message": f"Building {building_id} deleted successfully"}

    # =============================================================
    # Module E: Block Management
    # =============================================================
    @classmethod
    def list_blocks(
        cls,
        conn: sqlite3.Connection,
        building_id: Optional[int] = None,
        hostel_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        cursor = conn.cursor()
        where_clauses = []
        params = []

        if building_id:
            where_clauses.append("blk.building_id = ?")
            params.append(building_id)
        if hostel_id:
            where_clauses.append("blk.hostel_id = ?")
            params.append(hostel_id)
        if search:
            where_clauses.append("(blk.name LIKE ? OR blk.code LIKE ?)")
            term = f"%{search.strip()}%"
            params.extend([term, term])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            SELECT 
                blk.id, blk.building_id, b.name as building_name,
                blk.hostel_id, h.name as hostel_name,
                blk.name, blk.code, blk.description, blk.is_active,
                blk.created_at, blk.updated_at,
                COUNT(DISTINCT f.id) as floors_count,
                COUNT(DISTINCT r.id) as rooms_count,
                COUNT(DISTINCT bd.id) as physical_capacity,
                COUNT(DISTINCT CASE WHEN bd.is_active = 1 AND bd.maintenance_status != 'Out_Of_Service' THEN bd.id END) as operational_capacity,
                COUNT(DISTINCT CASE WHEN ra.allocation_status = 'Active' THEN ra.id END) as occupied_beds,
                COUNT(DISTINCT CASE WHEN bd.status = 'Available' AND bd.is_active = 1 AND bd.maintenance_status = 'Operational' THEN bd.id END) as available_beds
            FROM blocks blk
            LEFT JOIN buildings b ON blk.building_id = b.id
            LEFT JOIN hostels h ON blk.hostel_id = h.id
            LEFT JOIN floors f ON blk.id = f.block_id
            LEFT JOIN rooms r ON f.id = r.floor_id
            LEFT JOIN beds bd ON r.id = bd.room_id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            {where_sql}
            GROUP BY blk.id
            ORDER BY blk.name ASC;
        """
        cursor.execute(query, tuple(params))
        col_names = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            item = dict(zip(col_names, row))
            op_cap = item.get("operational_capacity") or 0
            occ = item.get("occupied_beds") or 0
            item["occupancy_rate_pct"] = round((occ / op_cap * 100.0), 2) if op_cap > 0 else 0.0
            results.append(item)
        return results

    @classmethod
    def get_block_by_id(cls, conn: sqlite3.Connection, block_id: int) -> Dict[str, Any]:
        blocks = cls.list_blocks(conn)
        for b in blocks:
            if b["id"] == block_id:
                return b
        raise HTTPException(status_code=404, detail=f"Block with ID {block_id} not found")

    @classmethod
    def create_block(
        cls,
        conn: sqlite3.Connection,
        data: BlockCreate,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Resolve hostel_id from building if not supplied
        cursor.execute("SELECT hostel_id FROM buildings WHERE id = ?;", (data.building_id,))
        b_row = cursor.fetchone()
        if not b_row:
            raise HTTPException(status_code=400, detail=f"Building with ID {data.building_id} does not exist")
        hostel_id = data.hostel_id or b_row[0]

        # Check unique code per building
        cursor.execute("SELECT id FROM blocks WHERE building_id = ? AND code = ?;", (data.building_id, data.code))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Block code '{data.code}' already exists in this building")

        cursor.execute(
            """
            INSERT INTO blocks (building_id, hostel_id, name, code, description, is_active)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (data.building_id, hostel_id, data.name, data.code, data.description or "", data.is_active),
        )
        new_id = cursor.lastrowid
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "CREATE_BLOCK", "blocks", new_id,
            f"Created block {data.name} ({data.code})", latency_ms
        )
        return cls.get_block_by_id(conn, new_id)

    @classmethod
    def update_block(
        cls,
        conn: sqlite3.Connection,
        block_id: int,
        data: BlockUpdate,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id, building_id FROM blocks WHERE id = ?;", (block_id,))
        b_row = cursor.fetchone()
        if not b_row:
            raise HTTPException(status_code=404, detail=f"Block with ID {block_id} not found")
        building_id = b_row[1]

        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return cls.get_block_by_id(conn, block_id)

        if "code" in update_dict:
            cursor.execute(
                "SELECT id FROM blocks WHERE building_id = ? AND code = ? AND id != ?;",
                (building_id, update_dict["code"], block_id),
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail=f"Block code '{update_dict['code']}' already exists in this building")

        set_clauses = []
        params = []
        for k, v in update_dict.items():
            set_clauses.append(f"{k} = ?")
            params.append(v)
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(block_id)

        cursor.execute(f"UPDATE blocks SET {', '.join(set_clauses)} WHERE id = ?;", tuple(params))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "UPDATE_BLOCK", "blocks", block_id,
            f"Updated fields: {list(update_dict.keys())}", latency_ms
        )
        return cls.get_block_by_id(conn, block_id)

    @classmethod
    def delete_block(
        cls,
        conn: sqlite3.Connection,
        block_id: int,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Check for active allocations
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM room_allocations ra
            JOIN beds bd ON ra.bed_id = bd.id
            JOIN rooms r ON bd.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            WHERE f.block_id = ? AND ra.allocation_status = 'Active';
            """,
            (block_id,),
        )
        active_allocs = cursor.fetchone()[0]
        if active_allocs > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete block. {active_allocs} active student room allocations exist.",
            )

        cursor.execute("DELETE FROM blocks WHERE id = ?;", (block_id,))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "DELETE_BLOCK", "blocks", block_id,
            f"Deleted block ID {block_id}", latency_ms
        )
        return {"success": True, "message": f"Block {block_id} deleted successfully"}

    # =============================================================
    # Module F: Floor Management
    # =============================================================
    @classmethod
    def list_floors(
        cls,
        conn: sqlite3.Connection,
        building_id: Optional[int] = None,
        block_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        cursor = conn.cursor()
        where_clauses = []
        params = []

        if building_id:
            where_clauses.append("f.building_id = ?")
            params.append(building_id)
        if block_id:
            where_clauses.append("f.block_id = ?")
            params.append(block_id)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            SELECT 
                f.id, f.building_id, b.name as building_name,
                f.block_id, blk.name as block_name,
                f.floor_number, f.floor_name, f.is_active,
                f.created_at, f.updated_at,
                COUNT(DISTINCT r.id) as rooms_count,
                COUNT(DISTINCT bd.id) as physical_capacity,
                COUNT(DISTINCT CASE WHEN bd.is_active = 1 AND bd.maintenance_status != 'Out_Of_Service' THEN bd.id END) as operational_capacity,
                COUNT(DISTINCT CASE WHEN ra.allocation_status = 'Active' THEN ra.id END) as occupied_beds,
                COUNT(DISTINCT CASE WHEN bd.status = 'Available' AND bd.is_active = 1 AND bd.maintenance_status = 'Operational' THEN bd.id END) as available_beds
            FROM floors f
            LEFT JOIN buildings b ON f.building_id = b.id
            LEFT JOIN blocks blk ON f.block_id = blk.id
            LEFT JOIN rooms r ON f.id = r.floor_id
            LEFT JOIN beds bd ON r.id = bd.room_id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            {where_sql}
            GROUP BY f.id
            ORDER BY f.floor_number ASC;
        """
        cursor.execute(query, tuple(params))
        col_names = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            item = dict(zip(col_names, row))
            op_cap = item.get("operational_capacity") or 0
            occ = item.get("occupied_beds") or 0
            item["occupancy_rate_pct"] = round((occ / op_cap * 100.0), 2) if op_cap > 0 else 0.0
            results.append(item)
        return results

    @classmethod
    def get_floor_by_id(cls, conn: sqlite3.Connection, floor_id: int) -> Dict[str, Any]:
        floors = cls.list_floors(conn)
        for f in floors:
            if f["id"] == floor_id:
                return f
        raise HTTPException(status_code=404, detail=f"Floor with ID {floor_id} not found")

    @classmethod
    def create_floor(
        cls,
        conn: sqlite3.Connection,
        data: FloorCreate,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Check unique floor_number in building
        cursor.execute(
            "SELECT id FROM floors WHERE building_id = ? AND floor_number = ?;",
            (data.building_id, data.floor_number),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail=f"Floor number {data.floor_number} already exists in this building",
            )

        # Resolve block if missing
        block_id = data.block_id
        if not block_id:
            cursor.execute("SELECT id FROM blocks WHERE building_id = ? LIMIT 1;", (data.building_id,))
            blk_row = cursor.fetchone()
            if blk_row:
                block_id = blk_row[0]

        cursor.execute(
            """
            INSERT INTO floors (building_id, block_id, floor_number, floor_name, is_active)
            VALUES (?, ?, ?, ?, ?);
            """,
            (data.building_id, block_id, data.floor_number, data.floor_name, data.is_active),
        )
        new_id = cursor.lastrowid
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "CREATE_FLOOR", "floors", new_id,
            f"Created floor {data.floor_name} (Level {data.floor_number})", latency_ms
        )
        return cls.get_floor_by_id(conn, new_id)

    @classmethod
    def update_floor(
        cls,
        conn: sqlite3.Connection,
        floor_id: int,
        data: FloorUpdate,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id, building_id FROM floors WHERE id = ?;", (floor_id,))
        f_row = cursor.fetchone()
        if not f_row:
            raise HTTPException(status_code=404, detail=f"Floor with ID {floor_id} not found")
        building_id = f_row[1]

        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return cls.get_floor_by_id(conn, floor_id)

        if "floor_number" in update_dict:
            cursor.execute(
                "SELECT id FROM floors WHERE building_id = ? AND floor_number = ? AND id != ?;",
                (building_id, update_dict["floor_number"], floor_id),
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=400,
                    detail=f"Floor number {update_dict['floor_number']} already exists in this building",
                )

        set_clauses = []
        params = []
        for k, v in update_dict.items():
            set_clauses.append(f"{k} = ?")
            params.append(v)
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(floor_id)

        cursor.execute(f"UPDATE floors SET {', '.join(set_clauses)} WHERE id = ?;", tuple(params))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "UPDATE_FLOOR", "floors", floor_id,
            f"Updated fields: {list(update_dict.keys())}", latency_ms
        )
        return cls.get_floor_by_id(conn, floor_id)

    @classmethod
    def delete_floor(
        cls,
        conn: sqlite3.Connection,
        floor_id: int,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Check for active allocations
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM room_allocations ra
            JOIN beds bd ON ra.bed_id = bd.id
            JOIN rooms r ON bd.room_id = r.id
            WHERE r.floor_id = ? AND ra.allocation_status = 'Active';
            """,
            (floor_id,),
        )
        active_allocs = cursor.fetchone()[0]
        if active_allocs > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete floor. {active_allocs} active student room allocations exist.",
            )

        cursor.execute("DELETE FROM floors WHERE id = ?;", (floor_id,))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "DELETE_FLOOR", "floors", floor_id,
            f"Deleted floor ID {floor_id}", latency_ms
        )
        return {"success": True, "message": f"Floor {floor_id} deleted successfully"}

    # =============================================================
    # Module G: Room Management & Maintenance Integration
    # =============================================================
    @classmethod
    def list_rooms(
        cls,
        conn: sqlite3.Connection,
        floor_id: Optional[int] = None,
        building_id: Optional[int] = None,
        hostel_id: Optional[int] = None,
        campus_id: Optional[int] = None,
        room_type: Optional[str] = None,
        maintenance_status: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        cursor = conn.cursor()
        where_clauses = []
        params = []

        if floor_id:
            where_clauses.append("r.floor_id = ?")
            params.append(floor_id)
        if building_id:
            where_clauses.append("f.building_id = ?")
            params.append(building_id)
        if hostel_id:
            where_clauses.append("b.hostel_id = ?")
            params.append(hostel_id)
        if campus_id:
            where_clauses.append("b.campus_id = ?")
            params.append(campus_id)
        if room_type:
            where_clauses.append("r.room_type = ?")
            params.append(room_type)
        if maintenance_status:
            where_clauses.append("r.maintenance_status = ?")
            params.append(maintenance_status)
        if status:
            where_clauses.append("r.status = ?")
            params.append(status)
        if search:
            where_clauses.append("(r.room_number LIKE ? OR h.name LIKE ?)")
            term = f"%{search.strip()}%"
            params.extend([term, term])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Total count
        count_query = f"""
            SELECT COUNT(DISTINCT r.id)
            FROM rooms r
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            {where_sql};
        """
        cursor.execute(count_query, tuple(params))
        total = cursor.fetchone()[0]

        offset = max(0, (page - 1) * limit)
        data_query = f"""
            SELECT 
                r.id, r.floor_id, f.floor_name, f.floor_number,
                f.block_id, blk.name as block_name,
                f.building_id, b.name as building_name,
                b.hostel_id, h.name as hostel_name,
                b.campus_id, c.name as campus_name,
                r.room_number, r.room_type, r.capacity, r.base_fee,
                r.status, r.maintenance_status, r.condition_rating,
                r.amenities, r.is_ac, r.attached_washroom, r.is_active,
                r.created_at, r.updated_at,
                COUNT(DISTINCT bd.id) as beds_count,
                COUNT(DISTINCT CASE WHEN ra.allocation_status = 'Active' THEN ra.id END) as occupied_beds,
                COUNT(DISTINCT CASE WHEN bd.status = 'Available' AND bd.is_active = 1 AND bd.maintenance_status = 'Operational' THEN bd.id END) as available_beds
            FROM rooms r
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            LEFT JOIN campuses c ON b.campus_id = c.id
            LEFT JOIN blocks blk ON f.block_id = blk.id
            LEFT JOIN beds bd ON r.id = bd.room_id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            {where_sql}
            GROUP BY r.id
            ORDER BY r.room_number ASC
            LIMIT ? OFFSET ?;
        """
        cursor.execute(data_query, tuple(params + [limit, offset]))
        col_names = [col[0] for col in cursor.description]
        rooms = [dict(zip(col_names, row)) for row in cursor.fetchall()]

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "rooms": rooms,
        }

    @classmethod
    def get_room_by_id(cls, conn: sqlite3.Connection, room_id: int) -> Dict[str, Any]:
        cursor = conn.cursor()
        query = """
            SELECT 
                r.id, r.floor_id, f.floor_name, f.floor_number,
                f.block_id, blk.name as block_name,
                f.building_id, b.name as building_name,
                b.hostel_id, h.name as hostel_name,
                b.campus_id, c.name as campus_name,
                r.room_number, r.room_type, r.capacity, r.base_fee,
                r.status, r.maintenance_status, r.condition_rating,
                r.amenities, r.is_ac, r.attached_washroom, r.is_active,
                r.created_at, r.updated_at,
                COUNT(DISTINCT bd.id) as beds_count,
                COUNT(DISTINCT CASE WHEN ra.allocation_status = 'Active' THEN ra.id END) as occupied_beds,
                COUNT(DISTINCT CASE WHEN bd.status = 'Available' AND bd.is_active = 1 AND bd.maintenance_status = 'Operational' THEN bd.id END) as available_beds
            FROM rooms r
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            LEFT JOIN campuses c ON b.campus_id = c.id
            LEFT JOIN blocks blk ON f.block_id = blk.id
            LEFT JOIN beds bd ON r.id = bd.room_id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            WHERE r.id = ?
            GROUP BY r.id;
        """
        cursor.execute(query, (room_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Room with ID {room_id} not found")

        col_names = [col[0] for col in cursor.description]
        room_data = dict(zip(col_names, row))

        # Fetch occupants
        cursor.execute(
            """
            SELECT 
                ra.id as allocation_id, ra.bed_id, bd.bed_number,
                s.id as student_db_id, s.student_id, s.first_name, s.last_name,
                ra.start_date, ra.allocation_status as allocation_status
            FROM room_allocations ra
            JOIN beds bd ON ra.bed_id = bd.id
            JOIN students s ON ra.student_id = s.id
            WHERE bd.room_id = ? AND ra.allocation_status = 'Active';
            """,
            (room_id,),
        )
        occupants = []
        for o_row in cursor.fetchall():
            occupants.append({
                "allocation_id": o_row[0],
                "bed_id": o_row[1],
                "bed_number": o_row[2],
                "student_db_id": o_row[3],
                "student_id": o_row[4],
                "student_name": f"{o_row[5]} {o_row[6]}".strip(),
                "start_date": o_row[7],
                "status": o_row[8],
            })
        room_data["occupants"] = occupants
        return room_data

    @classmethod
    def create_room(
        cls,
        conn: sqlite3.Connection,
        data: RoomCreate,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        auto_create_beds: bool = True,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Check unique room_number on floor
        cursor.execute(
            "SELECT id FROM rooms WHERE floor_id = ? AND room_number = ?;",
            (data.floor_id, data.room_number),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail=f"Room number '{data.room_number}' already exists on this floor",
            )

        cursor.execute(
            """
            INSERT INTO rooms (
                floor_id, room_number, room_type, capacity, base_fee, status,
                maintenance_status, condition_rating, amenities, is_ac, attached_washroom, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                data.floor_id,
                data.room_number,
                data.room_type,
                data.capacity,
                data.base_fee,
                data.status or "Available",
                data.maintenance_status or "Operational",
                data.condition_rating or "Good",
                data.amenities or "[]",
                data.is_ac,
                data.attached_washroom,
                data.is_active,
            ),
        )
        new_room_id = cursor.lastrowid

        # Auto-create beds matching capacity: Bed A, Bed B, Bed C...
        if auto_create_beds and data.capacity > 0:
            bed_labels = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
            for i in range(data.capacity):
                label = bed_labels[i] if i < len(bed_labels) else str(i + 1)
                bed_num = f"{data.room_number}-{label}"
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO beds (room_id, bed_number, status, maintenance_status, is_active)
                    VALUES (?, ?, 'Available', 'Operational', 1);
                    """,
                    (new_room_id, bed_num),
                )

        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "CREATE_ROOM", "rooms", new_room_id,
            f"Created room {data.room_number} (capacity: {data.capacity})", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return cls.get_room_by_id(conn, new_room_id)

    @classmethod
    def update_room(
        cls,
        conn: sqlite3.Connection,
        room_id: int,
        data: RoomUpdate,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id, floor_id, capacity FROM rooms WHERE id = ?;", (room_id,))
        r_row = cursor.fetchone()
        if not r_row:
            raise HTTPException(status_code=404, detail=f"Room with ID {room_id} not found")
        floor_id, old_capacity = r_row[1], r_row[2]

        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return cls.get_room_by_id(conn, room_id)

        if "room_number" in update_dict:
            cursor.execute(
                "SELECT id FROM rooms WHERE floor_id = ? AND room_number = ? AND id != ?;",
                (floor_id, update_dict["room_number"], room_id),
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=400,
                    detail=f"Room number '{update_dict['room_number']}' already exists on this floor",
                )

        # If capacity changed in update_dict, validate via Poka-Yoke
        if "capacity" in update_dict:
            new_cap = update_dict["capacity"]
            cls.update_room_capacity(conn, room_id, new_cap, user_id, username)
            del update_dict["capacity"]

        if update_dict:
            set_clauses = []
            params = []
            for k, v in update_dict.items():
                set_clauses.append(f"{k} = ?")
                params.append(v)
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            params.append(room_id)

            cursor.execute(f"UPDATE rooms SET {', '.join(set_clauses)} WHERE id = ?;", tuple(params))
            conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "UPDATE_ROOM", "rooms", room_id,
            f"Updated room fields: {list(update_dict.keys())}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return cls.get_room_by_id(conn, room_id)

    @classmethod
    def update_room_capacity(
        cls,
        conn: sqlite3.Connection,
        room_id: int,
        new_capacity: int,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Poka-Yoke error proofing: Prevent capacity reduction below active occupancy."""
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id, room_number, capacity FROM rooms WHERE id = ?;", (room_id,))
        r_row = cursor.fetchone()
        if not r_row:
            raise HTTPException(status_code=404, detail=f"Room with ID {room_id} not found")
        room_number, old_cap = r_row[1], r_row[2]

        # Check active occupants
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM room_allocations ra
            JOIN beds bd ON ra.bed_id = bd.id
            WHERE bd.room_id = ? AND ra.allocation_status = 'Active';
            """,
            (room_id,),
        )
        active_occupants = cursor.fetchone()[0]

        if new_capacity < active_occupants:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reduce room capacity to {new_capacity}. Currently {active_occupants} active students are allocated to room {room_number}.",
            )

        # Update room capacity
        cursor.execute(
            "UPDATE rooms SET capacity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
            (new_capacity, room_id),
        )

        # Adjust beds count in room
        cursor.execute("SELECT id, bed_number, status FROM beds WHERE room_id = ? ORDER BY id ASC;", (room_id,))
        existing_beds = cursor.fetchall()
        current_bed_count = len(existing_beds)

        if new_capacity > current_bed_count:
            # Need to add beds
            bed_labels = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
            for i in range(current_bed_count, new_capacity):
                label = bed_labels[i] if i < len(bed_labels) else str(i + 1)
                bed_num = f"{room_number}-{label}"
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO beds (room_id, bed_number, status, maintenance_status, is_active)
                    VALUES (?, ?, 'Available', 'Operational', 1);
                    """,
                    (room_id, bed_num),
                )
        elif new_capacity < current_bed_count:
            # Need to remove unallocated beds from the end
            removable_count = current_bed_count - new_capacity
            cursor.execute(
                """
                SELECT id FROM beds 
                WHERE room_id = ? AND id NOT IN (SELECT bed_id FROM room_allocations WHERE allocation_status = 'Active')
                ORDER BY id DESC LIMIT ?;
                """,
                (room_id, removable_count),
            )
            beds_to_delete = [b[0] for b in cursor.fetchall()]
            if beds_to_delete:
                cursor.execute(
                    f"DELETE FROM beds WHERE id IN ({','.join(['?']*len(beds_to_delete))});",
                    tuple(beds_to_delete),
                )

        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "UPDATE_ROOM_CAPACITY", "rooms", room_id,
            f"Changed capacity from {old_cap} to {new_capacity} for room {room_number}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return cls.get_room_by_id(conn, room_id)

    @classmethod
    def update_room_maintenance(
        cls,
        conn: sqlite3.Connection,
        room_id: int,
        maintenance_status: str,
        room_status: Optional[str] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id, room_number, status FROM rooms WHERE id = ?;", (room_id,))
        r_row = cursor.fetchone()
        if not r_row:
            raise HTTPException(status_code=404, detail=f"Room with ID {room_id} not found")

        # Determine target status
        if not room_status:
            if maintenance_status in ("Under_Repair", "Decommissioned"):
                room_status = "Under Maintenance"
            elif maintenance_status == "Operational":
                room_status = "Available"
            else:
                room_status = r_row[2]

        cursor.execute(
            """
            UPDATE rooms 
            SET maintenance_status = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (maintenance_status, room_status, room_id),
        )

        # Propagate maintenance status to beds if room is under repair
        if maintenance_status in ("Under_Repair", "Decommissioned"):
            cursor.execute(
                """
                UPDATE beds 
                SET maintenance_status = 'Under_Repair', status = 'Maintenance', updated_at = CURRENT_TIMESTAMP
                WHERE room_id = ? AND status != 'Occupied';
                """,
                (room_id,),
            )
        elif maintenance_status == "Operational":
            cursor.execute(
                """
                UPDATE beds 
                SET maintenance_status = 'Operational', status = 'Available', updated_at = CURRENT_TIMESTAMP
                WHERE room_id = ? AND status = 'Maintenance';
                """,
                (room_id,),
            )

        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "UPDATE_ROOM_MAINTENANCE", "rooms", room_id,
            f"Maintenance status set to {maintenance_status}, room status to {room_status}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return cls.get_room_by_id(conn, room_id)

    @classmethod
    def delete_room(
        cls,
        conn: sqlite3.Connection,
        room_id: int,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Check for active allocations
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM room_allocations ra
            JOIN beds bd ON ra.bed_id = bd.id
            WHERE bd.room_id = ? AND ra.allocation_status = 'Active';
            """,
            (room_id,),
        )
        active_allocs = cursor.fetchone()[0]
        if active_allocs > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete room. {active_allocs} active student room allocations exist.",
            )

        cursor.execute("DELETE FROM rooms WHERE id = ?;", (room_id,))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "DELETE_ROOM", "rooms", room_id,
            f"Deleted room ID {room_id}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return {"success": True, "message": f"Room {room_id} deleted successfully"}

    # =============================================================
    # Module H: Bed Management & Allocation Locks
    # =============================================================
    @classmethod
    def list_beds(
        cls,
        conn: sqlite3.Connection,
        room_id: Optional[int] = None,
        hostel_id: Optional[int] = None,
        status: Optional[str] = None,
        maintenance_status: Optional[str] = None,
        is_active: Optional[int] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        cursor = conn.cursor()
        where_clauses = []
        params = []

        if room_id:
            where_clauses.append("bd.room_id = ?")
            params.append(room_id)
        if hostel_id:
            where_clauses.append("b.hostel_id = ?")
            params.append(hostel_id)
        if status:
            where_clauses.append("bd.status = ?")
            params.append(status)
        if maintenance_status:
            where_clauses.append("bd.maintenance_status = ?")
            params.append(maintenance_status)
        if is_active is not None:
            where_clauses.append("bd.is_active = ?")
            params.append(is_active)
        if search:
            where_clauses.append("(bd.bed_number LIKE ? OR r.room_number LIKE ?)")
            term = f"%{search.strip()}%"
            params.extend([term, term])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Count total
        count_query = f"""
            SELECT COUNT(DISTINCT bd.id)
            FROM beds bd
            JOIN rooms r ON bd.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            {where_sql};
        """
        cursor.execute(count_query, tuple(params))
        total = cursor.fetchone()[0]

        offset = max(0, (page - 1) * limit)
        data_query = f"""
            SELECT 
                bd.id, bd.room_id, r.room_number, f.id as floor_id,
                b.id as building_id, b.hostel_id,
                bd.bed_number, bd.status, bd.maintenance_status,
                bd.monthly_rate, bd.is_active,
                bd.created_at, bd.updated_at,
                s.student_id as occupant_student_id,
                (s.first_name || ' ' || s.last_name) as occupant_student_name,
                CASE 
                    WHEN bd.is_active = 1 AND bd.maintenance_status = 'Operational' AND bd.status = 'Available' THEN 1 
                    ELSE 0 
                END as is_allocatable
            FROM beds bd
            JOIN rooms r ON bd.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            LEFT JOIN students s ON ra.student_id = s.id
            {where_sql}
            ORDER BY bd.bed_number ASC
            LIMIT ? OFFSET ?;
        """
        cursor.execute(data_query, tuple(params + [limit, offset]))
        col_names = [col[0] for col in cursor.description]
        beds = []
        for row in cursor.fetchall():
            item = dict(zip(col_names, row))
            item["is_allocatable"] = bool(item["is_allocatable"])
            beds.append(item)

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "beds": beds,
        }

    @classmethod
    def get_bed_by_id(cls, conn: sqlite3.Connection, bed_id: int) -> Dict[str, Any]:
        cursor = conn.cursor()
        query = """
            SELECT 
                bd.id, bd.room_id, r.room_number, f.id as floor_id,
                b.id as building_id, b.hostel_id,
                bd.bed_number, bd.status, bd.maintenance_status,
                bd.monthly_rate, bd.is_active,
                bd.created_at, bd.updated_at,
                s.student_id as occupant_student_id,
                (s.first_name || ' ' || s.last_name) as occupant_student_name,
                CASE 
                    WHEN bd.is_active = 1 AND bd.maintenance_status = 'Operational' AND bd.status = 'Available' THEN 1 
                    ELSE 0 
                END as is_allocatable
            FROM beds bd
            JOIN rooms r ON bd.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            LEFT JOIN students s ON ra.student_id = s.id
            WHERE bd.id = ?;
        """
        cursor.execute(query, (bed_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Bed with ID {bed_id} not found")

        col_names = [col[0] for col in cursor.description]
        item = dict(zip(col_names, row))
        item["is_allocatable"] = bool(item["is_allocatable"])
        return item

    @classmethod
    def create_bed(
        cls,
        conn: sqlite3.Connection,
        data: BedCreate,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Verify room exists
        cursor.execute("SELECT id FROM rooms WHERE id = ?;", (data.room_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Room with ID {data.room_id} does not exist")

        # Check unique bed_number in room
        cursor.execute(
            "SELECT id FROM beds WHERE room_id = ? AND bed_number = ?;",
            (data.room_id, data.bed_number),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail=f"Bed number '{data.bed_number}' already exists in this room",
            )

        cursor.execute(
            """
            INSERT INTO beds (room_id, bed_number, status, maintenance_status, monthly_rate, is_active)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                data.room_id,
                data.bed_number,
                data.status or "Available",
                data.maintenance_status or "Operational",
                data.monthly_rate or 0.0,
                data.is_active,
            ),
        )
        new_id = cursor.lastrowid
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "CREATE_BED", "beds", new_id,
            f"Created bed {data.bed_number}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return cls.get_bed_by_id(conn, new_id)

    @classmethod
    def update_bed(
        cls,
        conn: sqlite3.Connection,
        bed_id: int,
        data: BedUpdate,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id, room_id FROM beds WHERE id = ?;", (bed_id,))
        b_row = cursor.fetchone()
        if not b_row:
            raise HTTPException(status_code=404, detail=f"Bed with ID {bed_id} not found")
        room_id = b_row[1]

        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return cls.get_bed_by_id(conn, bed_id)

        if "bed_number" in update_dict:
            cursor.execute(
                "SELECT id FROM beds WHERE room_id = ? AND bed_number = ? AND id != ?;",
                (room_id, update_dict["bed_number"], bed_id),
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=400,
                    detail=f"Bed number '{update_dict['bed_number']}' already exists in this room",
                )

        set_clauses = []
        params = []
        for k, v in update_dict.items():
            set_clauses.append(f"{k} = ?")
            params.append(v)
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(bed_id)

        cursor.execute(f"UPDATE beds SET {', '.join(set_clauses)} WHERE id = ?;", tuple(params))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "UPDATE_BED", "beds", bed_id,
            f"Updated fields: {list(update_dict.keys())}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return cls.get_bed_by_id(conn, bed_id)

    @classmethod
    def update_bed_maintenance(
        cls,
        conn: sqlite3.Connection,
        bed_id: int,
        maintenance_status: str,
        bed_status: Optional[str] = None,
        notes: Optional[str] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Poka-Yoke: Locks bed from allocation when marked Under_Repair or Out_Of_Service."""
        t0 = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute("SELECT id, bed_number, status FROM beds WHERE id = ?;", (bed_id,))
        b_row = cursor.fetchone()
        if not b_row:
            raise HTTPException(status_code=404, detail=f"Bed with ID {bed_id} not found")

        # If bed is being set to Under_Repair or Out_Of_Service, verify active occupancy
        if maintenance_status in ("Under_Repair", "Out_Of_Service"):
            cursor.execute(
                "SELECT COUNT(*) FROM room_allocations WHERE bed_id = ? AND allocation_status = 'Active';",
                (bed_id,),
            )
            active_allocs = cursor.fetchone()[0]
            if active_allocs > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot place bed {b_row[1]} under maintenance. A student is currently actively allocated to this bed. Please reallocate the student first.",
                )
            if not bed_status:
                bed_status = "Maintenance"
        elif maintenance_status == "Operational":
            if not bed_status:
                bed_status = "Available"

        cursor.execute(
            """
            UPDATE beds 
            SET maintenance_status = ?, status = COALESCE(?, status), updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (maintenance_status, bed_status, bed_id),
        )
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "UPDATE_BED_MAINTENANCE", "beds", bed_id,
            f"Maintenance set to {maintenance_status}, status={bed_status}. Notes: {notes or ''}",
            latency_ms,
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return cls.get_bed_by_id(conn, bed_id)

    @classmethod
    def delete_bed(
        cls,
        conn: sqlite3.Connection,
        bed_id: int,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # Check for active allocations
        cursor.execute(
            "SELECT COUNT(*) FROM room_allocations WHERE bed_id = ? AND allocation_status = 'Active';",
            (bed_id,),
        )
        active_allocs = cursor.fetchone()[0]
        if active_allocs > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete bed. An active student room allocation exists on this bed.",
            )

        cursor.execute("DELETE FROM beds WHERE id = ?;", (bed_id,))
        conn.commit()

        latency_ms = (time.perf_counter() - t0) * 1000.0
        cls._log_audit(
            conn, user_id, username, "DELETE_BED", "beds", bed_id,
            f"Deleted bed ID {bed_id}", latency_ms
        )
        CacheInvalidator.on_hostel_infrastructure_mutation()
        return {"success": True, "message": f"Bed {bed_id} deleted successfully"}

    # =============================================================
    # Module I: Hierarchy Tree Visualization
    # =============================================================
    @classmethod
    def get_hierarchy(
        cls,
        conn: sqlite3.Connection,
        campus_id: Optional[int] = None,
        hostel_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Builds high-performance 8-level tree: Institution -> Campus -> Hostel -> Building -> Block -> Floor -> Room -> Bed.
        
        Optimized single-pass multi-tier construction for sub-millisecond query execution.
        """
        t0 = time.perf_counter()
        cursor = conn.cursor()

        # 1. Fetch institution
        cursor.execute("SELECT id, name, code FROM institutions LIMIT 1;")
        inst_row = cursor.fetchone()
        if not inst_row:
            raise HTTPException(status_code=404, detail="Institution profile missing")

        inst_node = {
            "id": inst_row[0],
            "name": inst_row[1],
            "code": inst_row[2],
            "node_type": "institution",
            "status": "Active",
            "capacity": 0,
            "operational_capacity": 0,
            "occupancy": 0,
            "children": [],
        }

        # 2. Fetch campuses
        c_query = "SELECT id, name, code, operating_status FROM campuses WHERE is_active = 1"
        c_params = []
        if campus_id:
            c_query += " AND id = ?"
            c_params.append(campus_id)
        c_query += " ORDER BY name ASC;"
        cursor.execute(c_query, tuple(c_params))
        campus_rows = cursor.fetchall()
        campus_map = {}
        for c in campus_rows:
            node = {
                "id": c[0],
                "name": c[1],
                "code": c[2],
                "node_type": "campus",
                "status": c[3],
                "capacity": 0,
                "operational_capacity": 0,
                "occupancy": 0,
                "children": [],
            }
            campus_map[c[0]] = node
            inst_node["children"].append(node)

        # 3. Fetch hostels
        h_query = "SELECT id, campus_id, name, code, hostel_type, is_active FROM hostels WHERE is_active = 1"
        h_params = []
        if hostel_id:
            h_query += " AND id = ?"
            h_params.append(hostel_id)
        elif campus_id:
            h_query += " AND campus_id = ?"
            h_params.append(campus_id)
        h_query += " ORDER BY name ASC;"
        cursor.execute(h_query, tuple(h_params))
        hostel_rows = cursor.fetchall()
        hostel_map = {}
        for h in hostel_rows:
            h_id, c_id, h_name, h_code, h_type, is_act = h
            node = {
                "id": h_id,
                "campus_id": c_id,
                "name": h_name,
                "code": h_code,
                "node_type": "hostel",
                "status": "Active" if is_act == 1 else "Inactive",
                "hostel_type": h_type,
                "capacity": 0,
                "operational_capacity": 0,
                "occupancy": 0,
                "children": [],
            }
            hostel_map[h_id] = node
            if c_id in campus_map:
                campus_map[c_id]["children"].append(node)
            else:
                inst_node["children"].append(node)

        # 4. Fetch buildings
        b_query = """
            SELECT id, hostel_id, name, code, condition_rating, is_active 
            FROM buildings 
            WHERE is_active = 1
        """
        b_params = []
        if hostel_id:
            b_query += " AND hostel_id = ?"
            b_params.append(hostel_id)
        b_query += " ORDER BY name ASC;"
        cursor.execute(b_query, tuple(b_params))
        bld_rows = cursor.fetchall()
        bld_map = {}
        for b in bld_rows:
            b_id, h_id, b_name, b_code, b_cond, is_act = b
            node = {
                "id": b_id,
                "hostel_id": h_id,
                "name": b_name,
                "code": b_code,
                "node_type": "building",
                "status": b_cond or "Good",
                "capacity": 0,
                "operational_capacity": 0,
                "occupancy": 0,
                "children": [],
            }
            bld_map[b_id] = node
            if h_id in hostel_map:
                hostel_map[h_id]["children"].append(node)

        # 5. Fetch blocks
        cursor.execute("SELECT id, building_id, hostel_id, name, code FROM blocks WHERE is_active = 1 ORDER BY name ASC;")
        block_rows = cursor.fetchall()
        block_map = {}
        for blk in block_rows:
            blk_id, b_id, h_id, blk_name, blk_code = blk
            node = {
                "id": blk_id,
                "building_id": b_id,
                "name": blk_name,
                "code": blk_code,
                "node_type": "block",
                "status": "Active",
                "capacity": 0,
                "operational_capacity": 0,
                "occupancy": 0,
                "children": [],
            }
            block_map[blk_id] = node
            if b_id in bld_map:
                bld_map[b_id]["children"].append(node)

        # 6. Fetch floors
        cursor.execute("SELECT id, building_id, block_id, floor_number, floor_name FROM floors WHERE is_active = 1 ORDER BY floor_number ASC;")
        floor_rows = cursor.fetchall()
        floor_map = {}
        for f in floor_rows:
            f_id, b_id, blk_id, f_num, f_name = f
            node = {
                "id": f_id,
                "building_id": b_id,
                "block_id": blk_id,
                "name": f_name,
                "code": f"FL-{f_num}",
                "node_type": "floor",
                "status": "Active",
                "capacity": 0,
                "operational_capacity": 0,
                "occupancy": 0,
                "children": [],
            }
            floor_map[f_id] = node
            if blk_id and blk_id in block_map:
                block_map[blk_id]["children"].append(node)
            elif b_id in bld_map:
                bld_map[b_id]["children"].append(node)

        # 7. Fetch rooms with capacity and occupancy
        cursor.execute(
            """
            SELECT 
                r.id, r.floor_id, r.room_number, r.room_type, r.capacity,
                r.status, r.maintenance_status,
                COUNT(DISTINCT bd.id) as physical_beds,
                COUNT(DISTINCT CASE WHEN bd.is_active = 1 AND bd.maintenance_status != 'Out_Of_Service' THEN bd.id END) as operational_beds,
                COUNT(DISTINCT CASE WHEN ra.allocation_status = 'Active' THEN ra.id END) as occupants
            FROM rooms r
            LEFT JOIN beds bd ON r.id = bd.room_id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            WHERE r.is_active = 1
            GROUP BY r.id
            ORDER BY r.room_number ASC;
            """
        )
        for r in cursor.fetchall():
            r_id, f_id, r_num, r_type, r_cap, r_stat, r_maint, p_beds, op_beds, occ = r
            node = {
                "id": r_id,
                "floor_id": f_id,
                "name": f"Room {r_num}",
                "code": r_num,
                "node_type": "room",
                "room_type": r_type,
                "status": r_stat,
                "maintenance_status": r_maint,
                "capacity": p_beds or r_cap,
                "operational_capacity": op_beds or r_cap,
                "occupancy": occ,
                "children": [],
            }
            if f_id in floor_map:
                floor_map[f_id]["children"].append(node)

        # Roll up metrics bottom-up
        def rollup(node: Dict[str, Any]) -> Tuple[int, int, int]:
            if not node["children"]:
                return node["capacity"], node["operational_capacity"], node["occupancy"]
            tot_cap, tot_op, tot_occ = 0, 0, 0
            for child in node["children"]:
                c_cap, c_op, c_occ = rollup(child)
                tot_cap += c_cap
                tot_op += c_op
                tot_occ += c_occ
            node["capacity"] = tot_cap
            node["operational_capacity"] = tot_op
            node["occupancy"] = tot_occ
            node["occupancy_rate_pct"] = round((tot_occ / tot_op * 100.0), 2) if tot_op > 0 else 0.0
            return tot_cap, tot_op, tot_occ

        rollup(inst_node)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "hierarchy": inst_node,
            "latency_ms": round(latency_ms, 2),
        }

    # =============================================================
    # Module J: Capacity & Occupancy Calculation Engine
    # =============================================================
    @classmethod
    def get_capacity_metrics(
        cls,
        conn: sqlite3.Connection,
        campus_id: Optional[int] = None,
        hostel_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Provides completely reconciled institutional capacity analytics."""
        t0 = time.perf_counter()
        cursor = conn.cursor()

        where_clauses = []
        params = []
        if campus_id:
            where_clauses.append("b.campus_id = ?")
            params.append(campus_id)
        if hostel_id:
            where_clauses.append("b.hostel_id = ?")
            params.append(hostel_id)
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Global Bed counts
        cursor.execute(
            f"""
            SELECT 
                COUNT(*) as physical_capacity,
                COUNT(CASE WHEN bd.is_active = 1 AND bd.maintenance_status != 'Out_Of_Service' THEN 1 END) as operational_capacity,
                COUNT(CASE WHEN ra.allocation_status = 'Active' THEN 1 END) as occupied_beds,
                COUNT(CASE WHEN bd.status = 'Available' AND bd.is_active = 1 AND bd.maintenance_status = 'Operational' THEN 1 END) as available_beds,
                COUNT(CASE WHEN bd.maintenance_status IN ('Under_Repair', 'Out_Of_Service') OR bd.status = 'Maintenance' THEN 1 END) as maintenance_beds
            FROM beds bd
            JOIN rooms r ON bd.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            {where_sql};
            """,
            tuple(params),
        )
        totals = cursor.fetchone()
        phys_cap, op_cap, occ, avail, maint = totals

        overall_occ_pct = round((occ / op_cap * 100.0), 2) if op_cap > 0 else 0.0

        # Breakdown by Campus
        cursor.execute(
            """
            SELECT 
                c.id, c.name, c.code,
                COUNT(DISTINCT bd.id) as physical_capacity,
                COUNT(DISTINCT CASE WHEN bd.is_active = 1 AND bd.maintenance_status != 'Out_Of_Service' THEN bd.id END) as operational_capacity,
                COUNT(DISTINCT CASE WHEN ra.allocation_status = 'Active' THEN ra.id END) as occupied_beds,
                COUNT(DISTINCT CASE WHEN bd.status = 'Available' AND bd.is_active = 1 AND bd.maintenance_status = 'Operational' THEN bd.id END) as available_beds,
                COUNT(DISTINCT CASE WHEN bd.maintenance_status IN ('Under_Repair', 'Out_Of_Service') OR bd.status = 'Maintenance' THEN bd.id END) as maintenance_beds
            FROM campuses c
            LEFT JOIN hostels h ON c.id = h.campus_id
            LEFT JOIN buildings b ON h.id = b.hostel_id
            LEFT JOIN floors f ON b.id = f.building_id
            LEFT JOIN rooms r ON f.id = r.floor_id
            LEFT JOIN beds bd ON r.id = bd.room_id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            WHERE c.is_active = 1
            GROUP BY c.id
            ORDER BY c.name ASC;
            """
        )
        campus_items = []
        for row in cursor.fetchall():
            c_op = row[4] or 0
            c_occ = row[5] or 0
            c_pct = round((c_occ / c_op * 100.0), 2) if c_op > 0 else 0.0
            campus_items.append({
                "id": row[0],
                "name": row[1],
                "code": row[2],
                "physical_capacity": row[3],
                "operational_capacity": row[4],
                "occupied_beds": row[5],
                "available_beds": row[6],
                "maintenance_beds": row[7],
                "occupancy_rate_pct": c_pct,
            })

        # Breakdown by Hostel
        cursor.execute(
            """
            SELECT 
                h.id, h.name, h.code,
                COUNT(DISTINCT bd.id) as physical_capacity,
                COUNT(DISTINCT CASE WHEN bd.is_active = 1 AND bd.maintenance_status != 'Out_Of_Service' THEN bd.id END) as operational_capacity,
                COUNT(DISTINCT CASE WHEN ra.allocation_status = 'Active' THEN ra.id END) as occupied_beds,
                COUNT(DISTINCT CASE WHEN bd.status = 'Available' AND bd.is_active = 1 AND bd.maintenance_status = 'Operational' THEN bd.id END) as available_beds,
                COUNT(DISTINCT CASE WHEN bd.maintenance_status IN ('Under_Repair', 'Out_Of_Service') OR bd.status = 'Maintenance' THEN bd.id END) as maintenance_beds
            FROM hostels h
            LEFT JOIN buildings b ON h.id = b.hostel_id
            LEFT JOIN floors f ON b.id = f.building_id
            LEFT JOIN rooms r ON f.id = r.floor_id
            LEFT JOIN beds bd ON r.id = bd.room_id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            WHERE h.is_active = 1
            GROUP BY h.id
            ORDER BY h.name ASC;
            """
        )
        hostel_items = []
        for row in cursor.fetchall():
            h_op = row[4] or 0
            h_occ = row[5] or 0
            h_pct = round((h_occ / h_op * 100.0), 2) if h_op > 0 else 0.0
            hostel_items.append({
                "id": row[0],
                "name": row[1],
                "code": row[2],
                "physical_capacity": row[3],
                "operational_capacity": row[4],
                "occupied_beds": row[5],
                "available_beds": row[6],
                "maintenance_beds": row[7],
                "occupancy_rate_pct": h_pct,
            })

        # Breakdown by Room Type
        cursor.execute(
            """
            SELECT 
                r.room_type,
                COUNT(DISTINCT r.id) as rooms_count,
                COUNT(DISTINCT bd.id) as total_beds,
                COUNT(DISTINCT CASE WHEN ra.allocation_status = 'Active' THEN ra.id END) as occupied_beds,
                COUNT(DISTINCT CASE WHEN bd.status = 'Available' AND bd.is_active = 1 AND bd.maintenance_status = 'Operational' THEN bd.id END) as available_beds
            FROM rooms r
            LEFT JOIN beds bd ON r.id = bd.room_id
            LEFT JOIN room_allocations ra ON bd.id = ra.bed_id AND ra.allocation_status = 'Active'
            WHERE r.is_active = 1
            GROUP BY r.room_type
            ORDER BY r.room_type ASC;
            """
        )
        room_type_items = {}
        for row in cursor.fetchall():
            rtype, r_count, t_beds, o_beds, a_beds = row
            room_type_items[rtype] = {
                "rooms_count": r_count,
                "total_beds": t_beds,
                "occupied_beds": o_beds,
                "available_beds": a_beds,
                "occupancy_rate_pct": round((o_beds / t_beds * 100.0), 2) if t_beds > 0 else 0.0,
            }

        latency_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "total_physical_capacity": phys_cap,
            "total_operational_capacity": op_cap,
            "total_occupied_beds": occ,
            "total_available_beds": avail,
            "total_maintenance_beds": maint,
            "overall_occupancy_rate_pct": overall_occ_pct,
            "by_campus": campus_items,
            "by_hostel": hostel_items,
            "by_room_type": room_type_items,
            "latency_ms": round(latency_ms, 2),
        }

    # =============================================================
    # Module L: Bulk Import & Export with Rollback
    # =============================================================
    @classmethod
    def bulk_import(
        cls,
        conn: sqlite3.Connection,
        entity_type: str,
        records: List[Dict[str, Any]],
        dry_run: bool = True,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Performs bulk import with dry-run pre-flight validation and atomic transaction rollback."""
        t0 = time.perf_counter()
        cursor = conn.cursor()

        errors = []
        valid_rows = 0
        created_count = 0
        updated_count = 0

        # Validate entity type
        allowed_entities = ("campuses", "hostels", "buildings", "blocks", "floors", "rooms", "beds")
        if entity_type not in allowed_entities:
            raise HTTPException(status_code=400, detail=f"Unsupported entity type '{entity_type}'. Allowed: {allowed_entities}")

        # Pre-flight validation on each record
        for idx, rec in enumerate(records):
            row_num = idx + 1
            if entity_type == "campuses":
                if not rec.get("name") or not rec.get("code") or not rec.get("address"):
                    errors.append(f"Row {row_num}: name, code, and address are mandatory")
                else:
                    valid_rows += 1
            elif entity_type == "hostels":
                if not rec.get("name") or not rec.get("code") or not rec.get("campus_id"):
                    errors.append(f"Row {row_num}: name, code, and campus_id are mandatory")
                else:
                    cursor.execute("SELECT id FROM campuses WHERE id = ?;", (rec["campus_id"],))
                    if not cursor.fetchone():
                        errors.append(f"Row {row_num}: campus_id {rec['campus_id']} does not exist")
                    else:
                        valid_rows += 1
            elif entity_type == "buildings":
                if not rec.get("name") or not rec.get("code") or not rec.get("hostel_id") or not rec.get("total_floors"):
                    errors.append(f"Row {row_num}: name, code, hostel_id, and total_floors are mandatory")
                else:
                    cursor.execute("SELECT id FROM hostels WHERE id = ?;", (rec["hostel_id"],))
                    if not cursor.fetchone():
                        errors.append(f"Row {row_num}: hostel_id {rec['hostel_id']} does not exist")
                    else:
                        valid_rows += 1
            elif entity_type == "blocks":
                if not rec.get("name") or not rec.get("code") or not rec.get("building_id"):
                    errors.append(f"Row {row_num}: name, code, and building_id are mandatory")
                else:
                    cursor.execute("SELECT id FROM buildings WHERE id = ?;", (rec["building_id"],))
                    if not cursor.fetchone():
                        errors.append(f"Row {row_num}: building_id {rec['building_id']} does not exist")
                    else:
                        valid_rows += 1
            elif entity_type == "floors":
                if not rec.get("floor_name") or rec.get("floor_number") is None or not rec.get("building_id"):
                    errors.append(f"Row {row_num}: floor_name, floor_number, and building_id are mandatory")
                else:
                    cursor.execute("SELECT id FROM buildings WHERE id = ?;", (rec["building_id"],))
                    if not cursor.fetchone():
                        errors.append(f"Row {row_num}: building_id {rec['building_id']} does not exist")
                    else:
                        valid_rows += 1
            elif entity_type == "rooms":
                if not rec.get("room_number") or not rec.get("floor_id") or not rec.get("capacity"):
                    errors.append(f"Row {row_num}: room_number, floor_id, and capacity are mandatory")
                else:
                    cursor.execute("SELECT id FROM floors WHERE id = ?;", (rec["floor_id"],))
                    if not cursor.fetchone():
                        errors.append(f"Row {row_num}: floor_id {rec['floor_id']} does not exist")
                    else:
                        valid_rows += 1
            elif entity_type == "beds":
                if not rec.get("bed_number") or not rec.get("room_id"):
                    errors.append(f"Row {row_num}: bed_number and room_id are mandatory")
                else:
                    cursor.execute("SELECT id FROM rooms WHERE id = ?;", (rec["room_id"],))
                    if not cursor.fetchone():
                        errors.append(f"Row {row_num}: room_id {rec['room_id']} does not exist")
                    else:
                        valid_rows += 1

        if errors or dry_run:
            return {
                "success": len(errors) == 0,
                "dry_run": dry_run,
                "total_rows": len(records),
                "valid_rows": valid_rows,
                "invalid_rows": len(errors),
                "errors": errors,
                "created_count": 0,
                "updated_count": 0,
            }

        # Dry run passed and not requested: Execute atomic commit
        try:
            cursor.execute("SAVEPOINT bulk_import_savepoint;")
            for rec in records:
                if entity_type == "campuses":
                    cursor.execute(
                        """
                        INSERT INTO campuses (institution_id, name, code, address, city, state, country, postal_code, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(code) DO UPDATE SET
                            name = excluded.name,
                            address = excluded.address;
                        """,
                        (
                            rec.get("institution_id", 1), rec["name"], rec["code"], rec["address"],
                            rec.get("city", ""), rec.get("state", ""),
                            rec.get("country", "India"), rec.get("postal_code", ""),
                            rec.get("is_active", 1),
                        ),
                    )
                    created_count += 1
                elif entity_type == "hostels":
                    cursor.execute(
                        """
                        INSERT INTO hostels (institution_id, campus_id, name, code, hostel_type, category, address, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(code) DO UPDATE SET
                            name = excluded.name,
                            campus_id = excluded.campus_id,
                            category = excluded.category;
                        """,
                        (
                            rec.get("institution_id", 1), rec["campus_id"], rec["name"],
                            rec["code"], rec.get("hostel_type", "Co-Ed"),
                            rec.get("category", "General"), rec.get("address", ""),
                            rec.get("is_active", 1),
                        ),
                    )
                    created_count += 1
                elif entity_type == "buildings":
                    cursor.execute(
                        """
                        INSERT INTO buildings (hostel_id, campus_id, name, code, total_floors, is_active)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(code) DO UPDATE SET
                            name = excluded.name,
                            total_floors = excluded.total_floors;
                        """,
                        (
                            rec["hostel_id"], rec.get("campus_id", 1), rec["name"],
                            rec["code"], rec["total_floors"], rec.get("is_active", 1),
                        ),
                    )
                    created_count += 1
                elif entity_type == "blocks":
                    cursor.execute(
                        """
                        INSERT INTO blocks (building_id, hostel_id, name, code, description, is_active)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(building_id, code) DO UPDATE SET
                            name = excluded.name,
                            description = excluded.description;
                        """,
                        (
                            rec["building_id"], rec.get("hostel_id", 1), rec["name"],
                            rec["code"], rec.get("description", ""), rec.get("is_active", 1),
                        ),
                    )
                    created_count += 1
                elif entity_type == "floors":
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO floors (building_id, block_id, floor_number, floor_name, is_active)
                        VALUES (?, ?, ?, ?, ?);
                        """,
                        (
                            rec["building_id"], rec.get("block_id"), rec["floor_number"],
                            rec["floor_name"], rec.get("is_active", 1),
                        ),
                    )
                    created_count += 1
                elif entity_type == "rooms":
                    cursor.execute(
                        """
                        INSERT INTO rooms (floor_id, room_number, room_type, capacity, base_fee, status, maintenance_status, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            rec["floor_id"], rec["room_number"], rec.get("room_type", "Double"),
                            rec["capacity"], rec.get("base_fee", 0.0), rec.get("status", "Available"),
                            rec.get("maintenance_status", "Operational"), rec.get("is_active", 1),
                        ),
                    )
                    r_id = cursor.lastrowid
                    # Create beds
                    for b_idx in range(rec["capacity"]):
                        b_num = f"{rec['room_number']}-{chr(65 + b_idx)}"
                        cursor.execute(
                            "INSERT OR IGNORE INTO beds (room_id, bed_number, status, maintenance_status, is_active) VALUES (?, ?, 'Available', 'Operational', 1);",
                            (r_id, b_num),
                        )
                    created_count += 1
                elif entity_type == "beds":
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO beds (room_id, bed_number, status, maintenance_status, monthly_rate, is_active)
                        VALUES (?, ?, ?, ?, ?, ?);
                        """,
                        (
                            rec["room_id"], rec["bed_number"], rec.get("status", "Available"),
                            rec.get("maintenance_status", "Operational"), rec.get("monthly_rate", 0.0),
                            rec.get("is_active", 1),
                        ),
                    )
                    created_count += 1

            cursor.execute("RELEASE SAVEPOINT bulk_import_savepoint;")
            conn.commit()

            latency_ms = (time.perf_counter() - t0) * 1000.0
            cls._log_audit(
                conn, user_id, username, "BULK_IMPORT", entity_type, "bulk",
                f"Imported {created_count} {entity_type} records", latency_ms
            )
            CacheInvalidator.on_hostel_infrastructure_mutation()
            return {
                "success": True,
                "dry_run": False,
                "total_rows": len(records),
                "valid_rows": valid_rows,
                "invalid_rows": 0,
                "errors": [],
                "created_count": created_count,
                "updated_count": updated_count,
            }
        except Exception as e:
            cursor.execute("ROLLBACK TO SAVEPOINT bulk_import_savepoint;")
            logger.error(f"Bulk import error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Bulk import transaction rolled back due to error: {str(e)}")

    @classmethod
    def bulk_export(
        cls,
        conn: sqlite3.Connection,
        entity_type: str,
        campus_id: Optional[int] = None,
        hostel_id: Optional[int] = None,
        export_format: str = "json",
    ) -> Any:
        cursor = conn.cursor()
        allowed_entities = ("campuses", "hostels", "buildings", "blocks", "floors", "rooms", "beds")
        if entity_type not in allowed_entities:
            raise HTTPException(status_code=400, detail=f"Unsupported entity type '{entity_type}'. Allowed: {allowed_entities}")

        if entity_type == "campuses":
            cursor.execute("SELECT id, name, code, address, city, state, country, operating_status, is_active FROM campuses ORDER BY name ASC;")
        elif entity_type == "hostels":
            cursor.execute("SELECT id, campus_id, name, code, hostel_type, category, curfew_time, is_active FROM hostels ORDER BY name ASC;")
        elif entity_type == "buildings":
            cursor.execute("SELECT id, hostel_id, campus_id, name, code, total_floors, condition_rating, is_active FROM buildings ORDER BY name ASC;")
        elif entity_type == "blocks":
            cursor.execute("SELECT id, building_id, hostel_id, name, code, description, is_active FROM blocks ORDER BY name ASC;")
        elif entity_type == "floors":
            cursor.execute("SELECT id, building_id, block_id, floor_number, floor_name, is_active FROM floors ORDER BY floor_number ASC;")
        elif entity_type == "rooms":
            cursor.execute("SELECT id, floor_id, room_number, room_type, capacity, base_fee, status, maintenance_status, is_active FROM rooms ORDER BY room_number ASC;")
        elif entity_type == "beds":
            cursor.execute("SELECT id, room_id, bed_number, status, maintenance_status, monthly_rate, is_active FROM beds ORDER BY bed_number ASC;")

        col_names = [col[0] for col in cursor.description]
        rows = [dict(zip(col_names, row)) for row in cursor.fetchall()]

        if export_format.lower() == "csv":
            output = io.StringIO()
            if rows:
                writer = csv.DictWriter(output, fieldnames=col_names)
                writer.writeheader()
                writer.writerows(rows)
            return output.getvalue()
        return rows
