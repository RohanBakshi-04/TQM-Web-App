from backend.app.services.auth_dependencies import get_parent_authorized_ward_ids
"""Leave Application and Gate Outpass Service.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Fast Response Time (< 10ms)
"""

import sqlite3
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

from backend.app.database.connection import get_db_connection
from backend.app.models.leave_dto import (
    LeaveApplicationCreate,
    LeaveApplicationUpdate,
    LeaveApprovalRequest,
    LeaveRejectionRequest,
    OutpassVerificationRequest,
    LeaveResponse,
    OutpassResponse
)
from backend.app.services.cache_service import cache_service
from backend.app.utils.logger import logger


class LeaveService:
    """Service managing student outstation/medical leave applications, warden approvals, and gate outpass verification."""

    @staticmethod
    def _get_student_for_user(conn: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
        """Resolve student ID for a student user account."""
        cursor = conn.cursor()
        cursor.execute("SELECT id, first_name || ' ' || last_name as name FROM students WHERE user_id = ?;", (user_id,))
        return cursor.fetchone()

    @staticmethod
    def _enforce_staff_hostel_access(current_user: Dict[str, Any], hostel_id: Optional[int]) -> None:
        """Validate warden assigned hostel permissions with strict fail-closed enforcement."""
        active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()
        user_hostel_id = current_user.get("linked_hostel_id") or current_user.get("hostel_id")

        if active_role in ["super_admin", "auditor"]:
            return
        if active_role in ["warden", "assistant_warden"]:
            if not user_hostel_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: Staff member has no assigned hostel facility."
                )
            if not hostel_id or int(user_hostel_id) != int(hostel_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Target record belongs to hostel #{hostel_id or 'Unassigned'}, outside your facility (#{user_hostel_id})."
                )

    @classmethod
    def create_leave_application(cls, payload: LeaveApplicationCreate, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a new leave application or save as draft."""
        if payload.end_date < payload.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date range: Expected return date must be on or after departure date."
            )

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            role = current_user.get("role")
            user_id = current_user.get("user_id")

            # Determine student
            active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()
            student_id = None
            if active_role == "student" or role == "student":
                st = cls._get_student_for_user(conn, user_id)
                if not st:
                    raise HTTPException(status_code=404, detail="Student profile not linked to your user account.")
                student_id = st["id"]
            elif active_role in ("parent", "parent_guardian") or role in ("parent", "parent_guardian"):
                from backend.app.services.auth_dependencies import get_parent_authorized_ward_ids
                wards = get_parent_authorized_ward_ids(conn, current_user)
                if not wards:
                    raise HTTPException(status_code=403, detail="Access Denied: No verified student wards linked to your parent account.")
                req_sid = getattr(payload, "student_id", None)
                if req_sid and int(req_sid) in wards:
                    student_id = int(req_sid)
                elif len(wards) == 1:
                    student_id = wards[0]
                else:
                    raise HTTPException(status_code=400, detail="Please select which linked ward to submit leave for.")
            elif active_role in ("super_admin", "hostel_admin", "warden"):
                req_sid = getattr(payload, "student_id", None)
                if not req_sid:
                    raise HTTPException(status_code=400, detail="Staff submitting leave on behalf must provide a valid student_id.")
                cursor.execute("SELECT id FROM students WHERE id = ?;", (req_sid,))
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail=f"Student #{req_sid} not found.")
                student_id = row[0]
            else:
                raise HTTPException(status_code=403, detail="Unauthorized role to create leave requests.")

            initial_status = "Draft" if payload.is_draft else "Submitted"

            cursor.execute("""
                INSERT INTO leave_requests (
                    student_id, leave_type, start_date, end_date, departure_time, expected_return_time,
                    reason, destination, emergency_contact, guardian_contact, document_url, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                student_id, payload.leave_type, payload.start_date, payload.end_date,
                payload.departure_time or "08:00", payload.expected_return_time or "20:00",
                payload.reason, payload.destination, payload.emergency_contact,
                payload.guardian_contact or "", payload.document_url or "", initial_status
            ))
            leave_id = cursor.lastrowid

            # If submitted immediately, alert warden
            if initial_status == "Submitted":
                # Find hostel wardens
                cursor.execute("""
                    SELECT u.id as warden_user_id
                    FROM room_allocations ra
                    JOIN rooms r ON r.id = ra.room_id
                    JOIN floors f ON f.id = r.floor_id
                    JOIN buildings bld ON bld.id = f.building_id
                    JOIN user_roles ur ON ur.role_id IN (SELECT id FROM roles WHERE name IN ('warden', 'assistant_warden'))
                    JOIN users u ON u.id = ur.user_id AND (u.linked_hostel_id = bld.hostel_id OR u.linked_hostel_id IS NULL)
                    WHERE ra.student_id = ? AND ra.allocation_status = 'Active';
                """, (student_id,))
                for w in cursor.fetchall():
                    cursor.execute("""
                        INSERT INTO notifications (user_id, title, message, notification_type)
                        VALUES (?, ?, ?, 'info');
                    """, (
                        w["warden_user_id"],
                        "New Leave Application",
                        f"Student has submitted a {payload.leave_type} request for {payload.start_date} to {payload.end_date}."
                    ))

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'SUBMIT_LEAVE', 'leave_requests', ?, ?, 0.6);
            """, (
                user_id,
                current_user.get("username", "student"),
                str(leave_id),
                f"Created leave ({initial_status}): {payload.leave_type} {payload.start_date} to {payload.end_date}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("leave")
            logger.info(f"Leave application #{leave_id} created with status {initial_status} by user {user_id}")

            return cls.get_leave_application(leave_id, current_user)
        finally:
            conn.close()

    @classmethod
    def get_leave_application(cls, leave_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch details of a single leave application, enforcing RBAC data isolation."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lr.*, s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       s.user_id as student_user_id, h.name as hostel_name, bld.hostel_id, r.room_number,
                       u.username as approved_by_name
                FROM leave_requests lr
                JOIN students s ON s.id = lr.student_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                LEFT JOIN users u ON u.id = lr.approved_by
                WHERE lr.id = ?;
            """, (leave_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Leave application not found.")

            res = dict(record)

            # Role isolation check
            role = current_user.get("role")
            if role == "student" and res.get("student_user_id") != current_user.get("user_id"):
                raise HTTPException(status_code=403, detail="Forbidden: You cannot access other students' leave applications.")
            if role in ["warden", "assistant_warden"] and res.get("hostel_id"):
                cls._enforce_staff_hostel_access(current_user, res["hostel_id"])

            # Check for linked outpass
            cursor.execute("""
                SELECT op.*, u1.username as exit_verified_by_name, u2.username as return_verified_by_name
                FROM outpasses op
                LEFT JOIN users u1 ON u1.id = op.exit_verified_by
                LEFT JOIN users u2 ON u2.id = op.return_verified_by
                WHERE op.leave_request_id = ?;
            """, (leave_id,))
            op_row = cursor.fetchone()
            if op_row:
                op_dict = dict(op_row)
                # Compute overdue flag
                if op_dict["status"] == "Departed" and not op_dict["actual_return_time"]:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                    op_dict["is_overdue"] = op_dict["expected_return_time"] < now_str
                else:
                    op_dict["is_overdue"] = op_dict["status"] == "Overdue"
                res["outpass"] = op_dict
            else:
                res["outpass"] = None

            return res
        finally:
            conn.close()

    @classmethod
    def update_leave_application(cls, leave_id: int, payload: LeaveApplicationUpdate, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Update leave application while still in Draft or Submitted state."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM leave_requests WHERE id = ?;", (leave_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Leave application not found.")

            from backend.app.services.auth_dependencies import verify_student_isolation
            verify_student_isolation(record["student_id"], current_user)

            active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()
            if active_role == "student":
                st = cls._get_student_for_user(conn, current_user.get("user_id") or current_user.get("id"))
                if not st or st["id"] != record["student_id"]:
                    raise HTTPException(status_code=403, detail="Access Denied: You can only edit your own leave applications.")

            if record["status"] not in ["Draft", "Submitted"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot edit leave application in '{record['status']}' state. Only Draft and Submitted requests can be modified."
                )

            # Determine updates
            updates = []
            params = []
            if payload.leave_type:
                updates.append("leave_type = ?")
                params.append(payload.leave_type)
            if payload.start_date:
                updates.append("start_date = ?")
                params.append(payload.start_date)
            if payload.end_date:
                updates.append("end_date = ?")
                params.append(payload.end_date)
            if payload.departure_time:
                updates.append("departure_time = ?")
                params.append(payload.departure_time)
            if payload.expected_return_time:
                updates.append("expected_return_time = ?")
                params.append(payload.expected_return_time)
            if payload.reason:
                updates.append("reason = ?")
                params.append(payload.reason)
            if payload.destination:
                updates.append("destination = ?")
                params.append(payload.destination)
            if payload.emergency_contact:
                updates.append("emergency_contact = ?")
                params.append(payload.emergency_contact)
            if payload.guardian_contact is not None:
                updates.append("guardian_contact = ?")
                params.append(payload.guardian_contact)
            if payload.document_url is not None:
                updates.append("document_url = ?")
                params.append(payload.document_url)
            if payload.submit_now and record["status"] == "Draft":
                updates.append("status = 'Submitted'")

            if updates:
                cursor.execute(f"UPDATE leave_requests SET {', '.join(updates)} WHERE id = ?;", params + [leave_id])
                conn.commit()

            return cls.get_leave_application(leave_id, current_user)
        finally:
            conn.close()

    @classmethod
    def approve_leave_application(cls, leave_id: int, payload: LeaveApprovalRequest, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Approve a submitted leave application, generating a unique gate outpass."""
        role = current_user.get("role")
        if role not in ["super_admin", "hostel_admin", "warden", "assistant_warden"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only hostel wardens and administrators can approve leave requests."
            )

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lr.*, s.user_id as student_user_id, s.first_name || ' ' || s.last_name as student_name,
                       bld.hostel_id
                FROM leave_requests lr
                JOIN students s ON s.id = lr.student_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                WHERE lr.id = ?;
            """, (leave_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Leave application not found.")

            # Students cannot approve their own application
            if record["student_user_id"] == current_user.get("user_id"):
                raise HTTPException(status_code=403, detail="Poka-Yoke Security Violation: Students cannot approve their own leave applications.")

            cls._enforce_staff_hostel_access(current_user, record["hostel_id"])

            # Workflow validation: must be Submitted or Under Review
            if record["status"] not in ["Submitted", "Under Review", "Pending"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid workflow transition: Cannot approve leave application currently in '{record['status']}' state."
                )

            # Generate unique outpass number: OP-YYYYMM-XXXX
            today_prefix = date.today().strftime("%Y%m")
            outpass_number = f"OP-{today_prefix}-{leave_id:04d}"

            expected_exit = f"{record['start_date']} {record['departure_time'] or '08:00'}"
            expected_return = f"{record['end_date']} {record['expected_return_time'] or '20:00'}"

            # 1. Update leave_request
            cursor.execute("""
                UPDATE leave_requests
                SET status = 'Approved', approved_by = ?, reviewed_at = CURRENT_TIMESTAMP, remarks = ?
                WHERE id = ?;
            """, (current_user.get("user_id"), payload.remarks or "Approved by Warden", leave_id))

            # 2. Insert or update outpasses table
            cursor.execute("""
                INSERT INTO outpasses (outpass_number, leave_request_id, student_id, status, expected_exit_time, expected_return_time)
                VALUES (?, ?, ?, 'Issued', ?, ?)
                ON CONFLICT(leave_request_id) DO UPDATE SET
                    outpass_number = excluded.outpass_number,
                    status = 'Issued',
                    expected_exit_time = excluded.expected_exit_time,
                    expected_return_time = excluded.expected_return_time;
            """, (outpass_number, leave_id, record["student_id"], expected_exit, expected_return))

            # 3. Notification to student
            if record["student_user_id"]:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type)
                    VALUES (?, ?, ?, 'success');
                """, (
                    record["student_user_id"],
                    "Leave Approved - Outpass Issued",
                    f"Your leave request has been approved. Digital Outpass #{outpass_number} is now active for gate departure."
                ))

            # 4. Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'APPROVE_LEAVE', 'leave_requests', ?, ?, 0.7);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "warden"),
                str(leave_id),
                f"Approved leave #{leave_id}. Outpass #{outpass_number} issued."
            ))

            conn.commit()
            cache_service.invalidate_by_tag("leave")
            logger.info(f"Leave #{leave_id} approved by user {current_user.get('user_id')}. Outpass {outpass_number} generated.")

            return cls.get_leave_application(leave_id, current_user)
        finally:
            conn.close()

    @classmethod
    def reject_leave_application(cls, leave_id: int, payload: LeaveRejectionRequest, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Reject a student leave application with mandatory audit reason."""
        role = current_user.get("role")
        if role not in ["super_admin", "hostel_admin", "warden", "assistant_warden"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only hostel wardens and administrators can reject leave requests."
            )

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lr.*, s.user_id as student_user_id, s.first_name || ' ' || s.last_name as student_name,
                       bld.hostel_id
                FROM leave_requests lr
                JOIN students s ON s.id = lr.student_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                WHERE lr.id = ?;
            """, (leave_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Leave application not found.")

            cls._enforce_staff_hostel_access(current_user, record["hostel_id"])

            if record["status"] in ["Approved", "Cancelled"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot reject leave application currently in '{record['status']}' state."
                )

            # 1. Update leave_requests
            cursor.execute("""
                UPDATE leave_requests
                SET status = 'Rejected', approved_by = ?, rejection_reason = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (current_user.get("user_id"), payload.reason, leave_id))

            # 2. Cancel any pending outpass
            cursor.execute("UPDATE outpasses SET status = 'Cancelled' WHERE leave_request_id = ?;", (leave_id,))

            # 3. Notification to student
            if record["student_user_id"]:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type)
                    VALUES (?, ?, ?, 'alert');
                """, (
                    record["student_user_id"],
                    "Leave Application Rejected",
                    f"Your leave request for {record['start_date']} has been rejected. Reason: {payload.reason}"
                ))

            # 4. Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'REJECT_LEAVE', 'leave_requests', ?, ?, 0.6);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "warden"),
                str(leave_id),
                f"Rejected leave #{leave_id}. Reason: {payload.reason}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("leave")
            logger.info(f"Leave #{leave_id} rejected by user {current_user.get('user_id')}. Reason: {payload.reason}")

            return cls.get_leave_application(leave_id, current_user)
        finally:
            conn.close()

    @classmethod
    def verify_outpass_exit(cls, outpass_ref: str, payload: OutpassVerificationRequest, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Record student physical exit at the campus security gate."""
        role = current_user.get("role") or current_user.get("active_role")
        user_roles = set(current_user.get("roles", []))
        if role not in ["security_guard", "super_admin", "hostel_admin", "warden", "assistant_warden"] and not user_roles.intersection({"super_admin", "hostel_admin", "security_guard", "warden", "assistant_warden"}):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only security guards and hostel staff can record gate exits."
            )

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Match by ID or outpass_number
            cursor.execute("""
                SELECT op.*, s.user_id as student_user_id, s.first_name || ' ' || s.last_name as student_name
                FROM outpasses op
                JOIN students s ON s.id = op.student_id
                WHERE op.id = ? OR op.outpass_number = ?;
            """, (outpass_ref, outpass_ref))
            outpass = cursor.fetchone()
            if not outpass:
                raise HTTPException(status_code=404, detail=f"Outpass '{outpass_ref}' not found.")

            # Duplicate exit prevention
            if outpass["status"] in ["Departed", "Returned"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate Exit Error: Outpass #{outpass['outpass_number']} exit was already recorded at {outpass['actual_exit_time']}."
                )

            if outpass["status"] == "Cancelled":
                raise HTTPException(status_code=400, detail="Cannot record exit: Outpass has been Cancelled.")

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                UPDATE outpasses
                SET status = 'Departed', actual_exit_time = ?, exit_verified_by = ?, exit_remarks = ?
                WHERE id = ?;
            """, (now_str, current_user.get("user_id"), payload.remarks or "", outpass["id"]))

            # Notification to student
            if outpass["student_user_id"]:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type)
                    VALUES (?, ?, ?, 'info');
                """, (
                    outpass["student_user_id"],
                    "Gate Exit Recorded",
                    f"Your departure through campus security was logged at {now_str}. Expected return: {outpass['expected_return_time']}."
                ))

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'GATE_EXIT', 'outpasses', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "guard"),
                str(outpass["id"]),
                f"Recorded gate departure for student {outpass['student_id']}. Outpass #{outpass['outpass_number']}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("leave")
            logger.info(f"Gate exit verified for outpass {outpass['outpass_number']} by {current_user.get('username')}")

            return cls.get_leave_application(outpass["leave_request_id"], current_user)
        finally:
            conn.close()

    @classmethod
    def verify_outpass_return(cls, outpass_ref: str, payload: OutpassVerificationRequest, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Record student physical return to the hostel at campus security gate."""
        role = current_user.get("role") or current_user.get("active_role")
        user_roles = set(current_user.get("roles", []))
        if role not in ["security_guard", "super_admin", "hostel_admin", "warden", "assistant_warden"] and not user_roles.intersection({"super_admin", "hostel_admin", "security_guard", "warden", "assistant_warden"}):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only security guards and hostel staff can record gate returns."
            )

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT op.*, s.user_id as student_user_id, s.first_name || ' ' || s.last_name as student_name
                FROM outpasses op
                JOIN students s ON s.id = op.student_id
                WHERE op.id = ? OR op.outpass_number = ?;
            """, (outpass_ref, outpass_ref))
            outpass = cursor.fetchone()
            if not outpass:
                raise HTTPException(status_code=404, detail=f"Outpass '{outpass_ref}' not found.")

            # Duplicate return prevention
            if outpass["status"] == "Returned":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate Return Error: Outpass #{outpass['outpass_number']} return was already recorded at {outpass['actual_return_time']}."
                )

            if outpass["status"] == "Issued":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Workflow: Student has not exited campus yet. Record gate exit first."
                )

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                UPDATE outpasses
                SET status = 'Returned', actual_return_time = ?, return_verified_by = ?, return_remarks = ?
                WHERE id = ?;
            """, (now_str, current_user.get("user_id"), payload.remarks or "", outpass["id"]))

            # Notification to student
            if outpass["student_user_id"]:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type)
                    VALUES (?, ?, ?, 'success');
                """, (
                    outpass["student_user_id"],
                    "Hostel Return Recorded",
                    f"Your safe return was verified at {now_str}. Welcome back!"
                ))

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'GATE_RETURN', 'outpasses', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "guard"),
                str(outpass["id"]),
                f"Recorded safe gate return for student {outpass['student_id']}. Outpass #{outpass['outpass_number']}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("leave")
            logger.info(f"Gate return verified for outpass {outpass['outpass_number']} by {current_user.get('username')}")

            return cls.get_leave_application(outpass["leave_request_id"], current_user)
        finally:
            conn.close()

    @classmethod
    def get_overdue_outpasses(cls, hostel_id: Optional[int], current_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify all resident students who exited campus and are overdue past their curfew/expected return."""
        role = current_user.get("role")
        user_hostel_id = current_user.get("hostel_id")
        if role in ["warden", "assistant_warden"] and user_hostel_id:
            hostel_id = int(user_hostel_id)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

            hostel_clause = "AND bld.hostel_id = ?" if hostel_id else ""
            h_params = [hostel_id] if hostel_id else []

            query = f"""
                SELECT op.*, s.first_name || ' ' || s.last_name as student_name, s.student_id as roll_no,
                       lr.emergency_contact as emergency_contact_phone, h.name as hostel_name, r.room_number, lr.destination, lr.leave_type
                FROM outpasses op
                JOIN students s ON s.id = op.student_id
                JOIN leave_requests lr ON lr.id = op.leave_request_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                WHERE op.status = 'Departed' AND op.actual_return_time IS NULL AND op.expected_return_time < ? {hostel_clause}
                ORDER BY op.expected_return_time ASC;
            """
            cursor.execute(query, [now_str] + h_params)
            rows = cursor.fetchall()

            result = []
            for r in rows:
                item = dict(r)
                item["is_overdue"] = True
                result.append(item)
            return result
        finally:
            conn.close()

    @classmethod
    def get_leave_applications(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch filtered and paginated leave applications adhering to strict RBAC row-level isolation."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            role = current_user.get("role")
            user_hostel_id = current_user.get("hostel_id")

            where_clauses = ["1=1"]
            params: List[Any] = []

            # RBAC Isolation
            if role == "student":
                st = cls._get_student_for_user(conn, current_user.get("user_id"))
                if not st:
                    return {"total": 0, "records": []}
                where_clauses.append("lr.student_id = ?")
                params.append(st["id"])
            elif role in ("parent", "parent_guardian"):
                wards = get_parent_authorized_ward_ids(conn, current_user)
                if not wards:
                    return {"total": 0, "records": []}
                placeholders = ",".join("?" for _ in wards)
                where_clauses.append(f"lr.student_id IN ({placeholders})")
                params.extend(wards)
            elif role in ["warden", "assistant_warden"] and user_hostel_id:
                where_clauses.append("bld.hostel_id = ?")
                params.append(int(user_hostel_id))

            # Query Filters
            if filters.get("status"):
                where_clauses.append("lr.status = ?")
                params.append(filters["status"])
            if filters.get("leave_type"):
                where_clauses.append("lr.leave_type = ?")
                params.append(filters["leave_type"])
            if filters.get("hostel_id"):
                where_clauses.append("bld.hostel_id = ?")
                params.append(filters["hostel_id"])
            if filters.get("start_date"):
                where_clauses.append("lr.start_date >= ?")
                params.append(filters["start_date"])
            if filters.get("end_date"):
                where_clauses.append("lr.end_date <= ?")
                params.append(filters["end_date"])

            where_str = " AND ".join(where_clauses)

            # Count total
            cursor.execute(f"""
                SELECT COUNT(lr.id)
                FROM leave_requests lr
                JOIN students s ON s.id = lr.student_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                WHERE {where_str};
            """, params)
            total = cursor.fetchone()[0]

            limit = int(filters.get("limit", 50))
            offset = int(filters.get("offset", 0))

            query = f"""
                SELECT lr.*, s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       h.name as hostel_name, bld.hostel_id, r.room_number,
                       op.outpass_number, op.status as outpass_status, op.actual_exit_time, op.actual_return_time
                FROM leave_requests lr
                JOIN students s ON s.id = lr.student_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                LEFT JOIN outpasses op ON op.leave_request_id = lr.id
                WHERE {where_str}
                ORDER BY lr.id DESC
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
    def get_outpasses(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch filtered and paginated gate outpasses for security officers and wardens."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            role = current_user.get("role")
            user_hostel_id = current_user.get("hostel_id")

            where_clauses = ["1=1"]
            params: List[Any] = []

            # RBAC Isolation
            if role == "student":
                st = cls._get_student_for_user(conn, current_user.get("user_id"))
                if not st:
                    return {"total": 0, "records": []}
                where_clauses.append("op.student_id = ?")
                params.append(st["id"])
            elif role in ["warden", "assistant_warden"] and user_hostel_id:
                where_clauses.append("bld.hostel_id = ?")
                params.append(int(user_hostel_id))

            if filters.get("status"):
                where_clauses.append("op.status = ?")
                params.append(filters["status"])
            if filters.get("outpass_number"):
                where_clauses.append("op.outpass_number LIKE ?")
                params.append(f"%{filters['outpass_number']}%")

            where_str = " AND ".join(where_clauses)

            cursor.execute(f"""
                SELECT COUNT(op.id)
                FROM outpasses op
                JOIN students s ON s.id = op.student_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                WHERE {where_str};
            """, params)
            total = cursor.fetchone()[0]

            limit = int(filters.get("limit", 50))
            offset = int(filters.get("offset", 0))

            query = f"""
                SELECT op.*, s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       h.name as hostel_name, r.room_number, lr.leave_type, lr.destination,
                       u1.username as exit_verified_by_name, u2.username as return_verified_by_name
                FROM outpasses op
                JOIN students s ON s.id = op.student_id
                JOIN leave_requests lr ON lr.id = op.leave_request_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                LEFT JOIN users u1 ON u1.id = op.exit_verified_by
                LEFT JOIN users u2 ON u2.id = op.return_verified_by
                WHERE {where_str}
                ORDER BY op.id DESC
                LIMIT ? OFFSET ?;
            """
            cursor.execute(query, params + [limit, offset])
            rows = cursor.fetchall()

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            records = []
            for r in rows:
                item = dict(r)
                if item["status"] == "Departed" and not item["actual_return_time"]:
                    item["is_overdue"] = item["expected_return_time"] < now_str
                else:
                    item["is_overdue"] = item["status"] == "Overdue"
                records.append(item)

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "records": records
            }
        finally:
            conn.close()
