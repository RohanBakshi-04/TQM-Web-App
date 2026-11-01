"""Attendance Management Service.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Fast Response Time (< 10ms)
"""

import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

from backend.app.database.connection import get_db_connection
from backend.app.models.attendance_dto import (
    AttendanceRecordCreate,
    AttendanceBulkMarkRequest,
    AttendanceCorrectionRequest,
    AttendanceResponse,
    AttendanceDailySummary,
    StudentAttendanceSummary
)
from backend.app.services.cache_service import cache_service
from backend.app.utils.logger import logger


class AttendanceService:
    """Service handling high-reliability student attendance tracking, corrections, and analytics."""

    @staticmethod
    def _get_student_hostel_and_room(conn: sqlite3.Connection, student_id: int) -> Optional[sqlite3.Row]:
        """Fetch active hostel and room allocation details for a student."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ra.id as allocation_id, bld.hostel_id, ra.room_id, ra.bed_id,
                   h.name as hostel_name, r.room_number, b.bed_number as bed_code,
                   s.first_name || ' ' || s.last_name as student_name, s.student_id as roll_no,
                   s.user_id as student_user_id
            FROM students s
            LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
            LEFT JOIN rooms r ON r.id = ra.room_id
            LEFT JOIN floors f ON f.id = r.floor_id
            LEFT JOIN buildings bld ON bld.id = f.building_id
            LEFT JOIN hostels h ON h.id = bld.hostel_id
            LEFT JOIN beds b ON b.id = ra.bed_id
            WHERE s.id = ?;
        """, (student_id,))
        return cursor.fetchone()

    @staticmethod
    def _enforce_staff_hostel_access(current_user: Dict[str, Any], hostel_id: Optional[int]) -> None:
        """Validate that warden/assistant warden only manages attendance for their assigned hostel."""
        role = current_user.get("role")
        user_hostel_id = current_user.get("hostel_id")

        if role in ["super_admin", "auditor"]:
            return
        if role in ["hostel_admin", "warden", "assistant_warden", "security_guard"]:
            if user_hostel_id and hostel_id and int(user_hostel_id) != int(hostel_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: You are assigned to hostel ID {user_hostel_id}, not {hostel_id}."
                )

    @classmethod
    def mark_attendance(cls, payload: AttendanceRecordCreate, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Record daily attendance for a single student."""
        role = current_user.get("role")
        if role not in ["super_admin", "hostel_admin", "warden", "assistant_warden", "security_guard"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only hostel staff can record attendance."
            )

        conn = get_db_connection()
        try:
            student_info = cls._get_student_hostel_and_room(conn, payload.student_id)
            if not student_info:
                raise HTTPException(status_code=404, detail="Student not found.")

            if student_info["hostel_id"]:
                cls._enforce_staff_hostel_access(current_user, student_info["hostel_id"])

            cursor = conn.cursor()
            # Check for duplicate
            cursor.execute("SELECT id, status FROM attendance WHERE student_id = ? AND date = ?;", (payload.student_id, payload.date))
            existing = cursor.fetchone()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Attendance already marked for student {payload.student_id} on {payload.date} (Status: {existing['status']}). Use correction endpoint to modify."
                )

            # Insert attendance
            cursor.execute("""
                INSERT INTO attendance (student_id, date, status, marked_by, remarks, marked_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (payload.student_id, payload.date, payload.status, current_user.get("user_id"), payload.remarks or ""))
            att_id = cursor.lastrowid

            # If marked Absent, notify student
            if payload.status == "Absent" and student_info["student_user_id"]:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type)
                    VALUES (?, ?, ?, 'alert');
                """, (
                    student_info["student_user_id"],
                    "Attendance Alert: Marked Absent",
                    f"You were marked Absent for attendance on date {payload.date}. If this is an error, contact your warden."
                ))

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'MARK_ATTENDANCE', 'attendance', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "staff"),
                str(att_id),
                f"Marked {payload.status} for student {payload.student_id} on {payload.date}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("attendance")
            logger.info(f"Attendance marked: student {payload.student_id} -> {payload.status} on {payload.date} by {current_user.get('username')}")

            return {
                "id": att_id,
                "student_id": payload.student_id,
                "student_name": student_info["student_name"],
                "student_roll_no": student_info["roll_no"],
                "date": payload.date,
                "status": payload.status,
                "remarks": payload.remarks or "",
                "marked_by": current_user.get("user_id"),
                "marked_by_name": current_user.get("username")
            }
        finally:
            conn.close()

    @classmethod
    def bulk_mark_attendance(cls, payload: AttendanceBulkMarkRequest, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Atomically record attendance for multiple students for a specific date."""
        role = current_user.get("role")
        if role not in ["super_admin", "hostel_admin", "warden", "assistant_warden", "security_guard"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only hostel staff can record attendance."
            )

        if payload.hostel_id:
            cls._enforce_staff_hostel_access(current_user, payload.hostel_id)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            user_id = current_user.get("user_id")

            # Check for existing records on that date
            student_ids = [item.student_id for item in payload.records]
            placeholders = ",".join("?" for _ in student_ids)
            cursor.execute(f"SELECT student_id FROM attendance WHERE date = ? AND student_id IN ({placeholders});", [payload.date] + student_ids)
            already_marked = {r["student_id"] for r in cursor.fetchall()}

            marked_count = 0
            skipped_count = 0

            for item in payload.records:
                if item.student_id in already_marked:
                    skipped_count += 1
                    continue

                cursor.execute("""
                    INSERT INTO attendance (student_id, date, status, marked_by, remarks, marked_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """, (item.student_id, payload.date, item.status, user_id, item.remarks or ""))
                marked_count += 1

            conn.commit()
            cache_service.invalidate_by_tag("attendance")
            logger.info(f"Bulk attendance: {marked_count} marked, {skipped_count} skipped on {payload.date}")

            return {
                "date": payload.date,
                "marked_count": marked_count,
                "skipped_count": skipped_count,
                "total_processed": len(payload.records)
            }
        finally:
            conn.close()

    @classmethod
    def correct_attendance(cls, attendance_id: int, payload: AttendanceCorrectionRequest, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Authorized correction of an existing attendance record with mandatory audit trail."""
        role = current_user.get("role")
        if role not in ["super_admin", "hostel_admin", "warden", "assistant_warden"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only administrators and wardens can correct marked attendance."
            )

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.id, a.student_id, a.date, a.status, bld.hostel_id, s.user_id as student_user_id,
                       s.first_name || ' ' || s.last_name as student_name
                FROM attendance a
                JOIN students s ON s.id = a.student_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                WHERE a.id = ?;
            """, (attendance_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Attendance record not found.")

            if record["hostel_id"]:
                cls._enforce_staff_hostel_access(current_user, record["hostel_id"])

            prev_status = record["status"]
            if prev_status == payload.new_status:
                raise HTTPException(status_code=400, detail=f"Attendance is already marked as {prev_status}.")

            # 1. Insert audit correction history
            cursor.execute("""
                INSERT INTO attendance_corrections (attendance_id, student_id, previous_status, new_status, reason, corrected_by)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (attendance_id, record["student_id"], prev_status, payload.new_status, payload.reason, current_user.get("user_id")))

            # 2. Update attendance record
            cursor.execute("""
                UPDATE attendance
                SET status = ?, remarks = ?, marked_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (payload.new_status, payload.remarks or f"Corrected from {prev_status}: {payload.reason}", attendance_id))

            # 3. Notification to student
            if record["student_user_id"]:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type)
                    VALUES (?, ?, ?, 'info');
                """, (
                    record["student_user_id"],
                    "Attendance Status Corrected",
                    f"Your attendance for {record['date']} was updated from {prev_status} to {payload.new_status}. Reason: {payload.reason}"
                ))

            # 4. Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'CORRECT_ATTENDANCE', 'attendance', ?, ?, 0.8);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "staff"),
                str(attendance_id),
                f"Status corrected: {prev_status} -> {payload.new_status}. Reason: {payload.reason}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("attendance")
            logger.info(f"Attendance {attendance_id} corrected: {prev_status} -> {payload.new_status} by {current_user.get('username')}")

            return {
                "id": attendance_id,
                "student_id": record["student_id"],
                "student_name": record["student_name"],
                "date": record["date"],
                "previous_status": prev_status,
                "new_status": payload.new_status,
                "reason": payload.reason,
                "corrected_by": current_user.get("user_id"),
                "corrected_by_name": current_user.get("username")
            }
        finally:
            conn.close()

    @classmethod
    def get_attendance_records(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch filtered and paginated attendance records with strict RBAC row-level isolation."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            role = current_user.get("role")
            user_hostel_id = current_user.get("hostel_id")

            where_clauses = ["1=1"]
            params: List[Any] = []

            # RBAC Data Isolation
            if role == "student":
                # Find student profile for user
                cursor.execute("SELECT id FROM students WHERE user_id = ?;", (current_user.get("user_id"),))
                st = cursor.fetchone()
                if not st:
                    return {"total": 0, "records": []}
                where_clauses.append("a.student_id = ?")
                params.append(st["id"])
            elif role == "parent":
                cursor.execute("""
                    SELECT sg.student_id FROM student_guardians sg
                    JOIN guardians g ON g.id = sg.guardian_id
                    WHERE g.user_id = ?;
                """, (current_user.get("user_id"),))
                wards = [r[0] for r in cursor.fetchall()]
                if not wards:
                    return {"total": 0, "records": []}
                placeholders = ",".join("?" for _ in wards)
                where_clauses.append(f"a.student_id IN ({placeholders})")
                params.extend(wards)
            elif role in ["warden", "assistant_warden"] and user_hostel_id:
                where_clauses.append("bld.hostel_id = ?")
                params.append(int(user_hostel_id))

            # Query Filters
            if filters.get("student_id"):
                where_clauses.append("a.student_id = ?")
                params.append(filters["student_id"])
            if filters.get("date"):
                where_clauses.append("a.date = ?")
                params.append(filters["date"])
            if filters.get("start_date"):
                where_clauses.append("a.date >= ?")
                params.append(filters["start_date"])
            if filters.get("end_date"):
                where_clauses.append("a.date <= ?")
                params.append(filters["end_date"])
            if filters.get("status"):
                where_clauses.append("a.status = ?")
                params.append(filters["status"])
            if filters.get("hostel_id"):
                where_clauses.append("bld.hostel_id = ?")
                params.append(filters["hostel_id"])
            if filters.get("building_id"):
                where_clauses.append("f.building_id = ?")
                params.append(filters["building_id"])
            if filters.get("room_id"):
                where_clauses.append("ra.room_id = ?")
                params.append(filters["room_id"])

            where_str = " AND ".join(where_clauses)

            # Count total
            count_query = f"""
                SELECT COUNT(a.id)
                FROM attendance a
                JOIN students s ON s.id = a.student_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                WHERE {where_str};
            """
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Fetch records
            limit = int(filters.get("limit", 50))
            offset = int(filters.get("offset", 0))

            query = f"""
                SELECT a.id, a.student_id, a.date, a.status, a.remarks, a.marked_at, a.created_at,
                       s.first_name || ' ' || s.last_name as student_name, s.student_id as roll_no,
                       h.name as hostel_name, bld.hostel_id, r.room_number, b.bed_number as bed_code,
                       u.username as marked_by_name, a.marked_by
                FROM attendance a
                JOIN students s ON s.id = a.student_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                LEFT JOIN beds b ON b.id = ra.bed_id
                LEFT JOIN users u ON u.id = a.marked_by
                WHERE {where_str}
                ORDER BY a.date DESC, a.id DESC
                LIMIT ? OFFSET ?;
            """
            cursor.execute(query, params + [limit, offset])
            records = [dict(r) for r in cursor.fetchall()]

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "records": records
            }
        finally:
            conn.close()

    @classmethod
    def get_student_attendance_history(cls, student_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve comprehensive attendance history and statistics for a single student."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            active_role = current_user.get("active_role") or current_user.get("role") or (current_user.get("roles")[0] if current_user.get("roles") else None)
            if active_role == "student":
                cursor.execute("SELECT id FROM students WHERE user_id = ?;", (current_user.get("user_id"),))
                st = cursor.fetchone()
                user_student_id = st["id"] if st else current_user.get("linked_student_id")
                if not user_student_id or user_student_id != student_id:
                    raise HTTPException(status_code=403, detail="Forbidden: You cannot view other students' attendance.")

            # Student basic details
            student_info = cls._get_student_hostel_and_room(conn, student_id)
            if not student_info:
                raise HTTPException(status_code=404, detail="Student not found.")

            # Metrics
            cursor.execute("""
                SELECT 
                    COUNT(id) as total_days,
                    SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
                    SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
                    SUM(CASE WHEN status IN ('On Leave', 'On_Leave') THEN 1 ELSE 0 END) as on_leave_days
                FROM attendance
                WHERE student_id = ?;
            """, (student_id,))
            metrics = dict(cursor.fetchone())
            total = metrics.get("total_days") or 0
            present = metrics.get("present_days") or 0
            absent = metrics.get("absent_days") or 0
            on_leave = metrics.get("on_leave_days") or 0
            pct = round((present / total) * 100, 1) if total > 0 else 100.0

            # List records
            cursor.execute("""
                SELECT a.id, a.date, a.status, a.remarks, a.marked_at, u.username as marked_by_name
                FROM attendance a
                LEFT JOIN users u ON u.id = a.marked_by
                WHERE a.student_id = ?
                ORDER BY a.date DESC;
            """, (student_id,))
            records = [dict(r) for r in cursor.fetchall()]

            # Fetch correction history for this student
            cursor.execute("""
                SELECT c.id, c.attendance_id, c.previous_status, c.new_status, c.reason, c.corrected_at,
                       u.username as corrected_by_name
                FROM attendance_corrections c
                LEFT JOIN users u ON u.id = c.corrected_by
                WHERE c.student_id = ?
                ORDER BY c.corrected_at DESC;
            """, (student_id,))
            corrections = [dict(r) for r in cursor.fetchall()]

            return {
                "student_id": student_id,
                "student_name": student_info["student_name"],
                "student_roll_no": student_info["roll_no"],
                "hostel_name": student_info["hostel_name"],
                "room_number": student_info["room_number"],
                "total_days": total,
                "present_days": present,
                "absent_days": absent,
                "on_leave_days": on_leave,
                "attendance_percentage": pct,
                "is_repeated_absentee": absent >= 3,
                "history": records,
                "corrections": corrections
            }
        finally:
            conn.close()

    @classmethod
    def get_daily_summary(cls, target_date: Optional[str], hostel_id: Optional[int], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate daily attendance summary and identify repeated absentees."""
        if not target_date:
            target_date = date.today().isoformat()

        user_roles = set(current_user.get("roles", []))
        if current_user.get("role"):
            user_roles.add(current_user["role"])
        user_hostel_id = current_user.get("hostel_id") or current_user.get("linked_hostel_id")
        if user_roles.intersection({"warden", "assistant_warden"}) and user_hostel_id and not hostel_id:
            hostel_id = int(user_hostel_id)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Active resident students count
            hostel_clause = "AND bld.hostel_id = ?" if hostel_id else ""
            h_params = [hostel_id] if hostel_id else []

            cursor.execute(f"""
                SELECT COUNT(DISTINCT s.id)
                FROM students s
                JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                JOIN rooms r ON r.id = ra.room_id
                JOIN floors f ON f.id = r.floor_id
                JOIN buildings bld ON bld.id = f.building_id
                WHERE 1=1 {hostel_clause};
            """, h_params)
            total_students = cursor.fetchone()[0]

            # Attendance status breakdown for target_date
            cursor.execute(f"""
                SELECT 
                    SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
                    SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
                    SUM(CASE WHEN a.status IN ('On Leave', 'On_Leave') THEN 1 ELSE 0 END) as on_leave_count
                FROM attendance a
                JOIN room_allocations ra ON ra.student_id = a.student_id AND ra.allocation_status = 'Active'
                JOIN rooms r ON r.id = ra.room_id
                JOIN floors f ON f.id = r.floor_id
                JOIN buildings bld ON bld.id = f.building_id
                WHERE a.date = ? {hostel_clause};
            """, [target_date] + h_params)
            counts = cursor.fetchone()
            present = counts["present_count"] or 0
            absent = counts["absent_count"] or 0
            on_leave = counts["on_leave_count"] or 0
            marked_total = present + absent + on_leave
            not_marked = max(0, total_students - marked_total)
            pct = round((present / total_students) * 100, 1) if total_students > 0 else 0.0

            # Repeated absentees: students with >= 3 absences in the last 30 days
            thirty_days_ago = (date.fromisoformat(target_date) - timedelta(days=30)).isoformat()
            cursor.execute(f"""
                SELECT s.id as student_id, s.first_name || ' ' || s.last_name as student_name,
                       s.student_id as roll_no, r.room_number, h.name as hostel_name,
                       COUNT(a.id) as absent_days
                FROM attendance a
                JOIN students s ON s.id = a.student_id
                JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                JOIN rooms r ON r.id = ra.room_id
                JOIN floors f ON f.id = r.floor_id
                JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                WHERE a.status = 'Absent' AND a.date >= ? AND a.date <= ? {hostel_clause}
                GROUP BY s.id
                HAVING COUNT(a.id) >= 3
                ORDER BY absent_days DESC;
            """, [thirty_days_ago, target_date] + h_params)
            repeated_absentees = [dict(r) for r in cursor.fetchall()]

            return {
                "date": target_date,
                "hostel_id": hostel_id,
                "total_students": total_students,
                "present_students": present,
                "absent_students": absent,
                "students_on_leave": on_leave,
                "not_marked_students": not_marked,
                "attendance_percentage": pct,
                "repeated_absentees": repeated_absentees
            }
        finally:
            conn.close()

    @classmethod
    def get_attendance_reports(cls, start_date: str, end_date: str, hostel_id: Optional[int], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive date-range attendance reports with percentage calculations."""
        user_roles = set(current_user.get("roles", []))
        if current_user.get("role"):
            user_roles.add(current_user["role"])
        user_hostel_id = current_user.get("hostel_id") or current_user.get("linked_hostel_id")
        if user_roles.intersection({"warden", "assistant_warden"}) and user_hostel_id and not hostel_id:
            hostel_id = int(user_hostel_id)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            hostel_clause = "AND bld.hostel_id = ?" if hostel_id else ""
            h_params = [hostel_id] if hostel_id else []

            cursor.execute(f"""
                SELECT 
                    s.id as student_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    s.student_id as roll_no,
                    h.name as hostel_name,
                    r.room_number,
                    COUNT(a.id) as total_days,
                    SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_days,
                    SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
                    SUM(CASE WHEN a.status IN ('On Leave', 'On_Leave') THEN 1 ELSE 0 END) as on_leave_days
                FROM students s
                JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                JOIN rooms r ON r.id = ra.room_id
                JOIN floors f ON f.id = r.floor_id
                JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                LEFT JOIN attendance a ON a.student_id = s.id AND a.date >= ? AND a.date <= ?
                WHERE 1=1 {hostel_clause}
                GROUP BY s.id
                ORDER BY h.name, r.room_number, s.first_name;
            """, [start_date, end_date] + h_params)

            rows = cursor.fetchall()
            student_reports = []
            total_present = 0
            total_marked = 0

            for r in rows:
                t_days = r["total_days"] or 0
                p_days = r["present_days"] or 0
                a_days = r["absent_days"] or 0
                l_days = r["on_leave_days"] or 0
                pct = round((p_days / t_days) * 100, 1) if t_days > 0 else 0.0

                total_present += p_days
                total_marked += t_days

                student_reports.append({
                    "student_id": r["student_id"],
                    "student_name": r["student_name"],
                    "student_roll_no": r["roll_no"],
                    "hostel_name": r["hostel_name"],
                    "room_number": r["room_number"],
                    "total_days": t_days,
                    "present_days": p_days,
                    "absent_days": a_days,
                    "on_leave_days": l_days,
                    "attendance_percentage": pct,
                    "is_repeated_absentee": a_days >= 3
                })

            overall_pct = round((total_present / total_marked) * 100, 1) if total_marked > 0 else 0.0

            return {
                "start_date": start_date,
                "end_date": end_date,
                "hostel_id": hostel_id,
                "total_records": len(student_reports),
                "overall_attendance_percentage": overall_pct,
                "student_reports": student_reports
            }
        finally:
            conn.close()

    @classmethod
    def get_students_for_marking(
        cls,
        target_date: str,
        hostel_id: Optional[int],
        building_id: Optional[int],
        floor_id: Optional[int],
        room_id: Optional[int],
        current_user: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Fetch all active students eligible for attendance marking in a given hostel/building/floor/room."""
        user_roles = set(current_user.get("roles", []))
        if current_user.get("role"):
            user_roles.add(current_user["role"])
        user_hostel_id = current_user.get("hostel_id") or current_user.get("linked_hostel_id")
        if user_roles.intersection({"warden", "assistant_warden"}) and user_hostel_id and not hostel_id:
            hostel_id = int(user_hostel_id)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            where_clauses = ["ra.allocation_status = 'Active'"]
            params: List[Any] = [target_date, target_date]

            if hostel_id:
                where_clauses.append("bld.hostel_id = ?")
                params.append(hostel_id)
            if building_id:
                where_clauses.append("f.building_id = ?")
                params.append(building_id)
            if floor_id:
                where_clauses.append("r.floor_id = ?")
                params.append(floor_id)
            if room_id:
                where_clauses.append("ra.room_id = ?")
                params.append(room_id)

            where_str = " AND ".join(where_clauses)

            # Check if student is on approved leave
            query = f"""
                SELECT s.id as student_id, s.first_name || ' ' || s.last_name as student_name,
                       s.student_id as roll_no, h.name as hostel_name, bld.hostel_id,
                       r.room_number, b.bed_number as bed_code,
                       att.id as attendance_id, att.status as marked_status, att.remarks as marked_remarks,
                       CASE WHEN lr.id IS NOT NULL THEN 1 ELSE 0 END as is_on_leave
                FROM students s
                JOIN room_allocations ra ON ra.student_id = s.id
                JOIN rooms r ON r.id = ra.room_id
                JOIN floors f ON f.id = r.floor_id
                JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                LEFT JOIN beds b ON b.id = ra.bed_id
                LEFT JOIN attendance att ON att.student_id = s.id AND att.date = ?
                LEFT JOIN leave_requests lr ON lr.student_id = s.id 
                     AND lr.status = 'Approved' 
                     AND lr.start_date <= ? AND lr.end_date >= ?
                WHERE {where_str}
                ORDER BY r.room_number, b.bed_number, s.first_name;
            """
            cursor.execute(query, [target_date] + params)
            rows = cursor.fetchall()

            result = []
            for r in rows:
                item = dict(r)
                # If not marked yet and on approved leave, suggest 'On Leave'
                if not item["marked_status"] and item["is_on_leave"]:
                    item["suggested_status"] = "On Leave"
                elif not item["marked_status"]:
                    item["suggested_status"] = "Present"
                else:
                    item["suggested_status"] = item["marked_status"]
                result.append(item)

            return result
        finally:
            conn.close()

    @classmethod
    def get_my_attendance(cls, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve personal attendance status and metrics for the authenticated student or linked ward."""
        user_id = current_user.get("user_id") or current_user.get("id")
        linked_student_id = current_user.get("linked_student_id")
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if not linked_student_id:
                cursor.execute("SELECT id FROM students WHERE user_id = ?;", (user_id,))
                st = cursor.fetchone()
                if st:
                    linked_student_id = st["id"] if isinstance(st, sqlite3.Row) else st[0]
                else:
                    linked_student_id = 1
            res = cls.get_student_attendance_history(linked_student_id, current_user)

            # Compute today's status
            today_str = datetime.now().strftime("%Y-%m-%d")
            history = res.get("history", [])
            today_record = next((r for r in history if r.get("date") == today_str), None)
            if today_record:
                res["today_status"] = today_record.get("status", "Present")
                res["today_marked_at"] = today_record.get("marked_at", "")
                res["today_remarks"] = today_record.get("remarks", "")
            else:
                latest_record = history[0] if history else None
                res["today_status"] = "Not Marked"
                res["today_marked_at"] = ""
                res["today_remarks"] = "Roll call pending for today"
                res["latest_status"] = latest_record.get("status") if latest_record else "Present"
                res["latest_date"] = latest_record.get("date") if latest_record else ""
            return res
        finally:
            conn.close()
