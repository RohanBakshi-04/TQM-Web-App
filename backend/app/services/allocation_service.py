"""Student Room and Bed Allocation Business Logic Service with Poka-Yoke System.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms)
Poka-Yoke: Defect-Proof Relational Integrity & Concurrency Protection
"""

import hashlib
import sqlite3
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from backend.app.models.allocation_dto import (
    AllocationCreate,
    CheckoutRequest,
    TransferRequestCreate,
    TransferReview,
)
from backend.app.services.cache_invalidation import CacheInvalidator
from backend.app.utils.logger import logger


class AllocationService:
    """Enterprise-grade Room Allocation & Poka-Yoke Defect Prevention Engine."""

    @staticmethod
    def create_allocation(
        conn: sqlite3.Connection,
        data: AllocationCreate,
        allocated_by_user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Allocate a student to a room bed with 10-layer Poka-Yoke validation."""
        cursor = conn.cursor()

        # Poka-Yoke Check 1: Student existence and eligibility
        student = cursor.execute("""
            SELECT id, student_id, first_name, last_name, gender, status, branch, academic_year
            FROM students
            WHERE id = ?;
        """, (data.student_id,)).fetchone()

        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student ID {data.student_id} not found.")

        if student["status"] != "Active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Ineligible student. Student '{student['first_name']} {student['last_name']}' is '{student['status']}' (Only 'Active' students can be allocated)."
            )

        # Poka-Yoke Check 7: Prevent duplicate active allocations for the same student
        existing_alloc = cursor.execute("""
            SELECT ra.id, ra.bed_id, r.room_number, h.name AS hostel_name
            FROM room_allocations ra
            JOIN rooms r ON ra.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE ra.student_id = ? AND ra.allocation_status = 'Active';
        """, (data.student_id,)).fetchone()

        if existing_alloc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Poka-Yoke Violation: Student already possesses an Active allocation "
                    f"(Allocation ID: {existing_alloc['id']} in Room {existing_alloc['room_number']}, {existing_alloc['hostel_name']}). "
                    f"Duplicate active student allocations are strictly prohibited."
                )
            )

        # Retrieve Bed, Room, Floor, Building, and Hostel hierarchy
        bed_info = cursor.execute("""
            SELECT 
                bd.id AS bed_id, bd.bed_number, bd.status AS bed_status,
                r.id AS room_id, r.room_number, r.room_type, r.capacity, r.base_fee, 
                r.status AS room_status, r.is_active AS room_active,
                f.id AS floor_id, f.floor_number, f.floor_name,
                b.id AS building_id, b.name AS building_name, b.is_active AS building_active,
                h.id AS hostel_id, h.name AS hostel_name, h.code AS hostel_code, 
                h.hostel_type, h.is_active AS hostel_active
            FROM beds bd
            JOIN rooms r ON bd.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE bd.id = ?;
        """, (data.bed_id,)).fetchone()

        if not bed_info:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bed ID {data.bed_id} not found.")

        # Poka-Yoke Check 5: Allocating students to inactive hostels or buildings
        if not bed_info["hostel_active"] or not bed_info["building_active"] or not bed_info["room_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Poka-Yoke Violation: Cannot allocate student to an inactive hostel, building, or room."
            )

        # Poka-Yoke Check 6: Allocating students to restricted hostels (Gender mismatch)
        h_type = bed_info["hostel_type"]
        s_gender = student["gender"]
        if h_type == "Boys" and s_gender != "Male":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Gender restriction mismatch. Student gender is '{s_gender}', but '{bed_info['hostel_name']}' is restricted to 'Boys'."
            )
        elif h_type == "Girls" and s_gender != "Female":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Gender restriction mismatch. Student gender is '{s_gender}', but '{bed_info['hostel_name']}' is restricted to 'Girls'."
            )

        # Poka-Yoke Check 4: Allocating students to rooms under maintenance
        if bed_info["room_status"] == "Maintenance":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Room {bed_info['room_number']} is currently under Maintenance."
            )

        # Poka-Yoke Check 3: Allocating students to inactive or maintenance beds
        if bed_info["bed_status"] == "Maintenance":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Bed {bed_info['bed_number']} is under Maintenance."
            )

        if bed_info["bed_status"] != "Available":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Bed {bed_info['bed_number']} is not available (Current status: '{bed_info['bed_status']}')."
            )

        # Poka-Yoke Check 1: Allocating one bed to multiple active students (Concurrency check)
        bed_alloc = cursor.execute("""
            SELECT id FROM room_allocations WHERE bed_id = ? AND allocation_status = 'Active';
        """, (data.bed_id,)).fetchone()
        if bed_alloc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Poka-Yoke Violation: Bed {bed_info['bed_number']} already has an active allocation (Allocation ID: {bed_alloc['id']})."
            )

        # Poka-Yoke Check 2: Allocating students to full rooms
        current_occ = cursor.execute("""
            SELECT COUNT(*) FROM room_allocations WHERE room_id = ? AND allocation_status = 'Active';
        """, (bed_info["room_id"],)).fetchone()[0]

        if current_occ >= bed_info["capacity"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Room {bed_info['room_number']} has reached maximum capacity ({current_occ}/{bed_info['capacity']})."
            )

        # Date validations
        start_dt = data.start_date.strip()
        end_dt = data.end_date.strip() if data.end_date else None
        if end_dt and end_dt < start_dt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Poka-Yoke Violation: Expected checkout date cannot be earlier than allocation start date."
            )

        # ATOMIC EXECUTION (BEGIN IMMEDIATE in SQLite)
        try:
            cursor.execute("BEGIN IMMEDIATE;")

            # 1. Insert allocation record
            cursor.execute("""
                INSERT INTO room_allocations (
                    student_id, bed_id, room_id, start_date, end_date,
                    fee_status, allocation_status, approval_status, remarks, allocated_by,
                    checkin_date
                )
                VALUES (?, ?, ?, ?, ?, ?, 'Active', 'Approved', ?, ?, ?);
            """, (
                data.student_id,
                data.bed_id,
                bed_info["room_id"],
                start_dt,
                end_dt,
                data.fee_status or "Pending",
                data.remarks or "",
                allocated_by_user_id,
                start_dt # Automatically record initial check-in date on creation
            ))
            allocation_id = cursor.lastrowid

            # 2. Update Bed status to Occupied
            cursor.execute("UPDATE beds SET status = 'Occupied', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (data.bed_id,))

            # 3. Update Room status based on new capacity
            new_occ = current_occ + 1
            new_status = "Full" if new_occ >= bed_info["capacity"] else "Partially_Occupied"
            cursor.execute("UPDATE rooms SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (new_status, bed_info["room_id"]))

            # 4. Audit Log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details)
                VALUES (?, 'staff', 'ALLOCATE_ROOM', 'room_allocations', ?, ?);
            """, (
                allocated_by_user_id or 1,
                str(allocation_id),
                f"Student {student['student_id']} allocated to {bed_info['hostel_code']} Room {bed_info['room_number']} Bed {bed_info['bed_number']}"
            ))

            conn.commit()
            h_id = bed_info["hostel_id"] if "hostel_id" in bed_info.keys() else None
            CacheInvalidator.on_allocation_mutation(hostel_id=h_id)
            logger.info(f"Poka-Yoke Allocation Created: Student {student['student_id']} -> Bed {bed_info['bed_number']} (Allocation #{allocation_id})")

        except sqlite3.IntegrityError as err:
            conn.rollback()
            logger.error(f"Integrity constraint violation during allocation: {err}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Poka-Yoke Constraint Violation: Database prevented duplicate or conflicting allocation ({str(err)})."
            )
        except Exception as e:
            conn.rollback()
            raise e

        return AllocationService.get_allocation_by_id(conn, allocation_id)

    @staticmethod
    def get_allocation_by_id(conn: sqlite3.Connection, allocation_id: int) -> Dict[str, Any]:
        """Fetch complete details of an allocation including confirmation metadata."""
        cursor = conn.cursor()
        row = cursor.execute("""
            SELECT 
                ra.id, ra.student_id, ra.bed_id, ra.room_id, ra.start_date, ra.end_date,
                ra.checkin_date, ra.checkout_date, ra.checkout_reason,
                ra.fee_status, ra.allocation_status, ra.approval_status, ra.remarks,
                ra.allocated_by, ra.created_at,
                s.student_id AS student_enrollment, s.first_name || ' ' || s.last_name AS student_name,
                s.gender AS student_gender, s.branch AS student_branch, s.academic_year AS student_academic_year,
                bd.bed_number,
                r.room_number, r.room_type, r.capacity AS room_capacity, r.base_fee AS room_base_fee,
                f.id AS floor_id, f.floor_number, f.floor_name,
                b.id AS building_id, b.name AS building_name,
                h.id AS hostel_id, h.name AS hostel_name, h.code AS hostel_code
            FROM room_allocations ra
            JOIN students s ON ra.student_id = s.id
            JOIN beds bd ON ra.bed_id = bd.id
            JOIN rooms r ON ra.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE ra.id = ?;
        """, (allocation_id,)).fetchone()

        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room allocation not found.")

        result = dict(row)

        # Generate cryptographic verification hash for confirmation slip
        hash_payload = f"ALLOC-{result['id']}-{result['student_enrollment']}-{result['bed_number']}-{result['created_at']}"
        result["confirmation_number"] = f"TQM-ALC-{result['id']:06d}"
        result["verification_hash"] = hashlib.sha256(hash_payload.encode()).hexdigest()[:16].upper()

        return result

    @staticmethod
    def get_allocations(
        conn: sqlite3.Connection,
        hostel_id: Optional[int] = None,
        building_id: Optional[int] = None,
        floor_id: Optional[int] = None,
        room_type: Optional[str] = None,
        allocation_status: Optional[str] = None,
        student_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List allocations with flexible filtering and Q05 response time SLA."""
        query = """
            SELECT 
                ra.id, ra.student_id, ra.bed_id, ra.room_id, ra.start_date, ra.end_date,
                ra.checkin_date, ra.checkout_date, ra.checkout_reason,
                ra.fee_status, ra.allocation_status, ra.approval_status, ra.remarks,
                ra.allocated_by, ra.created_at,
                s.student_id AS student_enrollment, s.first_name || ' ' || s.last_name AS student_name,
                s.gender AS student_gender, s.branch AS student_branch, s.academic_year AS student_academic_year,
                bd.bed_number,
                r.room_number, r.room_type, r.capacity AS room_capacity, r.base_fee AS room_base_fee,
                f.id AS floor_id, f.floor_number, f.floor_name,
                b.id AS building_id, b.name AS building_name,
                h.id AS hostel_id, h.name AS hostel_name, h.code AS hostel_code
            FROM room_allocations ra
            JOIN students s ON ra.student_id = s.id
            JOIN beds bd ON ra.bed_id = bd.id
            JOIN rooms r ON ra.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE 1=1
        """
        params: List[Any] = []

        if hostel_id:
            query += " AND h.id = ?"
            params.append(hostel_id)
        if building_id:
            query += " AND b.id = ?"
            params.append(building_id)
        if floor_id:
            query += " AND f.id = ?"
            params.append(floor_id)
        if room_type:
            query += " AND r.room_type = ?"
            params.append(room_type)
        if allocation_status:
            query += " AND ra.allocation_status = ?"
            params.append(allocation_status)
        if student_id:
            query += " AND ra.student_id = ?"
            params.append(student_id)
        if search:
            query += """ AND (
                s.first_name LIKE ? OR s.last_name LIKE ? OR s.student_id LIKE ? 
                OR r.room_number LIKE ? OR bd.bed_number LIKE ? OR h.name LIKE ?
            )"""
            term = f"%{search.strip()}%"
            params.extend([term, term, term, term, term, term])

        query += " ORDER BY ra.id DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        cursor = conn.cursor()
        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_allocation_suggestions(
        conn: sqlite3.Connection,
        student_id: int,
        preferred_hostel_id: Optional[int] = None,
        preferred_room_type: Optional[str] = None,
        floor_preference: Optional[int] = None,
        max_suggestions: int = 10
    ) -> List[Dict[str, Any]]:
        """Intelligent Room Allocation Suggestion Engine.

        Evaluates available inventory against student eligibility, gender constraints,
        institutional policies, cohort clustering (branch/year), and personal preferences.
        """
        cursor = conn.cursor()

        # 1. Verify student eligibility
        student = cursor.execute("""
            SELECT id, student_id, first_name, last_name, gender, branch, academic_year, email, status
            FROM students
            WHERE id = ?;
        """, (student_id,)).fetchone()

        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student ID {student_id} not found.")

        if student["status"] != "Active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Student '{student['first_name']} {student['last_name']}' is not Active (Status: {student['status']}). Ineligible for allocation."
            )

        # Retrieve preference from admission application if not explicitly provided
        target_room_type = preferred_room_type
        if not target_room_type:
            app_pref = cursor.execute("""
                SELECT preferred_room_type 
                FROM admission_applications 
                WHERE email = ? OR applicant_name LIKE ?
                ORDER BY id DESC LIMIT 1;
            """, (student["email"], f"%{student['first_name']}%")).fetchone()
            if app_pref and app_pref["preferred_room_type"]:
                target_room_type = app_pref["preferred_room_type"]

        # 2. Query available candidate beds matching gender policy
        gender_compatible = student["gender"]
        candidates = AllocationService.get_available_beds(
            conn=conn,
            hostel_id=preferred_hostel_id,
            room_type=None,
            gender_compatible=gender_compatible
        )

        scored_suggestions = []

        for b in candidates:
            score = 50 # Base score for eligible, clean, available bed
            reasons = [f"Gender Policy Matched: '{b['hostel_type']}' facility compatible with {student['gender']} student"]

            # Preferred Hostel Match
            if preferred_hostel_id and b["hostel_id"] == preferred_hostel_id:
                score += 25
                reasons.append(f"Hostel Preference: Selected '{b['hostel_name']}'")

            # Preferred Room Type Match
            if target_room_type and b["room_type"].lower() == target_room_type.lower():
                score += 25
                reasons.append(f"Room Type Preference: Matched '{b['room_type']}' configuration")

            # Floor Preference Match
            if floor_preference is not None and b["floor_number"] == floor_preference:
                score += 15
                reasons.append(f"Floor Preference: Level {b['floor_number']} ({b['floor_name']})")

            # Occupancy & Peer Roommate Analysis
            occupants = AllocationService.get_room_occupants(conn, b["room_id"])
            if occupants:
                score += 10
                reasons.append(f"Occupancy Consolidation: {len(occupants)} of {b['capacity']} beds currently occupied")

                # Check branch clustering
                same_branch = [o for o in occupants if o["branch"].lower() == student["branch"].lower()]
                if same_branch:
                    score += 20
                    reasons.append(f"Academic Peer Match: Roommate ({same_branch[0]['student_name']}) is also in {student['branch']}")

                # Check academic year cohort
                same_year = [o for o in occupants if o["academic_year"].lower() == student["academic_year"].lower()]
                if same_year:
                    score += 15
                    reasons.append(f"Cohort Alignment: Roommate is in the same class ({student['academic_year']})")
            else:
                reasons.append("Fresh Room: Fully available empty room")

            suggestion_item = {
                "bed_id": b["bed_id"],
                "bed_number": b["bed_number"],
                "room_id": b["room_id"],
                "room_number": b["room_number"],
                "room_type": b["room_type"],
                "base_fee": b["base_fee"],
                "floor_number": b["floor_number"],
                "floor_name": b["floor_name"],
                "building_id": b["building_id"],
                "building_name": b["building_name"],
                "hostel_id": b["hostel_id"],
                "hostel_name": b["hostel_name"],
                "hostel_type": b["hostel_type"],
                "match_score": score,
                "reasons": reasons,
                "existing_occupants": occupants
            }
            scored_suggestions.append(suggestion_item)

        # Sort highest match score first
        scored_suggestions.sort(key=lambda x: x["match_score"], reverse=True)
        return scored_suggestions[:max_suggestions]

    @staticmethod
    def get_available_beds(
        conn: sqlite3.Connection,
        hostel_id: Optional[int] = None,
        building_id: Optional[int] = None,
        floor_id: Optional[int] = None,
        room_type: Optional[str] = None,
        gender_compatible: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve all currently assignable beds across the institution."""
        query = """
            SELECT 
                bd.id AS bed_id, bd.bed_number,
                r.id AS room_id, r.room_number, r.room_type, r.capacity, r.base_fee,
                (SELECT COUNT(*) FROM room_allocations ra WHERE ra.room_id = r.id AND ra.allocation_status = 'Active') AS occupied_count,
                (r.capacity - (SELECT COUNT(*) FROM room_allocations ra WHERE ra.room_id = r.id AND ra.allocation_status = 'Active')) AS available_in_room,
                f.id AS floor_id, f.floor_number, f.floor_name,
                b.id AS building_id, b.name AS building_name,
                h.id AS hostel_id, h.name AS hostel_name, h.code AS hostel_code, h.hostel_type
            FROM beds bd
            JOIN rooms r ON bd.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE bd.status = 'Available'
              AND r.status != 'Maintenance'
              AND r.is_active = 1
              AND b.is_active = 1
              AND h.is_active = 1
              AND NOT EXISTS (
                  SELECT 1 FROM room_allocations ra 
                  WHERE ra.bed_id = bd.id AND ra.allocation_status = 'Active'
              )
        """
        params: List[Any] = []

        if hostel_id:
            query += " AND h.id = ?"
            params.append(hostel_id)
        if building_id:
            query += " AND b.id = ?"
            params.append(building_id)
        if floor_id:
            query += " AND f.id = ?"
            params.append(floor_id)
        if room_type:
            query += " AND r.room_type = ?"
            params.append(room_type)
        if gender_compatible:
            if gender_compatible.lower() == "male":
                query += " AND h.hostel_type IN ('Boys', 'Co-Ed')"
            elif gender_compatible.lower() == "female":
                query += " AND h.hostel_type IN ('Girls', 'Co-Ed')"

        query += " ORDER BY h.name, b.name, f.floor_number, r.room_number, bd.bed_number;"

        cursor = conn.cursor()
        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_room_occupants(conn: sqlite3.Connection, room_id: int) -> List[Dict[str, Any]]:
        """List active student occupants in a specified room."""
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT 
                ra.id AS allocation_id, ra.student_id,
                s.first_name || ' ' || s.last_name AS student_name,
                s.student_id AS student_enrollment, s.gender, s.branch, s.academic_year,
                bd.id AS bed_id, bd.bed_number,
                ra.start_date, ra.fee_status, ra.allocation_status
            FROM room_allocations ra
            JOIN students s ON ra.student_id = s.id
            JOIN beds bd ON ra.bed_id = bd.id
            WHERE ra.room_id = ? AND ra.allocation_status = 'Active'
            ORDER BY bd.bed_number ASC;
        """, (room_id,)).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_student_allocation_history(conn: sqlite3.Connection, student_id: int) -> List[Dict[str, Any]]:
        """Retrieve full chronological allocation and transfer history for a student."""
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT 
                ra.id, ra.start_date, ra.end_date, ra.checkin_date, ra.checkout_date,
                ra.checkout_reason, ra.fee_status, ra.allocation_status, ra.remarks,
                bd.bed_number, r.room_number, r.room_type,
                f.floor_name, b.name AS building_name, h.name AS hostel_name, h.code AS hostel_code
            FROM room_allocations ra
            JOIN beds bd ON ra.bed_id = bd.id
            JOIN rooms r ON ra.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE ra.student_id = ?
            ORDER BY ra.id DESC;
        """, (student_id,)).fetchall()
        return [dict(r) for r in rows]

    # ==================== CHECK-IN & CHECK-OUT LIFECYCLE ====================

    @staticmethod
    def checkin_allocation(
        conn: sqlite3.Connection,
        allocation_id: int,
        checkin_date: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Record verified student check-in and room occupation."""
        cursor = conn.cursor()
        alloc = cursor.execute("SELECT id, allocation_status, checkin_date, student_id, bed_id, room_id FROM room_allocations WHERE id = ?;", (allocation_id,)).fetchone()
        if not alloc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found.")

        if alloc["allocation_status"] != "Active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot check in. Allocation is '{alloc['allocation_status']}' (Only 'Active' allocations can be checked in)."
            )

        actual_date = checkin_date.strip() if checkin_date else date.today().isoformat()
        cursor.execute("""
            UPDATE room_allocations 
            SET checkin_date = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?;
        """, (actual_date, allocation_id))

        cursor.execute("""
            INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details)
            VALUES (?, 'staff', 'CHECK_IN_STUDENT', 'room_allocations', ?, ?);
        """, (user_id or 1, str(allocation_id), f"Student checked in on {actual_date}"))

        conn.commit()
        CacheInvalidator.on_allocation_mutation()
        return AllocationService.get_allocation_by_id(conn, allocation_id)

    @staticmethod
    def checkout_allocation(
        conn: sqlite3.Connection,
        allocation_id: int,
        checkout_date: Optional[str] = None,
        reason: str = "Academic Term Completion",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Release student bed and update room occupancy upon verified check-out."""
        cursor = conn.cursor()
        alloc = cursor.execute("""
            SELECT ra.id, ra.allocation_status, ra.bed_id, ra.room_id, ra.student_id,
                   r.capacity, s.student_id AS enrollment
            FROM room_allocations ra
            JOIN rooms r ON ra.room_id = r.id
            JOIN students s ON ra.student_id = s.id
            WHERE ra.id = ?;
        """, (allocation_id,)).fetchone()

        if not alloc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found.")

        # Poka-Yoke Check 9: Checking out students who have no active allocation & Duplicate checkouts
        if alloc["allocation_status"] != "Active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Cannot check out student who has no active allocation. Allocation #{allocation_id} is already '{alloc['allocation_status']}'."
            )

        actual_checkout = checkout_date.strip() if checkout_date else date.today().isoformat()

        try:
            cursor.execute("BEGIN IMMEDIATE;")

            # 1. Update allocation status to Vacated
            cursor.execute("""
                UPDATE room_allocations
                SET allocation_status = 'Vacated',
                    checkout_date = ?,
                    checkout_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (actual_checkout, reason.strip(), allocation_id))

            # 2. Release Bed to Available
            cursor.execute("UPDATE beds SET status = 'Available', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (alloc["bed_id"],))

            # 3. Recalculate and update Room occupancy status
            remaining_occ = cursor.execute("""
                SELECT COUNT(*) FROM room_allocations WHERE room_id = ? AND allocation_status = 'Active';
            """, (alloc["room_id"],)).fetchone()[0]

            new_room_status = "Available" if remaining_occ == 0 else "Partially_Occupied"
            cursor.execute("UPDATE rooms SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (new_room_status, alloc["room_id"]))

            # 4. Audit Log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details)
                VALUES (?, 'staff', 'CHECK_OUT_STUDENT', 'room_allocations', ?, ?);
            """, (
                user_id or 1,
                str(allocation_id),
                f"Student {alloc['enrollment']} checked out on {actual_checkout} (Reason: {reason})"
            ))

            conn.commit()
            CacheInvalidator.on_allocation_mutation()
            logger.info(f"Poka-Yoke Check-Out: Allocation #{allocation_id} Vacated. Bed #{alloc['bed_id']} Released to Available.")

        except Exception as e:
            conn.rollback()
            raise e

        return AllocationService.get_allocation_by_id(conn, allocation_id)

    # ==================== ROOM TRANSFERS ====================

    @staticmethod
    def request_or_execute_transfer(
        conn: sqlite3.Connection,
        allocation_id: int,
        to_bed_id: int,
        reason: str,
        user_id: int,
        user_roles: List[str]
    ) -> Dict[str, Any]:
        """Submit a room/bed transfer request, auto-executing if performed by authorized staff."""
        cursor = conn.cursor()

        # Fetch current active allocation
        alloc = cursor.execute("""
            SELECT ra.id, ra.student_id, ra.bed_id, ra.room_id, ra.allocation_status,
                   s.student_id AS enrollment, s.gender, s.first_name || ' ' || s.last_name AS student_name
            FROM room_allocations ra
            JOIN students s ON ra.student_id = s.id
            WHERE ra.id = ?;
        """, (allocation_id,)).fetchone()

        if not alloc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found.")

        if alloc["allocation_status"] != "Active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Cannot transfer inactive allocation (Current status: {alloc['allocation_status']})."
            )

        if alloc["bed_id"] == to_bed_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target bed cannot be the same as current bed.")

        # Poka-Yoke Check 8: Transferring students to unavailable beds
        target_bed = cursor.execute("""
            SELECT 
                bd.id, bd.bed_number, bd.status AS bed_status,
                r.id AS room_id, r.room_number, r.capacity, r.status AS room_status, r.is_active AS room_active,
                h.id AS hostel_id, h.name AS hostel_name, h.hostel_type, h.is_active AS hostel_active
            FROM beds bd
            JOIN rooms r ON bd.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE bd.id = ?;
        """, (to_bed_id,)).fetchone()

        if not target_bed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target bed not found.")

        if not target_bed["hostel_active"] or not target_bed["room_active"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Poka-Yoke Violation: Target hostel or room is inactive.")

        if target_bed["room_status"] == "Maintenance" or target_bed["bed_status"] == "Maintenance":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Poka-Yoke Violation: Target room or bed is under maintenance.")

        if target_bed["bed_status"] != "Available":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Violation: Target bed is unavailable (Current status: '{target_bed['bed_status']}')."
            )

        # Check gender restriction of target hostel
        if target_bed["hostel_type"] == "Boys" and alloc["gender"] != "Male":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Poka-Yoke Violation: Gender mismatch on target hostel.")
        elif target_bed["hostel_type"] == "Girls" and alloc["gender"] != "Female":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Poka-Yoke Violation: Gender mismatch on target hostel.")

        # Check if target room has capacity
        target_occ = cursor.execute("SELECT COUNT(*) FROM room_allocations WHERE room_id = ? AND allocation_status = 'Active';", (target_bed["room_id"],)).fetchone()[0]
        if target_occ >= target_bed["capacity"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Poka-Yoke Violation: Target room has reached maximum capacity.")

        # Check if user is staff (auto-execute) or student (create pending request)
        is_staff = bool(set(user_roles).intersection({"super_admin", "hostel_admin", "warden", "assistant_warden"}))

        if is_staff:
            return AllocationService._execute_atomic_transfer(
                conn=conn,
                old_allocation=alloc,
                target_bed_info=target_bed,
                reason=reason,
                reviewed_by_user_id=user_id
            )
        else:
            # Student submitted transfer request -> Pending
            cursor.execute("""
                INSERT INTO room_transfers (allocation_id, student_id, from_bed_id, to_bed_id, reason, status)
                VALUES (?, ?, ?, ?, ?, 'Pending');
            """, (allocation_id, alloc["student_id"], alloc["bed_id"], to_bed_id, reason.strip()))
            conn.commit()
            transfer_id = cursor.lastrowid
            return {
                "transfer_id": transfer_id,
                "status": "Pending",
                "message": "Transfer request submitted successfully. Awaiting administration/warden review."
            }

    @staticmethod
    def _execute_atomic_transfer(
        conn: sqlite3.Connection,
        old_allocation: sqlite3.Row,
        target_bed_info: sqlite3.Row,
        reason: str,
        reviewed_by_user_id: int,
        transfer_record_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute atomic database transaction for room transfer, releasing old bed and claiming new bed."""
        cursor = conn.cursor()
        today_str = date.today().isoformat()

        try:
            cursor.execute("BEGIN IMMEDIATE;")

            # 1. Mark previous allocation as Transferred
            cursor.execute("""
                UPDATE room_allocations
                SET allocation_status = 'Transferred',
                    end_date = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (today_str, old_allocation["id"]))

            # 2. Release previous bed to Available
            cursor.execute("UPDATE beds SET status = 'Available', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (old_allocation["bed_id"],))

            # 3. Recompute previous room status
            old_rem_occ = cursor.execute(
                "SELECT COUNT(*) FROM room_allocations WHERE room_id = ? AND allocation_status = 'Active';", (old_allocation["room_id"],)
            ).fetchone()[0]
            old_room_status = "Available" if old_rem_occ == 0 else "Partially_Occupied"
            cursor.execute("UPDATE rooms SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (old_room_status, old_allocation["room_id"]))

            # 4. Create new Active allocation for the student in target bed
            cursor.execute("""
                INSERT INTO room_allocations (
                    student_id, bed_id, room_id, start_date, fee_status,
                    allocation_status, approval_status, remarks, allocated_by, checkin_date
                )
                VALUES (?, ?, ?, ?, 'Paid', 'Active', 'Approved', ?, ?, ?);
            """, (
                old_allocation["student_id"],
                target_bed_info["id"],
                target_bed_info["room_id"],
                today_str,
                f"Transferred from Allocation #{old_allocation['id']}: {reason}",
                reviewed_by_user_id,
                today_str
            ))
            new_allocation_id = cursor.lastrowid

            # 5. Mark target bed as Occupied
            cursor.execute("UPDATE beds SET status = 'Occupied', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (target_bed_info["id"],))

            # 6. Recompute target room status
            new_occ = cursor.execute(
                "SELECT COUNT(*) FROM room_allocations WHERE room_id = ? AND allocation_status = 'Active';", (target_bed_info["room_id"],)
            ).fetchone()[0]
            new_room_status = "Full" if new_occ >= target_bed_info["capacity"] else "Partially_Occupied"
            cursor.execute("UPDATE rooms SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (new_room_status, target_bed_info["room_id"]))

            # 7. Update transfer request record if one exists
            if transfer_record_id:
                cursor.execute("""
                    UPDATE room_transfers
                    SET status = 'Approved', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, remarks = ?
                    WHERE id = ?;
                """, (reviewed_by_user_id, reason, transfer_record_id))
            else:
                cursor.execute("""
                    INSERT INTO room_transfers (allocation_id, student_id, from_bed_id, to_bed_id, reason, status, reviewed_by, reviewed_at)
                    VALUES (?, ?, ?, ?, ?, 'Approved', ?, CURRENT_TIMESTAMP);
                """, (old_allocation["id"], old_allocation["student_id"], old_allocation["bed_id"], target_bed_info["id"], reason, reviewed_by_user_id))

            # 8. Audit Log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details)
                VALUES (?, 'staff', 'TRANSFER_ROOM', 'room_allocations', ?, ?);
            """, (
                reviewed_by_user_id,
                str(new_allocation_id),
                f"Transferred student from Bed #{old_allocation['bed_id']} to Bed #{target_bed_info['id']} (Reason: {reason})"
            ))

            conn.commit()
            CacheInvalidator.on_allocation_mutation()
            logger.info(f"Poka-Yoke Atomic Transfer Completed: Allocation #{old_allocation['id']} -> Allocation #{new_allocation_id}")

        except Exception as e:
            conn.rollback()
            raise e

        return AllocationService.get_allocation_by_id(conn, new_allocation_id)

    @staticmethod
    def review_transfer_request(
        conn: sqlite3.Connection,
        transfer_id: int,
        review: TransferReview,
        reviewer_id: int
    ) -> Dict[str, Any]:
        """Approve or reject a pending student transfer request."""
        cursor = conn.cursor()
        t = cursor.execute("SELECT * FROM room_transfers WHERE id = ?;", (transfer_id,)).fetchone()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer request not found.")

        if t["status"] != "Pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Transfer request is already '{t['status']}'.")

        if review.action == "Rejected":
            cursor.execute("""
                UPDATE room_transfers
                SET status = 'Rejected', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, remarks = ?
                WHERE id = ?;
            """, (reviewer_id, review.remarks or "Rejected by administration", transfer_id))
            conn.commit()
            return {"transfer_id": transfer_id, "status": "Rejected", "message": "Transfer request rejected."}

        # Action is Approved
        alloc = cursor.execute("""
            SELECT ra.id, ra.student_id, ra.bed_id, ra.room_id, ra.allocation_status,
                   s.student_id AS enrollment, s.gender, s.first_name || ' ' || s.last_name AS student_name
            FROM room_allocations ra
            JOIN students s ON ra.student_id = s.id
            WHERE ra.id = ?;
        """, (t["allocation_id"],)).fetchone()

        target_bed = cursor.execute("""
            SELECT 
                bd.id, bd.bed_number, bd.status AS bed_status,
                r.id AS room_id, r.room_number, r.capacity, r.status AS room_status, r.is_active AS room_active,
                h.id AS hostel_id, h.name AS hostel_name, h.hostel_type, h.is_active AS hostel_active
            FROM beds bd
            JOIN rooms r ON bd.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id
            WHERE bd.id = ?;
        """, (t["to_bed_id"],)).fetchone()

        if target_bed["bed_status"] != "Available":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve transfer: Target bed #{target_bed['id']} is no longer available (Status: {target_bed['bed_status']})."
            )

        return AllocationService._execute_atomic_transfer(
            conn=conn,
            old_allocation=alloc,
            target_bed_info=target_bed,
            reason=t["reason"],
            reviewed_by_user_id=reviewer_id,
            transfer_record_id=transfer_id
        )

    @staticmethod
    def get_transfers(
        conn: sqlite3.Connection,
        status_filter: Optional[str] = None,
        student_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List room transfer requests."""
        query = """
            SELECT 
                rt.id, rt.allocation_id, rt.student_id, rt.from_bed_id, rt.to_bed_id,
                rt.reason, rt.status, rt.requested_at, rt.reviewed_by, rt.reviewed_at, rt.remarks,
                s.student_id AS student_enrollment, s.first_name || ' ' || s.last_name AS student_name,
                b_from.bed_number AS from_bed_number, r_from.room_number AS from_room_number,
                b_to.bed_number AS to_bed_number, r_to.room_number AS to_room_number
            FROM room_transfers rt
            JOIN students s ON rt.student_id = s.id
            JOIN beds b_from ON rt.from_bed_id = b_from.id
            JOIN rooms r_from ON b_from.room_id = r_from.id
            JOIN beds b_to ON rt.to_bed_id = b_to.id
            JOIN rooms r_to ON b_to.room_id = r_to.id
            WHERE 1=1
        """
        params: List[Any] = []
        if status_filter:
            query += " AND rt.status = ?"
            params.append(status_filter)
        if student_id:
            query += " AND rt.student_id = ?"
            params.append(student_id)

        query += " ORDER BY rt.id DESC;"
        cursor = conn.cursor()
        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]
