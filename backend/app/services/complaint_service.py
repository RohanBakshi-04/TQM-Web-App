"""Student Complaint Business Logic and Lifecycle Engine.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

import sqlite3
import time
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status

from backend.app.models.complaint_dto import (
    VALID_CATEGORIES,
    VALID_SEVERITIES,
    VALID_STATUSES,
    ComplaintCreate,
    ComplaintFeedback,
    ComplaintReopen,
)
from backend.app.services.cache_invalidation import CacheInvalidator
from backend.app.utils.logger import logger


class ComplaintService:
    """Core domain logic for Student Grievance Submission, Tracking, and Feedback."""

    @staticmethod
    def submit_complaint(
        conn: sqlite3.Connection,
        student_id: int,
        data: ComplaintCreate,
        submitted_by_user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Submit a new student complaint with validation and room linkage."""
        cursor = conn.cursor()

        # Validate category and severity
        if data.category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid complaint category '{data.category}'. Allowed: {', '.join(VALID_CATEGORIES)}"
            )

        if data.severity not in VALID_SEVERITIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid complaint severity '{data.severity}'. Allowed: {', '.join(VALID_SEVERITIES)}"
            )

        # Verify student exists
        student = cursor.execute("SELECT id, student_id, first_name, last_name FROM students WHERE id = ?;", (student_id,)).fetchone()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student record not found.")

        # If room_id not provided, resolve student's active allocated room
        room_id = data.room_id
        bed_id = data.bed_id
        hostel_id = None

        if not room_id:
            active_alloc = cursor.execute("""
                SELECT ra.room_id, ra.bed_id, b.hostel_id
                FROM room_allocations ra
                JOIN rooms r ON ra.room_id = r.id
                JOIN floors f ON r.floor_id = f.id
                JOIN buildings b ON f.building_id = b.id
                WHERE ra.student_id = ? AND ra.allocation_status = 'Active';
            """, (student_id,)).fetchone()
            if active_alloc:
                room_id = active_alloc["room_id"]
                bed_id = active_alloc["bed_id"]
                hostel_id = active_alloc["hostel_id"]
        elif room_id:
            h_row = cursor.execute("""
                SELECT b.hostel_id 
                FROM rooms r
                JOIN floors f ON r.floor_id = f.id
                JOIN buildings b ON f.building_id = b.id
                WHERE r.id = ?;
            """, (room_id,)).fetchone()
            if h_row:
                hostel_id = h_row["hostel_id"]

        # Generate unique ticket ID: CMP-YYYY-XXXXX
        ticket_seq = cursor.execute("SELECT COUNT(*) + 1 FROM complaints;").fetchone()[0]
        complaint_ticket = f"CMP-{time.strftime('%Y')}-{ticket_seq:04d}"

        cursor.execute("""
            INSERT INTO complaints (
                complaint_id, student_id, room_id, bed_id, category, title, description,
                severity, status, attachment_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Submitted', ?);
        """, (
            complaint_ticket,
            student_id,
            room_id,
            bed_id,
            data.category,
            data.title.strip(),
            data.description.strip(),
            data.severity,
            data.attachment_url
        ))
        complaint_db_id = cursor.lastrowid

        # Record initial status update in history
        cursor.execute("""
            INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
            VALUES (?, ?, 'None', 'Submitted', 'Grievance submitted by student.');
        """, (complaint_db_id, submitted_by_user_id))

        # Notification for student
        if submitted_by_user_id:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type)
                VALUES (?, 'Complaint Received', ?, 'complaint');
            """, (
                submitted_by_user_id,
                f"Your complaint '{data.title}' has been logged with Ticket #{complaint_ticket}."
            ))

        conn.commit()

        # Evict cached dashboard metrics
        CacheInvalidator.on_complaint_mutation(hostel_id=hostel_id)
        logger.info(f"Student Complaint Created: Ticket #{complaint_ticket} (ID: {complaint_db_id}) by Student #{student_id}")

        return ComplaintService.get_complaint_by_id(conn, complaint_db_id)

    @staticmethod
    def get_complaint_by_id(
        conn: sqlite3.Connection,
        complaint_id: int,
        student_id_restriction: Optional[int] = None
    ) -> Dict[str, Any]:
        """Fetch complete complaint record including update history and linked room hierarchy."""
        cursor = conn.cursor()
        c = cursor.execute("""
            SELECT 
                c.id, c.complaint_id, c.student_id, c.room_id, c.bed_id, c.category, c.title, c.description,
                c.severity, c.status, c.assigned_to, c.attachment_url, c.internal_remarks, c.rejection_reason,
                c.escalated, c.escalated_at, c.escalation_reason, c.feedback_rating, c.feedback_comment,
                c.reopened_count, c.affects_occupancy, c.created_at, c.resolved_at, c.closed_at,
                s.student_id AS enrollment_number, s.first_name || ' ' || s.last_name AS student_name, s.email AS student_email, s.phone AS student_phone,
                r.room_number, r.room_type,
                b.name AS building_name, b.hostel_id,
                h.name AS hostel_name, h.code AS hostel_code,
                u.first_name || ' ' || u.last_name AS assigned_worker_name
            FROM complaints c
            JOIN students s ON c.student_id = s.id
            LEFT JOIN rooms r ON c.room_id = r.id
            LEFT JOIN floors f ON r.floor_id = f.id
            LEFT JOIN buildings b ON f.building_id = b.id
            LEFT JOIN hostels h ON b.hostel_id = h.id
            LEFT JOIN users u ON c.assigned_to = u.id
            WHERE c.id = ?;
        """, (complaint_id,)).fetchone()

        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint record not found.")

        # Data isolation security check
        if student_id_restriction and c["student_id"] != student_id_restriction:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: You are not authorized to view another student's private grievance."
            )

        # Fetch update history
        updates = cursor.execute("""
            SELECT 
                cu.id, cu.previous_status, cu.new_status, cu.comment, cu.created_at,
                u.username, u.first_name || ' ' || u.last_name AS updater_name
            FROM complaint_updates cu
            LEFT JOIN users u ON cu.updated_by = u.id
            WHERE cu.complaint_id = ?
            ORDER BY cu.id ASC;
        """, (complaint_id,)).fetchall()

        # Linked maintenance task (if assigned)
        task = cursor.execute("""
            SELECT id, task_code, status, priority, assigned_worker, scheduled_date, completed_at
            FROM maintenance_tasks
            WHERE complaint_id = ?;
        """, (complaint_id,)).fetchone()

        record = dict(c)
        record["updates"] = [dict(u) for u in updates]
        record["maintenance_task"] = dict(task) if task else None
        return record

    @staticmethod
    def get_student_complaints(
        conn: sqlite3.Connection,
        student_id: int,
        status_filter: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve all complaints submitted by a student with optional status/category filters."""
        cursor = conn.cursor()
        sql = """
            SELECT 
                c.id, c.complaint_id, c.category, c.title, c.description, c.severity, c.status,
                c.attachment_url, c.feedback_rating, c.created_at, c.resolved_at,
                r.room_number, h.name AS hostel_name
            FROM complaints c
            LEFT JOIN rooms r ON c.room_id = r.id
            LEFT JOIN floors f ON r.floor_id = f.id
            LEFT JOIN buildings b ON f.building_id = b.id
            LEFT JOIN hostels h ON b.hostel_id = h.id
            WHERE c.student_id = ?
        """
        params: List[Any] = [student_id]

        if status_filter:
            sql += " AND c.status = ?"
            params.append(status_filter)

        if category:
            sql += " AND c.category = ?"
            params.append(category)

        sql += " ORDER BY c.id DESC;"
        rows = cursor.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def add_comment(
        conn: sqlite3.Connection,
        complaint_id: int,
        user_id: int,
        comment: str,
        student_id_restriction: Optional[int] = None
    ) -> Dict[str, Any]:
        """Append an informational comment or query to the complaint history."""
        cursor = conn.cursor()
        c = cursor.execute("SELECT id, student_id, status FROM complaints WHERE id = ?;", (complaint_id,)).fetchone()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")

        if student_id_restriction and c["student_id"] != student_id_restriction:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

        cursor.execute("""
            INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
            VALUES (?, ?, ?, ?, ?);
        """, (complaint_id, user_id, c["status"], c["status"], comment.strip()))

        conn.commit()
        return {"status": "success", "message": "Comment recorded successfully."}

    @staticmethod
    def reopen_complaint(
        conn: sqlite3.Connection,
        complaint_id: int,
        student_id: int,
        data: ComplaintReopen,
        user_id: int
    ) -> Dict[str, Any]:
        """Reopen an eligible resolved/closed complaint if the issue persists."""
        cursor = conn.cursor()
        c = cursor.execute("SELECT id, complaint_id, student_id, status, reopened_count FROM complaints WHERE id = ?;", (complaint_id,)).fetchone()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")

        if c["student_id"] != student_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Cannot reopen another student's complaint.")

        if c["status"] not in ("Resolved", "Closed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reopen complaint with status '{c['status']}'. Only 'Resolved' or 'Closed' complaints can be reopened."
            )

        cursor.execute("""
            UPDATE complaints
            SET status = 'Reopened', reopened_count = reopened_count + 1
            WHERE id = ?;
        """, (complaint_id,))

        cursor.execute("""
            INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
            VALUES (?, ?, ?, 'Reopened', ?);
        """, (complaint_id, user_id, c["status"], f"Reopened by student: {data.reason}"))

        conn.commit()
        CacheInvalidator.on_complaint_mutation()
        logger.info(f"Complaint Reopened: Ticket #{c['complaint_id']} by Student #{student_id}")

        return ComplaintService.get_complaint_by_id(conn, complaint_id)

    @staticmethod
    def submit_feedback(
        conn: sqlite3.Connection,
        complaint_id: int,
        student_id: int,
        data: ComplaintFeedback
    ) -> Dict[str, Any]:
        """Submit post-resolution satisfaction feedback."""
        cursor = conn.cursor()
        c = cursor.execute("SELECT id, complaint_id, student_id, status FROM complaints WHERE id = ?;", (complaint_id,)).fetchone()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")

        if c["student_id"] != student_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

        if c["status"] not in ("Resolved", "Closed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Feedback can only be provided after complaint resolution. Current status: '{c['status']}'."
            )

        cursor.execute("""
            UPDATE complaints
            SET feedback_rating = ?, feedback_comment = ?
            WHERE id = ?;
        """, (data.rating, data.comment.strip() if data.comment else "", complaint_id))

        conn.commit()
        logger.info(f"Feedback recorded for Complaint #{c['complaint_id']}: Rating {data.rating}/5")
        return {"status": "success", "message": "Thank you for your feedback!", "rating": data.rating}
