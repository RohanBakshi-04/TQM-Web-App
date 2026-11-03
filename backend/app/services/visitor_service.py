"""Visitor Management Service.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Fast Response Time (< 10ms)
"""

import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

from backend.app.database.connection import get_db_connection
from backend.app.services.auth_dependencies import get_parent_authorized_ward_ids, verify_student_isolation
from backend.app.models.visitor_dto import (
    VisitorRegistrationRequest,
    VisitorApprovalRequest,
    VisitorRejectionRequest,
    VisitorCheckInRequest,
    VisitorCheckOutRequest,
    VisitorResponse
)
from backend.app.services.cache_service import cache_service
from backend.app.utils.logger import logger


class VisitorService:
    """Service handling campus visitor registration, warden approvals, security ingress/egress, and overdue tracking."""

    @staticmethod
    def _mask_id_proof(id_proof_number: str) -> str:
        """Securely mask sensitive identification numbers for privacy protection."""
        if not id_proof_number:
            return ""
        if len(id_proof_number) <= 4:
            return "****"
        return "X" * (len(id_proof_number) - 4) + id_proof_number[-4:]

    @staticmethod
    def _mask_phone(phone: str) -> str:
        """Securely mask phone numbers for privacy protection."""
        if not phone:
            return ""
        p = str(phone).strip()
        if len(p) <= 4:
            return "****"
        return "*" * (len(p) - 4) + p[-4:]

    @classmethod
    def register_visitor(cls, payload: VisitorRegistrationRequest, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Register a visitor and log their visit pass, preventing active duplicate entries."""
        role = current_user.get("role") or current_user.get("active_role")
        user_roles = set(current_user.get("roles", []))
        if role not in ["security_guard", "super_admin", "hostel_admin", "warden", "assistant_warden"] and not user_roles.intersection({"super_admin", "hostel_admin", "security_guard", "warden", "assistant_warden"}):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only security guards and hostel staff can register visitors."
            )

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # 1. Prevent duplicate active visit for the same visitor contact number
            cursor.execute("""
                SELECT vl.id, vl.pass_number, vl.check_in_time
                FROM visitor_logs vl
                JOIN visitors v ON v.id = vl.visitor_id
                WHERE v.phone = ? AND vl.check_in_time IS NOT NULL AND vl.check_out_time IS NULL;
            """, (payload.phone,))
            active_visit = cursor.fetchone()
            if active_visit:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Active Visit Conflict: Visitor with phone {payload.phone} is currently checked in under Pass #{active_visit['pass_number']} (Entry: {active_visit['check_in_time']}). Check out first."
                )

            # 2. Get or create master visitor record
            cursor.execute("SELECT id FROM visitors WHERE phone = ?;", (payload.phone,))
            v_row = cursor.fetchone()
            if v_row:
                visitor_id = v_row["id"]
                # Update details if needed
                cursor.execute("""
                    UPDATE visitors SET name = ?, id_proof_type = ?, id_proof_number = ?, address = ?
                    WHERE id = ?;
                """, (payload.name, payload.id_proof_type, payload.id_proof_number, payload.address or "", visitor_id))
            else:
                cursor.execute("""
                    INSERT INTO visitors (name, phone, id_proof_type, id_proof_number, address)
                    VALUES (?, ?, ?, ?, ?);
                """, (payload.name, payload.phone, payload.id_proof_type, payload.id_proof_number, payload.address or ""))
                visitor_id = cursor.lastrowid

            # 3. Resolve student allocation details
            cursor.execute("""
                SELECT s.id as student_id, s.user_id as student_user_id, s.first_name || ' ' || s.last_name as student_name,
                       bld.hostel_id, ra.room_id, h.name as hostel_name, r.room_number
                FROM students s
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                WHERE s.student_id = ? OR CAST(s.id AS TEXT) = ?;
            """, (str(payload.student_id).strip(), str(payload.student_id).strip()))
            student_info = cursor.fetchone()
            if not student_info:
                raise HTTPException(status_code=404, detail="Resident student not found.")

            hostel_id = payload.hostel_id or student_info["hostel_id"]
            room_id = payload.room_id or student_info["room_id"]

            # 4. Generate unique pass number: VP-YYYYMM-XXXX
            today_prefix = date.today().strftime("%Y%m")
            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM visitor_logs;")
            seq = cursor.fetchone()[0] or 1
            while True:
                candidate_pass = f"VP-{today_prefix}-{seq:04d}"
                cursor.execute("SELECT 1 FROM visitor_logs WHERE pass_number = ?;", (candidate_pass,))
                if not cursor.fetchone():
                    pass_number = candidate_pass
                    break
                seq += 1

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            expected_exit = payload.expected_exit_time or (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")

            if payload.immediate_checkin:
                check_in_time = now_str
                initial_status = "Checked_In"
                approval_status = "Approved"
            else:
                check_in_time = None
                initial_status = "Pending"
                approval_status = "Pending"

            # 5. Insert visitor log
            cursor.execute("""
                INSERT INTO visitor_logs (
                    pass_number, visitor_id, student_id, hostel_id, room_id,
                    check_in_time, expected_exit_time, purpose, approval_status,
                    status, approved_by, remarks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                pass_number, visitor_id, student_info['student_id'], hostel_id, room_id,
                check_in_time, expected_exit, payload.purpose, approval_status,
                initial_status, current_user.get("user_id"), payload.address or ""
            ))
            log_id = cursor.lastrowid

            # 6. Notify student
            if student_info["student_user_id"]:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type)
                    VALUES (?, ?, ?, 'info');
                """, (
                    student_info["student_user_id"],
                    "Visitor Arrival Notification",
                    f"{payload.name} ({payload.purpose}) has registered at the campus gate to visit you. Pass #{pass_number}."
                ))

            # 7. Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'REGISTER_VISITOR', 'visitor_logs', ?, ?, 0.6);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "security"),
                str(log_id),
                f"Registered visitor {payload.name} for student {payload.student_id}. Pass #{pass_number}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("visitors")
            logger.info(f"Visitor registered: {payload.name} -> Student {payload.student_id} under Pass {pass_number}")

            return cls.get_visitor_log(log_id, current_user)
        finally:
            conn.close()

    @classmethod
    def get_visitor_log(cls, log_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch details of a single visitor entry pass, masking identity proof for unauthorized users."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT vl.*, v.name, v.phone, v.id_proof_type, v.id_proof_number,
                       s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       s.user_id as student_user_id, h.name as hostel_name, r.room_number,
                       u.username as approved_by_name
                FROM visitor_logs vl
                JOIN visitors v ON v.id = vl.visitor_id
                JOIN students s ON s.id = vl.student_id
                LEFT JOIN hostels h ON h.id = vl.hostel_id
                LEFT JOIN rooms r ON r.id = vl.room_id
                LEFT JOIN users u ON u.id = vl.approved_by
                WHERE vl.id = ?;
            """, (log_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Visitor pass not found.")

            res = dict(record)
            active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()

            # Strict Active-Role Scoping
            if active_role == "student":
                my_sid = current_user.get("linked_student_id")
                if res.get("student_id") != my_sid and res.get("student_user_id") != current_user.get("user_id"):
                    raise HTTPException(status_code=403, detail="Forbidden: You cannot view other students' visitors.")
            elif active_role in ("parent_guardian", "parent"):
                wards = get_parent_authorized_ward_ids(conn, current_user)
                if res.get("student_id") not in wards:
                    raise HTTPException(status_code=403, detail="Forbidden: You cannot view visitors of unlinked students.")
            elif active_role in ("warden", "assistant_warden"):
                linked_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
                if not linked_hid:
                    raise HTTPException(status_code=403, detail="Access Denied: Staff member has no assigned hostel facility.")
                if not res.get("hostel_id") or int(res["hostel_id"]) != int(linked_hid):
                    raise HTTPException(status_code=403, detail="Forbidden: Visitor pass belongs to another hostel facility.")
            elif active_role not in ("security_guard", "super_admin", "hostel_admin"):
                raise HTTPException(status_code=403, detail="Forbidden: Unauthorized active role for visitor log access.")

            # Overdue calculation
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if res["status"] == "Checked_In" and not res["check_out_time"] and res["expected_exit_time"]:
                res["is_overdue"] = res["expected_exit_time"] < now_str
            else:
                res["is_overdue"] = res["status"] == "Overdue"

            # Privacy masking for resident and parent queries
            if active_role in ["student", "parent", "parent_guardian"]:
                res["id_proof_number"] = cls._mask_id_proof(res.get("id_proof_number", ""))
                res["phone"] = cls._mask_phone(res.get("phone", ""))

            return res
        finally:
            conn.close()

    @classmethod
    def approve_visitor(cls, log_id: int, payload: VisitorApprovalRequest, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Warden approval for a pending visitor entry request."""
        role = current_user.get("role")
        if role not in ["super_admin", "hostel_admin", "warden", "assistant_warden"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only hostel wardens and administrators can approve visitor entry requests."
            )

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM visitor_logs WHERE id = ?;", (log_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Visitor pass not found.")

            cursor.execute("""
                UPDATE visitor_logs
                SET approval_status = 'Approved', status = 'Approved', approved_by = ?, remarks = ?
                WHERE id = ?;
            """, (current_user.get("user_id"), payload.remarks or "Approved by Warden", log_id))

            conn.commit()
            cache_service.invalidate_by_tag("visitors")
            logger.info(f"Visitor pass #{log_id} approved by user {current_user.get('user_id')}")

            return cls.get_visitor_log(log_id, current_user)
        finally:
            conn.close()

    @classmethod
    def reject_visitor(cls, log_id: int, payload: VisitorRejectionRequest, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Reject a visitor pass with mandatory justification reason."""
        role = current_user.get("role")
        if role not in ["super_admin", "hostel_admin", "warden", "assistant_warden"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only hostel wardens and administrators can reject visitor entry requests."
            )

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM visitor_logs WHERE id = ?;", (log_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Visitor pass not found.")

            if record["status"] in ["Checked_In", "Checked_Out"]:
                raise HTTPException(status_code=400, detail=f"Cannot reject visitor in '{record['status']}' state.")

            cursor.execute("""
                UPDATE visitor_logs
                SET approval_status = 'Rejected', status = 'Rejected', rejection_reason = ?, approved_by = ?
                WHERE id = ?;
            """, (payload.reason, current_user.get("user_id"), log_id))

            conn.commit()
            cache_service.invalidate_by_tag("visitors")
            logger.info(f"Visitor pass #{log_id} rejected by user {current_user.get('user_id')}. Reason: {payload.reason}")

            return cls.get_visitor_log(log_id, current_user)
        finally:
            conn.close()

    @classmethod
    def check_in_visitor(cls, log_id: int, payload: VisitorCheckInRequest, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Log visitor ingress into hostel campus."""
        role = current_user.get("role") or current_user.get("active_role")
        user_roles = set(current_user.get("roles", []))
        if role not in ["security_guard", "super_admin", "hostel_admin", "warden", "assistant_warden"] and not user_roles.intersection({"super_admin", "hostel_admin", "security_guard", "warden", "assistant_warden"}):
            raise HTTPException(status_code=403, detail="Unauthorized: Only security guards and authorized staff can log check-ins.")

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM visitor_logs WHERE id = ?;", (log_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Visitor pass not found.")

            if record["check_in_time"] is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate Ingress Error: Visitor was already checked in at {record['check_in_time']}."
                )

            if record["approval_status"] == "Rejected":
                raise HTTPException(status_code=400, detail="Cannot check in: Visitor pass has been Rejected.")

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updates = ["check_in_time = ?", "status = 'Checked_In'"]
            params = [now_str]

            if payload.expected_exit_time:
                updates.append("expected_exit_time = ?")
                params.append(payload.expected_exit_time)
            if payload.remarks:
                updates.append("remarks = ?")
                params.append(payload.remarks)

            cursor.execute(f"UPDATE visitor_logs SET {', '.join(updates)} WHERE id = ?;", params + [log_id])

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'VISITOR_CHECK_IN', 'visitor_logs', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "guard"),
                str(log_id),
                f"Logged check-in for visitor pass #{record['pass_number']}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("visitors")
            logger.info(f"Visitor pass #{log_id} checked in by {current_user.get('username')}")

            return cls.get_visitor_log(log_id, current_user)
        finally:
            conn.close()

    @classmethod
    def check_out_visitor(cls, log_id: int, payload: VisitorCheckOutRequest, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Log visitor departure and campus egress."""
        role = current_user.get("role") or current_user.get("active_role")
        user_roles = set(current_user.get("roles", []))
        if role not in ["security_guard", "super_admin", "hostel_admin", "warden", "assistant_warden"] and not user_roles.intersection({"super_admin", "hostel_admin", "security_guard", "warden", "assistant_warden"}):
            raise HTTPException(status_code=403, detail="Unauthorized: Only security guards and authorized staff can log check-outs.")

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM visitor_logs WHERE id = ?;", (log_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Visitor pass not found.")

            if record["check_in_time"] is None:
                raise HTTPException(status_code=400, detail="Cannot check out: Visitor was never checked in.")

            if record["check_out_time"] is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate Egress Error: Visitor was already checked out at {record['check_out_time']}."
                )

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                UPDATE visitor_logs
                SET check_out_time = ?, status = 'Checked_Out', remarks = ?
                WHERE id = ?;
            """, (now_str, payload.remarks or record["remarks"] or "", log_id))

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'VISITOR_CHECK_OUT', 'visitor_logs', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "guard"),
                str(log_id),
                f"Logged check-out for visitor pass #{record['pass_number']}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("visitors")
            logger.info(f"Visitor pass #{log_id} checked out by {current_user.get('username')}")

            return cls.get_visitor_log(log_id, current_user)
        finally:
            conn.close()

    @classmethod
    def get_active_visitors(cls, hostel_id: Optional[int], current_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List all visitors currently on campus premises (checked in without check out)."""
        active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()
        linked_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")

        if active_role in ("warden", "assistant_warden"):
            if not linked_hid:
                return []
            hostel_id = int(linked_hid)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            where_clauses = ["vl.check_in_time IS NOT NULL", "vl.check_out_time IS NULL"]
            params: List[Any] = []

            if hostel_id:
                where_clauses.append("vl.hostel_id = ?")
                params.append(hostel_id)

            if active_role == "student":
                my_sid = current_user.get("linked_student_id")
                if not my_sid:
                    cursor.execute("SELECT id FROM students WHERE user_id = ?;", (current_user.get("user_id"),))
                    st = cursor.fetchone()
                    my_sid = st["id"] if st else None
                if not my_sid:
                    return []
                where_clauses.append("vl.student_id = ?")
                params.append(my_sid)
            elif active_role in ("parent_guardian", "parent"):
                wards = get_parent_authorized_ward_ids(conn, current_user)
                if not wards:
                    return []
                where_clauses.append(f"vl.student_id IN ({','.join('?' for _ in wards)})")
                params.extend(wards)

            where_str = " AND ".join(where_clauses)
            query = f"""
                SELECT vl.*, v.name, v.phone, v.id_proof_type, v.id_proof_number,
                       s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       h.name as hostel_name, r.room_number
                FROM visitor_logs vl
                JOIN visitors v ON v.id = vl.visitor_id
                JOIN students s ON s.id = vl.student_id
                LEFT JOIN hostels h ON h.id = vl.hostel_id
                LEFT JOIN rooms r ON r.id = vl.room_id
                WHERE {where_str}
                ORDER BY vl.check_in_time DESC;
            """
            cursor.execute(query, params)
            rows = cursor.fetchall()

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            records = []
            for r in rows:
                item = dict(r)
                if item["expected_exit_time"] and item["expected_exit_time"] < now_str:
                    item["is_overdue"] = True
                else:
                    item["is_overdue"] = False

                active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()
                if active_role in ["student", "parent", "parent_guardian"]:
                    item["id_proof_number"] = cls._mask_id_proof(item.get("id_proof_number", ""))
                    item["phone"] = cls._mask_phone(item.get("phone", ""))
                records.append(item)

            return records
        finally:
            conn.close()

    @classmethod
    def get_visitor_logs(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch filtered and paginated visitor history logs with RBAC isolation and privacy masking."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()
            linked_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")

            where_clauses = ["1=1"]
            params: List[Any] = []

            # Active-Role RBAC Isolation
            if active_role == "student":
                my_sid = current_user.get("linked_student_id")
                if not my_sid:
                    cursor.execute("SELECT id FROM students WHERE user_id = ?;", (current_user.get("user_id"),))
                    st = cursor.fetchone()
                    my_sid = st["id"] if st else None
                if not my_sid:
                    return {"total": 0, "records": []}
                where_clauses.append("vl.student_id = ?")
                params.append(my_sid)
            elif active_role in ("parent_guardian", "parent"):
                wards = get_parent_authorized_ward_ids(conn, current_user)
                if not wards:
                    return {"total": 0, "records": []}
                where_clauses.append(f"vl.student_id IN ({','.join('?' for _ in wards)})")
                params.extend(wards)
            elif active_role in ("warden", "assistant_warden"):
                if not linked_hid:
                    return {"total": 0, "records": []}
                where_clauses.append("vl.hostel_id = ?")
                params.append(int(linked_hid))
            elif active_role not in ("security_guard", "super_admin", "hostel_admin"):
                return {"total": 0, "records": []}

            # Query Filters
            if filters.get("status"):
                where_clauses.append("vl.status = ?")
                params.append(filters["status"])
            if filters.get("hostel_id"):
                where_clauses.append("vl.hostel_id = ?")
                params.append(filters["hostel_id"])
            if filters.get("date"):
                where_clauses.append("DATE(vl.created_at) = ?")
                params.append(filters["date"])
            if filters.get("search"):
                q = f"%{filters['search']}%"
                where_clauses.append("(vl.pass_number LIKE ? OR v.name LIKE ? OR v.phone LIKE ?)")
                params.extend([q, q, q])

            where_str = " AND ".join(where_clauses)

            # Count total
            cursor.execute(f"""
                SELECT COUNT(vl.id)
                FROM visitor_logs vl
                JOIN visitors v ON v.id = vl.visitor_id
                WHERE {where_str};
            """, params)
            total = cursor.fetchone()[0]

            limit = int(filters.get("limit", 50))
            offset = int(filters.get("offset", 0))

            query = f"""
                SELECT vl.*, v.name, v.phone, v.id_proof_type, v.id_proof_number,
                       s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       h.name as hostel_name, r.room_number, u.username as approved_by_name
                FROM visitor_logs vl
                JOIN visitors v ON v.id = vl.visitor_id
                JOIN students s ON s.id = vl.student_id
                LEFT JOIN hostels h ON h.id = vl.hostel_id
                LEFT JOIN rooms r ON r.id = vl.room_id
                LEFT JOIN users u ON u.id = vl.approved_by
                WHERE {where_str}
                ORDER BY vl.id DESC
                LIMIT ? OFFSET ?;
            """
            cursor.execute(query, params + [limit, offset])
            rows = cursor.fetchall()

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            records = []
            for r in rows:
                item = dict(r)
                if item["status"] == "Checked_In" and not item["check_out_time"] and item["expected_exit_time"]:
                    item["is_overdue"] = item["expected_exit_time"] < now_str
                else:
                    item["is_overdue"] = item["status"] == "Overdue"

                active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()
                if active_role in ["student", "parent", "parent_guardian"]:
                    item["id_proof_number"] = cls._mask_id_proof(item.get("id_proof_number", ""))
                    item["phone"] = cls._mask_phone(item.get("phone", ""))
                records.append(item)

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "records": records
            }
        finally:
            conn.close()

    @classmethod
    def get_visitor_reports(cls, start_date: str, end_date: str, hostel_id: Optional[int], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate statistical reports for visitor visits over a date range."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            hostel_clause = "AND vl.hostel_id = ?" if hostel_id else ""
            h_params = [hostel_id] if hostel_id else []

            query = f"""
                SELECT 
                    COUNT(vl.id) as total_visits,
                    SUM(CASE WHEN vl.status = 'Checked_In' THEN 1 ELSE 0 END) as active_now,
                    SUM(CASE WHEN vl.status = 'Checked_Out' THEN 1 ELSE 0 END) as completed_visits,
                    SUM(CASE WHEN vl.status = 'Rejected' THEN 1 ELSE 0 END) as rejected_visits
                FROM visitor_logs vl
                WHERE DATE(vl.created_at) >= ? AND DATE(vl.created_at) <= ? {hostel_clause};
            """
            cursor.execute(query, [start_date, end_date] + h_params)
            metrics = dict(cursor.fetchone())

            return {
                "start_date": start_date,
                "end_date": end_date,
                "hostel_id": hostel_id,
                "total_visits": metrics.get("total_visits") or 0,
                "active_now": metrics.get("active_now") or 0,
                "completed_visits": metrics.get("completed_visits") or 0,
                "rejected_visits": metrics.get("rejected_visits") or 0
            }
        finally:
            conn.close()

    @classmethod
    def check_visitor_curfew(cls, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
        """Automated curfew monitor: identifies and marks visitors exceeding permitted campus visiting hours."""
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True
        try:
            cursor = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                SELECT vl.id, vl.pass_number, vl.student_id, vl.hostel_id, vl.expected_exit_time,
                       v.name as visitor_name, s.first_name || ' ' || s.last_name as student_name
                FROM visitor_logs vl
                JOIN visitors v ON v.id = vl.visitor_id
                JOIN students s ON s.id = vl.student_id
                WHERE vl.status = 'Checked_In'
                  AND vl.check_out_time IS NULL
                  AND vl.expected_exit_time IS NOT NULL
                  AND vl.expected_exit_time < ?;
            """, (now_str,))
            overdue_list = [dict(r) for r in cursor.fetchall()]

            updated_count = 0
            if overdue_list:
                for ov in overdue_list:
                    cursor.execute("""
                        UPDATE visitor_logs
                        SET status = 'Overdue'
                        WHERE id = ?;
                    """, (ov["id"],))
                    updated_count += cursor.rowcount

                    cursor.execute("""
                        INSERT INTO notifications (user_id, title, message, category, priority, is_read, event_key, delivery_channel)
                        SELECT u.id, 'Visitor Curfew Violation Alert', ?, 'security', 'Urgent', 0, ?, 'in_app'
                        FROM users u
                        JOIN user_roles ur ON u.id = ur.user_id
                        JOIN roles r ON ur.role_id = r.id
                        WHERE r.name IN ('security_guard', 'warden', 'super_admin')
                          AND (u.linked_hostel_id = ? OR u.linked_hostel_id IS NULL);
                    """, (
                        f"Visitor {ov['visitor_name']} (Pass #{ov['pass_number']}) visiting student {ov['student_name']} has exceeded curfew time {ov['expected_exit_time']}.",
                        f"visitor_curfew:{ov['id']}",
                        ov.get("hostel_id")
                    ))

                conn.commit()
                cache_service.invalidate_by_tag("visitors")
                logger.warning(f"Visitor curfew monitor detected and updated {updated_count} overdue visitors.")

            return {
                "checked_at": now_str,
                "overdue_count": updated_count,
                "overdue_visitors": overdue_list
            }
        finally:
            if should_close:
                conn.close()
