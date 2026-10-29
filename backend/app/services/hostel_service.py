"""Hostel and Building Business Logic Service.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms)
"""

import sqlite3
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from backend.app.models.hostel_dto import BuildingCreate, BuildingUpdate, HostelCreate, HostelUpdate


class HostelService:
    @staticmethod
    def get_all_hostels(
        conn: sqlite3.Connection,
        hostel_type: Optional[str] = None,
        is_active: Optional[int] = None,
        search: Optional[str] = None,
        user_hostel_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve all hostels with real-time capacity and occupancy metrics."""
        query = """
            SELECT 
                h.id, h.name, h.code, h.hostel_type, h.address, h.warden_id,
                h.contact_phone, h.contact_email, h.is_active, h.created_at, h.updated_at,
                u.first_name || ' ' || u.last_name AS warden_name,
                (SELECT COUNT(*) FROM buildings b WHERE b.hostel_id = h.id AND b.is_active = 1) AS total_buildings,
                (
                    SELECT COUNT(*) 
                    FROM rooms r 
                    JOIN floors f ON r.floor_id = f.id 
                    JOIN buildings b ON f.building_id = b.id 
                    WHERE b.hostel_id = h.id AND r.is_active = 1
                ) AS total_rooms,
                (
                    SELECT COUNT(*) 
                    FROM beds bd
                    JOIN rooms r ON bd.room_id = r.id
                    JOIN floors f ON r.floor_id = f.id
                    JOIN buildings b ON f.building_id = b.id
                    WHERE b.hostel_id = h.id
                ) AS total_beds,
                (
                    SELECT COUNT(DISTINCT ra.bed_id)
                    FROM room_allocations ra
                    JOIN beds bd ON ra.bed_id = bd.id
                    JOIN rooms r ON bd.room_id = r.id
                    JOIN floors f ON r.floor_id = f.id
                    JOIN buildings b ON f.building_id = b.id
                    WHERE b.hostel_id = h.id AND ra.allocation_status = 'Active'
                ) AS occupied_beds,
                (
                    SELECT COUNT(*)
                    FROM beds bd
                    JOIN rooms r ON bd.room_id = r.id
                    JOIN floors f ON r.floor_id = f.id
                    JOIN buildings b ON f.building_id = b.id
                    WHERE b.hostel_id = h.id AND bd.status = 'Available' AND r.is_active = 1 AND b.is_active = 1
                ) AS available_beds
            FROM hostels h
            LEFT JOIN users u ON h.warden_id = u.id
            WHERE 1=1
        """
        params: List[Any] = []

        if user_hostel_id is not None:
            query += " AND h.id = ?"
            params.append(user_hostel_id)

        if hostel_type:
            query += " AND h.hostel_type = ?"
            params.append(hostel_type)

        if is_active is not None:
            query += " AND h.is_active = ?"
            params.append(is_active)

        if search:
            query += " AND (h.name LIKE ? OR h.code LIKE ? OR h.address LIKE ?)"
            term = f"%{search.strip()}%"
            params.extend([term, term, term])

        query += " ORDER BY h.name ASC;"

        cursor = conn.cursor()
        rows = cursor.execute(query, params).fetchall()

        results = []
        for r in rows:
            tot_beds = r["total_beds"] or 0
            occ_beds = r["occupied_beds"] or 0
            rate = round((occ_beds / tot_beds * 100), 1) if tot_beds > 0 else 0.0
            item = dict(r)
            item["occupancy_rate"] = rate
            results.append(item)
        return results

    @staticmethod
    def get_hostel_by_id(conn: sqlite3.Connection, hostel_id: int) -> Dict[str, Any]:
        """Fetch a single hostel's details with operational summaries."""
        cursor = conn.cursor()
        hostel = cursor.execute("""
            SELECT 
                h.id, h.name, h.code, h.hostel_type, h.address, h.warden_id,
                h.contact_phone, h.contact_email, h.is_active, h.created_at, h.updated_at,
                u.first_name || ' ' || u.last_name AS warden_name,
                u.email AS warden_email, u.phone AS warden_phone
            FROM hostels h
            LEFT JOIN users u ON h.warden_id = u.id
            WHERE h.id = ?;
        """, (hostel_id,)).fetchone()

        if not hostel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hostel not found.")

        # Buildings summary
        buildings = cursor.execute("""
            SELECT 
                b.id, b.hostel_id, b.name, b.code, b.total_floors, b.is_active, b.created_at,
                (SELECT COUNT(*) FROM floors f WHERE f.building_id = b.id) AS floor_count,
                (
                    SELECT COUNT(*) 
                    FROM rooms r 
                    JOIN floors f ON r.floor_id = f.id 
                    WHERE f.building_id = b.id AND r.is_active = 1
                ) AS room_count,
                (
                    SELECT COUNT(*) 
                    FROM beds bd 
                    JOIN rooms r ON bd.room_id = r.id 
                    JOIN floors f ON r.floor_id = f.id 
                    WHERE f.building_id = b.id
                ) AS bed_count,
                (
                    SELECT COUNT(DISTINCT ra.bed_id)
                    FROM room_allocations ra
                    JOIN beds bd ON ra.bed_id = bd.id
                    JOIN rooms r ON bd.room_id = r.id
                    JOIN floors f ON r.floor_id = f.id
                    WHERE f.building_id = b.id AND ra.allocation_status = 'Active'
                ) AS occupied_beds
            FROM buildings b
            WHERE b.hostel_id = ?
            ORDER BY b.name ASC;
        """, (hostel_id,)).fetchall()

        building_list = []
        total_beds = 0
        total_occupied = 0
        total_rooms = 0

        for b in buildings:
            b_beds = b["bed_count"] or 0
            b_occ = b["occupied_beds"] or 0
            b_rate = round((b_occ / b_beds * 100), 1) if b_beds > 0 else 0.0
            total_beds += b_beds
            total_occupied += b_occ
            total_rooms += (b["room_count"] or 0)
            b_dict = dict(b)
            b_dict["occupancy_rate"] = b_rate
            building_list.append(b_dict)

        hostel_dict = dict(hostel)
        hostel_dict["buildings"] = building_list
        hostel_dict["total_buildings"] = len(building_list)
        hostel_dict["total_rooms"] = total_rooms
        hostel_dict["total_beds"] = total_beds
        hostel_dict["occupied_beds"] = total_occupied
        hostel_dict["available_beds"] = max(0, total_beds - total_occupied)
        hostel_dict["occupancy_rate"] = round((total_occupied / total_beds * 100), 1) if total_beds > 0 else 0.0

        return hostel_dict

    @staticmethod
    def create_hostel(conn: sqlite3.Connection, data: HostelCreate) -> Dict[str, Any]:
        """Create a new hostel with unique code and name validation."""
        cursor = conn.cursor()

        # Check unique code
        existing_code = cursor.execute("SELECT id FROM hostels WHERE code = ?;", (data.code.strip().upper(),)).fetchone()
        if existing_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Hostel code '{data.code}' already exists.")

        # Check unique name
        existing_name = cursor.execute("SELECT id FROM hostels WHERE name = ?;", (data.name.strip(),)).fetchone()
        if existing_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Hostel name '{data.name}' already exists.")

        # Check warden if assigned
        if data.warden_id:
            warden = cursor.execute("SELECT id FROM users WHERE id = ?;", (data.warden_id,)).fetchone()
            if not warden:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Assigned warden user ID {data.warden_id} does not exist.")

        valid_types = ("Boys", "Girls", "Co-Ed")
        if data.hostel_type not in valid_types:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid hostel type. Must be one of: {', '.join(valid_types)}")

        cursor.execute("""
            INSERT INTO hostels (name, code, hostel_type, address, warden_id, contact_phone, contact_email, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            data.name.strip(),
            data.code.strip().upper(),
            data.hostel_type,
            data.address.strip() if data.address else "",
            data.warden_id,
            data.contact_phone.strip() if data.contact_phone else "",
            data.contact_email.strip() if data.contact_email else "",
            data.is_active
        ))
        conn.commit()
        new_id = cursor.lastrowid
        return HostelService.get_hostel_by_id(conn, new_id)

    @staticmethod
    def update_hostel(conn: sqlite3.Connection, hostel_id: int, data: HostelUpdate) -> Dict[str, Any]:
        """Update existing hostel properties."""
        cursor = conn.cursor()
        existing = cursor.execute("SELECT id, name, code FROM hostels WHERE id = ?;", (hostel_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hostel not found.")

        updates = []
        params = []

        if data.name is not None:
            name_val = data.name.strip()
            conflict = cursor.execute("SELECT id FROM hostels WHERE name = ? AND id != ?;", (name_val, hostel_id)).fetchone()
            if conflict:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Hostel name '{name_val}' already in use.")
            updates.append("name = ?")
            params.append(name_val)

        if data.code is not None:
            code_val = data.code.strip().upper()
            conflict = cursor.execute("SELECT id FROM hostels WHERE code = ? AND id != ?;", (code_val, hostel_id)).fetchone()
            if conflict:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Hostel code '{code_val}' already in use.")
            updates.append("code = ?")
            params.append(code_val)

        if data.hostel_type is not None:
            if data.hostel_type not in ("Boys", "Girls", "Co-Ed"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid hostel type.")
            updates.append("hostel_type = ?")
            params.append(data.hostel_type)

        if data.address is not None:
            updates.append("address = ?")
            params.append(data.address.strip())

        if data.warden_id is not None:
            if data.warden_id != 0:
                warden = cursor.execute("SELECT id FROM users WHERE id = ?;", (data.warden_id,)).fetchone()
                if not warden:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned warden user ID does not exist.")
                updates.append("warden_id = ?")
                params.append(data.warden_id)
            else:
                updates.append("warden_id = NULL")

        if data.contact_phone is not None:
            updates.append("contact_phone = ?")
            params.append(data.contact_phone.strip())

        if data.contact_email is not None:
            updates.append("contact_email = ?")
            params.append(data.contact_email.strip())

        if data.is_active is not None:
            updates.append("is_active = ?")
            params.append(data.is_active)

        if not updates:
            return HostelService.get_hostel_by_id(conn, hostel_id)

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(hostel_id)

        cursor.execute(f"UPDATE hostels SET {', '.join(updates)} WHERE id = ?;", params)
        conn.commit()
        return HostelService.get_hostel_by_id(conn, hostel_id)

    @staticmethod
    def set_hostel_status(conn: sqlite3.Connection, hostel_id: int, is_active: int) -> Dict[str, Any]:
        """Activate or deactivate a hostel, verifying active allocations if deactivating."""
        cursor = conn.cursor()
        if is_active == 0:
            # Check for active allocations
            active_allocs = cursor.execute("""
                SELECT COUNT(*)
                FROM room_allocations ra
                JOIN beds bd ON ra.bed_id = bd.id
                JOIN rooms r ON bd.room_id = r.id
                JOIN floors f ON r.floor_id = f.id
                JOIN buildings b ON f.building_id = b.id
                WHERE b.hostel_id = ? AND ra.allocation_status = 'Active';
            """, (hostel_id,)).fetchone()[0]
            if active_allocs > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot deactivate hostel. There are {active_allocs} active student allocation(s) in this hostel."
                )

        cursor.execute("UPDATE hostels SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (is_active, hostel_id))
        conn.commit()
        return {"id": hostel_id, "is_active": is_active, "message": f"Hostel status updated to {'active' if is_active == 1 else 'inactive'}."}

    # ==================== BUILDINGS ====================

    @staticmethod
    def get_buildings_for_hostel(conn: sqlite3.Connection, hostel_id: int) -> List[Dict[str, Any]]:
        """Retrieve all buildings for a given hostel with aggregated metrics."""
        cursor = conn.cursor()
        hostel = cursor.execute("SELECT id FROM hostels WHERE id = ?;", (hostel_id,)).fetchone()
        if not hostel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hostel not found.")

        rows = cursor.execute("""
            SELECT 
                b.id, b.hostel_id, b.name, b.code, b.total_floors, b.is_active, b.created_at,
                (SELECT COUNT(*) FROM floors f WHERE f.building_id = b.id) AS floor_count,
                (
                    SELECT COUNT(*) 
                    FROM rooms r 
                    JOIN floors f ON r.floor_id = f.id 
                    WHERE f.building_id = b.id AND r.is_active = 1
                ) AS room_count,
                (
                    SELECT COUNT(*) 
                    FROM beds bd 
                    JOIN rooms r ON bd.room_id = r.id 
                    JOIN floors f ON r.floor_id = f.id 
                    WHERE f.building_id = b.id
                ) AS bed_count,
                (
                    SELECT COUNT(DISTINCT ra.bed_id)
                    FROM room_allocations ra
                    JOIN beds bd ON ra.bed_id = bd.id
                    JOIN rooms r ON bd.room_id = r.id
                    JOIN floors f ON r.floor_id = f.id
                    WHERE f.building_id = b.id AND ra.allocation_status = 'Active'
                ) AS occupied_beds,
                (
                    SELECT COUNT(*)
                    FROM beds bd
                    JOIN rooms r ON bd.room_id = r.id
                    JOIN floors f ON r.floor_id = f.id
                    WHERE f.building_id = b.id AND bd.status = 'Available' AND r.is_active = 1
                ) AS available_beds
            FROM buildings b
            WHERE b.hostel_id = ?
            ORDER BY b.name ASC;
        """, (hostel_id,)).fetchall()

        results = []
        for r in rows:
            tot = r["bed_count"] or 0
            occ = r["occupied_beds"] or 0
            rate = round((occ / tot * 100), 1) if tot > 0 else 0.0
            item = dict(r)
            item["occupancy_rate"] = rate
            results.append(item)
        return results

    @staticmethod
    def create_building(conn: sqlite3.Connection, hostel_id: int, data: BuildingCreate) -> Dict[str, Any]:
        """Create a new building under a specific hostel."""
        cursor = conn.cursor()
        hostel = cursor.execute("SELECT id, name FROM hostels WHERE id = ?;", (hostel_id,)).fetchone()
        if not hostel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hostel not found.")

        # Check unique building name within hostel
        conflict_name = cursor.execute(
            "SELECT id FROM buildings WHERE hostel_id = ? AND name = ?;", (hostel_id, data.name.strip())
        ).fetchone()
        if conflict_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Building name '{data.name}' already exists in this hostel.")

        # Check unique building code within hostel
        conflict_code = cursor.execute(
            "SELECT id FROM buildings WHERE hostel_id = ? AND code = ?;", (hostel_id, data.code.strip().upper())
        ).fetchone()
        if conflict_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Building code '{data.code}' already exists in this hostel.")

        cursor.execute("""
            INSERT INTO buildings (hostel_id, name, code, total_floors, is_active)
            VALUES (?, ?, ?, ?, ?);
        """, (
            hostel_id,
            data.name.strip(),
            data.code.strip().upper(),
            data.total_floors,
            data.is_active
        ))
        conn.commit()
        new_id = cursor.lastrowid
        return HostelService.get_building_by_id(conn, new_id)

    @staticmethod
    def get_building_by_id(conn: sqlite3.Connection, building_id: int) -> Dict[str, Any]:
        """Fetch building details by ID."""
        cursor = conn.cursor()
        b = cursor.execute("""
            SELECT 
                b.id, b.hostel_id, b.name, b.code, b.total_floors, b.is_active, b.created_at,
                h.name AS hostel_name, h.code AS hostel_code
            FROM buildings b
            JOIN hostels h ON b.hostel_id = h.id
            WHERE b.id = ?;
        """, (building_id,)).fetchone()

        if not b:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found.")

        # Aggregate counts
        stats = cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM floors WHERE building_id = ?) AS floor_count,
                (
                    SELECT COUNT(*) 
                    FROM rooms r 
                    JOIN floors f ON r.floor_id = f.id 
                    WHERE f.building_id = ? AND r.is_active = 1
                ) AS room_count,
                (
                    SELECT COUNT(*) 
                    FROM beds bd 
                    JOIN rooms r ON bd.room_id = r.id 
                    JOIN floors f ON r.floor_id = f.id 
                    WHERE f.building_id = ?
                ) AS bed_count,
                (
                    SELECT COUNT(DISTINCT ra.bed_id)
                    FROM room_allocations ra
                    JOIN beds bd ON ra.bed_id = bd.id
                    JOIN rooms r ON bd.room_id = r.id
                    JOIN floors f ON r.floor_id = f.id
                    WHERE f.building_id = ? AND ra.allocation_status = 'Active'
                ) AS occupied_beds
        """, (building_id, building_id, building_id, building_id)).fetchone()

        b_dict = dict(b)
        tot_beds = stats["bed_count"] or 0
        occ_beds = stats["occupied_beds"] or 0
        b_dict["floor_count"] = stats["floor_count"] or 0
        b_dict["room_count"] = stats["room_count"] or 0
        b_dict["bed_count"] = tot_beds
        b_dict["occupied_beds"] = occ_beds
        b_dict["available_beds"] = max(0, tot_beds - occ_beds)
        b_dict["occupancy_rate"] = round((occ_beds / tot_beds * 100), 1) if tot_beds > 0 else 0.0

        return b_dict

    @staticmethod
    def update_building(conn: sqlite3.Connection, building_id: int, data: BuildingUpdate) -> Dict[str, Any]:
        """Update building attributes."""
        cursor = conn.cursor()
        existing = cursor.execute("SELECT id, hostel_id FROM buildings WHERE id = ?;", (building_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found.")

        hostel_id = existing["hostel_id"]
        updates = []
        params = []

        if data.name is not None:
            name_val = data.name.strip()
            conflict = cursor.execute(
                "SELECT id FROM buildings WHERE hostel_id = ? AND name = ? AND id != ?;", (hostel_id, name_val, building_id)
            ).fetchone()
            if conflict:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Building name '{name_val}' already in use in this hostel.")
            updates.append("name = ?")
            params.append(name_val)

        if data.code is not None:
            code_val = data.code.strip().upper()
            conflict = cursor.execute(
                "SELECT id FROM buildings WHERE hostel_id = ? AND code = ? AND id != ?;", (hostel_id, code_val, building_id)
            ).fetchone()
            if conflict:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Building code '{code_val}' already in use in this hostel.")
            updates.append("code = ?")
            params.append(code_val)

        if data.total_floors is not None:
            # Cannot reduce total floors below existing floor count
            existing_floors = cursor.execute("SELECT COUNT(*) FROM floors WHERE building_id = ?;", (building_id,)).fetchone()[0]
            if data.total_floors < existing_floors:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot reduce total floors to {data.total_floors}. Building already has {existing_floors} registered floor(s)."
                )
            updates.append("total_floors = ?")
            params.append(data.total_floors)

        if data.is_active is not None:
            if data.is_active == 0:
                # Check active allocations
                active_allocs = cursor.execute("""
                    SELECT COUNT(*)
                    FROM room_allocations ra
                    JOIN beds bd ON ra.bed_id = bd.id
                    JOIN rooms r ON bd.room_id = r.id
                    JOIN floors f ON r.floor_id = f.id
                    WHERE f.building_id = ? AND ra.allocation_status = 'Active';
                """, (building_id,)).fetchone()[0]
                if active_allocs > 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot deactivate building. There are {active_allocs} active allocation(s) in this building."
                    )
            updates.append("is_active = ?")
            params.append(data.is_active)

        if not updates:
            return HostelService.get_building_by_id(conn, building_id)

        params.append(building_id)
        cursor.execute(f"UPDATE buildings SET {', '.join(updates)} WHERE id = ?;", params)
        conn.commit()
        return HostelService.get_building_by_id(conn, building_id)

    @staticmethod
    def get_warden_candidates(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        """Retrieve users eligible for warden or administrator assignments."""
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT DISTINCT u.id, u.username, u.first_name, u.last_name, u.email, u.phone, r.name AS role_name
            FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            JOIN roles r ON ur.role_id = r.id
            WHERE r.name IN ('hostel_admin', 'warden', 'assistant_warden', 'super_admin') AND u.is_active = 1
            ORDER BY u.first_name ASC;
        """).fetchall()
        return [dict(r) for r in rows]
