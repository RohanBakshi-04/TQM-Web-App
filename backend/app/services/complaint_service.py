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
                VALUES (?, 'Complaint Received', ?, 'info');
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

    @staticmethod
    def get_complaints_list(
        conn: sqlite3.Connection,
        hostel_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Fetch paginated, filtered complaints for Warden and Admin dashboards."""
        cursor = conn.cursor()
        query = """
            SELECT 
                c.id, c.complaint_id, c.student_id, c.room_id, c.bed_id, c.category, c.title, c.description,
                c.severity, c.status, c.assigned_to, c.attachment_url, c.internal_remarks, c.rejection_reason,
                c.escalated, c.escalated_at, c.escalation_reason, c.feedback_rating, c.feedback_comment,
                c.reopened_count, c.affects_occupancy, c.created_at, c.resolved_at, c.closed_at,
                s.student_id AS enrollment_number, s.first_name || ' ' || s.last_name AS student_name,
                r.room_number,
                b.name AS building_name, b.hostel_id,
                h.name AS hostel_name, h.code AS hostel_code,
                u.first_name || ' ' || u.last_name AS technician_name
            FROM complaints c
            JOIN students s ON c.student_id = s.id
            LEFT JOIN rooms r ON c.room_id = r.id
            LEFT JOIN floors f ON r.floor_id = f.id
            LEFT JOIN buildings b ON f.building_id = b.id
            LEFT JOIN hostels h ON b.hostel_id = h.id
            LEFT JOIN users u ON c.assigned_to = u.id
            WHERE 1=1
        """
        params: List[Any] = []

        if hostel_id:
            query += " AND b.hostel_id = ?"
            params.append(hostel_id)

        if status_filter and status_filter.lower() != "all":
            query += " AND c.status = ?"
            params.append(status_filter)

        if category and category.lower() != "all":
            query += " AND c.category = ?"
            params.append(category)

        if severity and severity.lower() != "all":
            query += " AND c.severity = ?"
            params.append(severity)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query += " AND (c.complaint_id LIKE ? OR c.title LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ? OR s.student_id LIKE ? OR r.room_number LIKE ?)"
            params.extend([term, term, term, term, term, term])

        # Get total count
        count_sql = f"SELECT COUNT(*) FROM ({query})"
        total_items = cursor.execute(count_sql, params).fetchone()[0]

        # Pagination
        query += " ORDER BY c.id DESC LIMIT ? OFFSET ?;"
        offset = (max(1, page) - 1) * page_size
        params.extend([page_size, offset])

        rows = cursor.execute(query, params).fetchall()
        return {
            "items": [dict(r) for r in rows],
            "total": total_items,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_items + page_size - 1) // page_size if total_items > 0 else 1
        }

    @staticmethod
    def get_complaint_analytics(conn: sqlite3.Connection, hostel_id: Optional[int] = None) -> Dict[str, Any]:
        """Aggregate statistical metrics for complaint dashboards."""
        cursor = conn.cursor()
        base_where = "WHERE 1=1"
        params: List[Any] = []
        if hostel_id:
            base_where += " AND b.hostel_id = ?"
            params.append(hostel_id)

        sql = f"""
            SELECT 
                COUNT(*) AS total_complaints,
                COUNT(CASE WHEN c.status = 'Submitted' THEN 1 END) AS submitted_count,
                COUNT(CASE WHEN c.status = 'Pending' THEN 1 END) AS pending_count,
                COUNT(CASE WHEN c.status = 'Assigned' THEN 1 END) AS assigned_count,
                COUNT(CASE WHEN c.status = 'In Progress' THEN 1 END) AS in_progress_count,
                COUNT(CASE WHEN c.status = 'On Hold' THEN 1 END) AS on_hold_count,
                COUNT(CASE WHEN c.status = 'Resolved' THEN 1 END) AS resolved_count,
                COUNT(CASE WHEN c.status = 'Closed' THEN 1 END) AS closed_count,
                COUNT(CASE WHEN c.status = 'Rejected' THEN 1 END) AS rejected_count,
                COUNT(CASE WHEN c.status = 'Reopened' THEN 1 END) AS reopened_count,
                COUNT(CASE WHEN c.severity = 'Critical' AND c.status NOT IN ('Resolved', 'Closed', 'Rejected') THEN 1 END) AS critical_active_count,
                COUNT(CASE WHEN c.escalated = 1 AND c.status NOT IN ('Resolved', 'Closed', 'Rejected') THEN 1 END) AS escalated_active_count,
                AVG(c.feedback_rating) AS avg_satisfaction_rating
            FROM complaints c
            LEFT JOIN rooms r ON c.room_id = r.id
            LEFT JOIN floors f ON r.floor_id = f.id
            LEFT JOIN buildings b ON f.building_id = b.id
            {base_where};
        """
        row = cursor.execute(sql, params).fetchone()
        stats = dict(row) if row else {}
        stats["avg_satisfaction_rating"] = round(stats.get("avg_satisfaction_rating") or 0.0, 2)
        return stats

    @staticmethod
    def assign_complaint(
        conn: sqlite3.Connection,
        complaint_id: int,
        user_id: int,
        data: Any
    ) -> Dict[str, Any]:
        """Warden assigns a complaint to a technician and creates/updates linked maintenance task."""
        cursor = conn.cursor()
        c = cursor.execute("SELECT id, complaint_id, student_id, room_id, bed_id, title, description, category, severity, status FROM complaints WHERE id = ?;", (complaint_id,)).fetchone()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")

        if c["status"] in ("Resolved", "Closed", "Rejected"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot assign complaint in '{c['status']}' state. Reopen grievance first."
            )

        # Verify technician
        tech = cursor.execute("SELECT id, first_name, last_name FROM users WHERE id = ?;", (data.assigned_to,)).fetchone()
        if not tech:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Technician User ID {data.assigned_to} not found.")

        tech_name = f"{tech['first_name']} {tech['last_name']}".strip()
        new_priority = data.priority or c["severity"]

        # Update complaints table
        cursor.execute("""
            UPDATE complaints
            SET status = 'Assigned',
                assigned_to = ?,
                severity = ?,
                internal_remarks = ?,
                affects_occupancy = CASE WHEN ? THEN 1 ELSE affects_occupancy END
            WHERE id = ?;
        """, (data.assigned_to, new_priority, data.internal_remarks or "", 1 if data.affects_occupancy else 0, complaint_id))

        cursor.execute("""
            INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
            VALUES (?, ?, ?, 'Assigned', ?);
        """, (complaint_id, user_id, c["status"], f"Assigned to {tech_name}. {data.internal_remarks or ''}".strip()))

        # Enforce Poka-Yoke room status lock
        if data.affects_occupancy or new_priority == "Critical":
            if c["room_id"]:
                cursor.execute("UPDATE rooms SET status = 'Maintenance', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (c["room_id"],))
            if c["bed_id"]:
                cursor.execute("UPDATE beds SET status = 'Maintenance' WHERE id = ?;", (c["bed_id"],))

        # Check or create linked maintenance work-order
        existing_task = cursor.execute("SELECT id, task_code FROM maintenance_tasks WHERE complaint_id = ?;", (complaint_id,)).fetchone()
        if existing_task:
            cursor.execute("""
                UPDATE maintenance_tasks
                SET assigned_to = ?, assigned_worker = ?, priority = ?, deadline = ?, status = 'Assigned'
                WHERE id = ?;
            """, (data.assigned_to, tech_name, new_priority, data.deadline, existing_task["id"]))
            cursor.execute("""
                INSERT INTO maintenance_history (task_id, updated_by, status, notes)
                VALUES (?, ?, 'Assigned', ?);
            """, (existing_task["id"], user_id, f"Work order reassigned to {tech_name}."))
        else:
            task_count = cursor.execute("SELECT COUNT(*) + 1 FROM maintenance_tasks;").fetchone()[0]
            task_code = f"MT-{time.strftime('%Y')}-{task_count:04d}"
            cursor.execute("""
                INSERT INTO maintenance_tasks (
                    complaint_id, task_code, room_id, category, title, description,
                    priority, status, assigned_to, assigned_worker, deadline
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Assigned', ?, ?, ?);
            """, (
                complaint_id, task_code, c["room_id"], c["category"], c["title"], c["description"],
                new_priority, data.assigned_to, tech_name, data.deadline
            ))
            new_task_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO maintenance_history (task_id, updated_by, status, notes)
                VALUES (?, ?, 'Assigned', 'Task created via Warden assignment.');
            """, (new_task_id, user_id))

        # Notify technician
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type)
            VALUES (?, 'Work Order Assigned', ?, 'info');
        """, (
            data.assigned_to,
            f"Grievance Ticket #{c['complaint_id']} ('{c['title']}') has been assigned to you."
        ))

        # Notify student
        s_user = cursor.execute("SELECT id FROM users WHERE linked_student_id = ?;", (c["student_id"],)).fetchone()
        if s_user:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type)
                VALUES (?, 'Grievance Assigned to Technician', ?, 'info');
            """, (
                s_user["id"],
                f"Your grievance '{c['title']}' has been assigned to technician {tech_name}."
            ))

        conn.commit()
        CacheInvalidator.on_complaint_mutation()
        logger.info(f"Complaint #{complaint_id} assigned to technician {tech_name} by user #{user_id}")
        return ComplaintService.get_complaint_by_id(conn, complaint_id)

    @staticmethod
    def escalate_complaint(
        conn: sqlite3.Connection,
        complaint_id: int,
        user_id: int,
        reason: str,
        current_user: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Escalate complaint to senior management with active-role isolation."""
        cursor = conn.cursor()
        c = cursor.execute("SELECT id, complaint_id, student_id, title, status FROM complaints WHERE id = ?;", (complaint_id,)).fetchone()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")

        if current_user:
            active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()
            if active_role == "student":
                my_sid = current_user.get("linked_student_id")
                if c["student_id"] != my_sid:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: You can only escalate your own complaints.")
            elif active_role in ("parent_guardian", "parent"):
                from backend.app.services.auth_dependencies import get_parent_authorized_ward_ids
                wards = get_parent_authorized_ward_ids(conn, current_user)
                if c["student_id"] not in wards:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: You can only escalate complaints for your linked ward.")
            elif active_role in ("warden", "assistant_warden"):
                linked_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
                if not linked_hid:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access Denied: Staff member has no assigned hostel facility.")
                cursor.execute("""
                    SELECT bld.hostel_id
                    FROM room_allocations ra
                    JOIN rooms rm ON rm.id = ra.room_id
                    JOIN floors fl ON fl.id = rm.floor_id
                    JOIN buildings bld ON bld.id = fl.building_id
                    WHERE ra.student_id = ?;
                """, (c["student_id"],))
                alloc = cursor.fetchone()
                if not alloc or int(alloc[0]) != int(linked_hid):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Complaint belongs to a resident in another hostel facility.")
            elif active_role not in ("super_admin", "hostel_admin"):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Not authorized to escalate complaints.")

        cursor.execute("""
            UPDATE complaints
            SET escalated = 1, escalated_at = CURRENT_TIMESTAMP, escalation_reason = ?
            WHERE id = ?;
        """, (reason.strip(), complaint_id))

        cursor.execute("""
            INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
            VALUES (?, ?, ?, ?, ?);
        """, (complaint_id, user_id, c["status"], c["status"], f"Grievance escalated to Senior Administration: {reason.strip()}"))

        # Notify super admins
        admin_users = cursor.execute("""
            SELECT u.id FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            JOIN roles r ON ur.role_id = r.id
            WHERE r.name IN ('super_admin', 'warden') AND u.is_active = 1;
        """).fetchall()

        for adm in admin_users:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type)
                VALUES (?, 'Urgent Grievance Escalation', ?, 'alert');
            """, (
                adm["id"],
                f"URGENT: Complaint #{c['complaint_id']} ('{c['title']}') was escalated: {reason.strip()}"
            ))

        conn.commit()
        CacheInvalidator.on_complaint_mutation()
        logger.warning(f"Complaint #{complaint_id} Escalated: {reason.strip()}")
        return ComplaintService.get_complaint_by_id(conn, complaint_id)

    @staticmethod
    def reject_complaint(
        conn: sqlite3.Connection,
        complaint_id: int,
        user_id: int,
        reason: str
    ) -> Dict[str, Any]:
        """Warden rejects complaint with mandatory justification."""
        cursor = conn.cursor()
        c = cursor.execute("SELECT id, complaint_id, student_id, title, status, room_id, bed_id FROM complaints WHERE id = ?;", (complaint_id,)).fetchone()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")

        if c["status"] in ("Resolved", "Closed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject a '{c['status']}' complaint."
            )

        cursor.execute("""
            UPDATE complaints
            SET status = 'Rejected', rejection_reason = ?
            WHERE id = ?;
        """, (reason.strip(), complaint_id))

        cursor.execute("""
            INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
            VALUES (?, ?, ?, 'Rejected', ?);
        """, (complaint_id, user_id, c["status"], f"Rejected by Warden: {reason.strip()}"))

        # Cancel linked task if open
        cursor.execute("""
            UPDATE maintenance_tasks
            SET status = 'Cancelled'
            WHERE complaint_id = ? AND status IN ('Open', 'Assigned', 'Accepted');
        """, (complaint_id,))

        # Notify student
        s_user = cursor.execute("SELECT id FROM users WHERE linked_student_id = ?;", (c["student_id"],)).fetchone()
        if s_user:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type)
                VALUES (?, 'Grievance Rejected', ?, 'info');
            """, (
                s_user["id"],
                f"Your grievance '{c['title']}' has been reviewed and rejected. Reason: {reason.strip()}"
            ))

        conn.commit()
        CacheInvalidator.on_complaint_mutation()
        logger.info(f"Complaint #{complaint_id} Rejected: {reason.strip()}")
        return ComplaintService.get_complaint_by_id(conn, complaint_id)

    @staticmethod
    def close_complaint(
        conn: sqlite3.Connection,
        complaint_id: int,
        user_id: int,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Warden verifies resolution and approves closure of grievance."""
        cursor = conn.cursor()
        c = cursor.execute("SELECT id, complaint_id, student_id, title, status, room_id, bed_id FROM complaints WHERE id = ?;", (complaint_id,)).fetchone()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")

        if c["status"] != "Resolved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Poka-Yoke Workflow Violation: Cannot close complaint in '{c['status']}' status. Complaint must be marked 'Resolved' before closure can be approved."
            )

        cursor.execute("""
            UPDATE complaints
            SET status = 'Closed', closed_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """, (complaint_id,))

        cursor.execute("""
            INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
            VALUES (?, ?, 'Resolved', 'Closed', ?);
        """, (complaint_id, user_id, f"Closure approved by Warden: {notes.strip() or 'Resolution verified.'}"))

        # Restore room/bed from Maintenance if affected
        if c["room_id"]:
            active_tasks = cursor.execute("""
                SELECT COUNT(*) FROM maintenance_tasks
                WHERE room_id = ? AND status IN ('Assigned', 'Accepted', 'In Progress', 'On Hold');
            """, (c["room_id"],)).fetchone()[0]
            if active_tasks == 0:
                cursor.execute("UPDATE rooms SET status = 'Available', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'Maintenance';", (c["room_id"],))
                cursor.execute("UPDATE beds SET status = 'Available' WHERE room_id = ? AND status = 'Maintenance';", (c["room_id"],))

        # Notify student
        s_user = cursor.execute("SELECT id FROM users WHERE linked_student_id = ?;", (c["student_id"],)).fetchone()
        if s_user:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type)
                VALUES (?, 'Grievance Closed by Warden', ?, 'info');
            """, (
                s_user["id"],
                f"Your grievance '{c['title']}' has been officially verified and closed. Please take a moment to rate the service resolution."
            ))

        conn.commit()
        CacheInvalidator.on_complaint_mutation()
        logger.info(f"Complaint #{complaint_id} Closed by user #{user_id}")
        return ComplaintService.get_complaint_by_id(conn, complaint_id)
