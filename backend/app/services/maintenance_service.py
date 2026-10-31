"""Maintenance Task and Work-Order Management Service.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

import sqlite3
import time
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status

from backend.app.models.maintenance_dto import (
    VALID_MAINTENANCE_STATUSES,
    VALID_PRIORITIES,
    MaintenanceTaskComplete,
    MaintenanceTaskCreate,
    MaintenanceTaskHold,
    MaintenanceTaskProgress,
    MaintenanceTaskVerify,
)
from backend.app.services.cache_invalidation import CacheInvalidator
from backend.app.utils.logger import logger


class MaintenanceService:
    """Core domain logic for Work-Order Management, Technician Assignment, and Infrastructure Integrity."""

    @staticmethod
    def create_maintenance_task(
        conn: sqlite3.Connection,
        data: MaintenanceTaskCreate,
        created_by_user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a new maintenance task work-order and link to infrastructure/complaint."""
        cursor = conn.cursor()

        if data.priority not in VALID_PRIORITIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid priority '{data.priority}'. Allowed: {', '.join(VALID_PRIORITIES)}"
            )

        complaint = None
        room_id = data.room_id
        bed_id = None
        hostel_id = None

        if data.complaint_id:
            complaint = cursor.execute("""
                SELECT c.id, c.complaint_id, c.student_id, c.room_id, c.bed_id, c.category, c.status,
                       b.hostel_id
                FROM complaints c
                LEFT JOIN rooms r ON c.room_id = r.id
                LEFT JOIN floors f ON r.floor_id = f.id
                LEFT JOIN buildings b ON f.building_id = b.id
                WHERE c.id = ?;
            """, (data.complaint_id,)).fetchone()

            if not complaint:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Linked complaint #{data.complaint_id} does not exist."
                )

            if not room_id:
                room_id = complaint["room_id"]
            bed_id = complaint["bed_id"]
            hostel_id = complaint["hostel_id"]

        if room_id and not hostel_id:
            h_row = cursor.execute("""
                SELECT b.hostel_id FROM rooms r
                JOIN floors f ON r.floor_id = f.id
                JOIN buildings b ON f.building_id = b.id
                WHERE r.id = ?;
            """, (room_id,)).fetchone()
            if h_row:
                hostel_id = h_row["hostel_id"]

        # Generate unique Task Code: MT-YYYY-XXXX
        task_count = cursor.execute("SELECT COUNT(*) + 1 FROM maintenance_tasks;").fetchone()[0]
        task_code = f"MT-{time.strftime('%Y')}-{task_count:04d}"

        assigned_worker_name = ""
        initial_status = "Assigned" if data.assigned_to else "Open"

        if data.assigned_to:
            w = cursor.execute("SELECT first_name, last_name FROM users WHERE id = ?;", (data.assigned_to,)).fetchone()
            if w:
                assigned_worker_name = f"{w['first_name']} {w['last_name']}".strip()

        cursor.execute("""
            INSERT INTO maintenance_tasks (
                complaint_id, task_code, room_id, title, description,
                priority, status, assigned_to, assigned_worker,
                deadline, estimated_cost, scheduled_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            data.complaint_id,
            task_code,
            room_id,
            data.title.strip(),
            data.description.strip(),
            data.priority,
            initial_status,
            data.assigned_to,
            assigned_worker_name,
            data.deadline,
            data.estimated_cost,
            data.scheduled_date
        ))
        task_id = cursor.lastrowid

        # Record initial history entry
        cursor.execute("""
            INSERT INTO maintenance_history (task_id, updated_by, status, notes)
            VALUES (?, ?, ?, 'Work order issued and logged into system.');
        """, (task_id, created_by_user_id, initial_status))

        # Infrastructure maintenance status integration & Poka-Yoke enforcement
        if data.affects_occupancy or data.priority == "Critical":
            if room_id:
                cursor.execute("UPDATE rooms SET status = 'Maintenance', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (room_id,))
            if bed_id:
                cursor.execute("UPDATE beds SET status = 'Maintenance' WHERE id = ?;", (bed_id,))

        # Update linked complaint if present
        if data.complaint_id:
            cursor.execute("""
                UPDATE complaints
                SET status = 'Assigned',
                    assigned_to = ?,
                    affects_occupancy = CASE WHEN ? THEN 1 ELSE affects_occupancy END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (data.assigned_to, 1 if data.affects_occupancy else 0, data.complaint_id))

            cursor.execute("""
                INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
                VALUES (?, ?, ?, 'Assigned', ?);
            """, (
                data.complaint_id,
                created_by_user_id,
                complaint["status"],
                f"Work order #{task_code} assigned to technician {assigned_worker_name or 'Staff'}."
            ))

        # Notify assigned worker
        if data.assigned_to:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type)
                VALUES (?, 'New Work Order Assigned', ?, 'maintenance');
            """, (
                data.assigned_to,
                f"Work Order #{task_code} ('{data.title}') has been assigned to you with {data.priority} priority."
            ))

        conn.commit()

        # Invalidate metrics cache
        CacheInvalidator.on_maintenance_mutation(hostel_id=hostel_id)
        logger.info(f"Maintenance Task Created: {task_code} (ID: {task_id}) assigned to {assigned_worker_name or 'Unassigned'}")

        return MaintenanceService.get_task_by_id(conn, task_id)

    @staticmethod
    def get_maintenance_tasks(
        conn: sqlite3.Connection,
        status_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
        assigned_to: Optional[int] = None,
        hostel_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch filtered maintenance tasks with related room, hostel, and user details."""
        cursor = conn.cursor()
        query = """
            SELECT 
                mt.id, mt.task_code, mt.complaint_id, mt.room_id, mt.title, mt.description,
                mt.priority, mt.status, mt.assigned_to, mt.assigned_worker, mt.resolution_notes,
                mt.completion_photo_url, mt.hold_reason, mt.deadline, mt.estimated_cost,
                mt.actual_cost, mt.scheduled_date, mt.verified_by, mt.verified_at, mt.completed_at, mt.created_at,
                r.room_number, r.status AS room_status,
                b.name AS building_name, b.hostel_id,
                h.name AS hostel_name, h.code AS hostel_code,
                u.first_name || ' ' || u.last_name AS technician_name, u.email AS technician_email,
                c.complaint_id AS complaint_ticket, c.category AS complaint_category,
                s.student_id AS student_enrollment, s.first_name || ' ' || s.last_name AS student_name
            FROM maintenance_tasks mt
            LEFT JOIN rooms r ON mt.room_id = r.id
            LEFT JOIN floors f ON r.floor_id = f.id
            LEFT JOIN buildings b ON f.building_id = b.id
            LEFT JOIN hostels h ON b.hostel_id = h.id
            LEFT JOIN users u ON mt.assigned_to = u.id
            LEFT JOIN complaints c ON mt.complaint_id = c.id
            LEFT JOIN students s ON c.student_id = s.id
            WHERE 1=1
        """
        params: List[Any] = []

        if status_filter and status_filter.lower() != "all":
            query += " AND mt.status = ?"
            params.append(status_filter)

        if priority_filter and priority_filter.lower() != "all":
            query += " AND mt.priority = ?"
            params.append(priority_filter)

        if assigned_to:
            query += " AND mt.assigned_to = ?"
            params.append(assigned_to)

        if hostel_id:
            query += " AND b.hostel_id = ?"
            params.append(hostel_id)

        query += " ORDER BY mt.id DESC;"

        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_task_by_id(conn: sqlite3.Connection, task_id: int) -> Dict[str, Any]:
        """Fetch comprehensive maintenance task record including history log."""
        cursor = conn.cursor()
        task = cursor.execute("""
            SELECT 
                mt.id, mt.task_code, mt.complaint_id, mt.room_id, mt.title, mt.description,
                mt.priority, mt.status, mt.assigned_to, mt.assigned_worker, mt.resolution_notes,
                mt.completion_photo_url, mt.hold_reason, mt.deadline, mt.estimated_cost,
                mt.actual_cost, mt.scheduled_date, mt.verified_by, mt.verified_at, mt.completed_at, mt.created_at,
                r.room_number, r.status AS room_status,
                b.name AS building_name, b.hostel_id,
                h.name AS hostel_name, h.code AS hostel_code,
                u.first_name || ' ' || u.last_name AS technician_name, u.email AS technician_email,
                v.first_name || ' ' || v.last_name AS verifier_name,
                c.complaint_id AS complaint_ticket, c.category AS complaint_category, c.student_id,
                s.student_id AS student_enrollment, s.first_name || ' ' || s.last_name AS student_name, s.phone AS student_phone
            FROM maintenance_tasks mt
            LEFT JOIN rooms r ON mt.room_id = r.id
            LEFT JOIN floors f ON r.floor_id = f.id
            LEFT JOIN buildings b ON f.building_id = b.id
            LEFT JOIN hostels h ON b.hostel_id = h.id
            LEFT JOIN users u ON mt.assigned_to = u.id
            LEFT JOIN users v ON mt.verified_by = v.id
            LEFT JOIN complaints c ON mt.complaint_id = c.id
            LEFT JOIN students s ON c.student_id = s.id
            WHERE mt.id = ?;
        """, (task_id,)).fetchone()

        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Maintenance Task #{task_id} not found.")

        history = cursor.execute("""
            SELECT mh.id, mh.status, mh.notes, mh.logged_at,
                   u.username, u.first_name || ' ' || u.last_name AS updater_name
            FROM maintenance_history mh
            LEFT JOIN users u ON mh.updated_by = u.id
            WHERE mh.task_id = ?
            ORDER BY mh.id ASC;
        """, (task_id,)).fetchall()

        res = dict(task)
        res["history"] = [dict(h) for h in history]
        return res

    @staticmethod
    def accept_task(conn: sqlite3.Connection, task_id: int, worker_user_id: int, notes: str = "") -> Dict[str, Any]:
        """Technician accepts an assigned maintenance work-order."""
        cursor = conn.cursor()
        task = cursor.execute("SELECT id, status, complaint_id, title FROM maintenance_tasks WHERE id = ?;", (task_id,)).fetchone()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance task not found.")

        if task["status"] not in ("Open", "Assigned"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot accept task in current status '{task['status']}'."
            )

        cursor.execute("UPDATE maintenance_tasks SET status = 'Accepted' WHERE id = ?;", (task_id,))
        cursor.execute("""
            INSERT INTO maintenance_history (task_id, updated_by, status, notes)
            VALUES (?, ?, 'Accepted', ?);
        """, (task_id, worker_user_id, notes or "Task accepted by technician."))

        if task["complaint_id"]:
            cursor.execute("""
                INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
                VALUES (?, ?, 'Assigned', 'In Progress', 'Technician acknowledged and accepted work order.');
            """, (task["complaint_id"], worker_user_id))
            cursor.execute("UPDATE complaints SET status = 'In Progress', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (task["complaint_id"],))

        conn.commit()
        CacheInvalidator.on_maintenance_mutation()
        logger.info(f"Maintenance Task #{task_id} Accepted by worker #{worker_user_id}")
        return MaintenanceService.get_task_by_id(conn, task_id)

    @staticmethod
    def start_task(conn: sqlite3.Connection, task_id: int, worker_user_id: int, notes: str = "") -> Dict[str, Any]:
        """Technician marks task as actively In Progress."""
        cursor = conn.cursor()
        task = cursor.execute("SELECT id, status, complaint_id FROM maintenance_tasks WHERE id = ?;", (task_id,)).fetchone()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance task not found.")

        cursor.execute("UPDATE maintenance_tasks SET status = 'In Progress' WHERE id = ?;", (task_id,))
        cursor.execute("""
            INSERT INTO maintenance_history (task_id, updated_by, status, notes)
            VALUES (?, ?, 'In Progress', ?);
        """, (task_id, worker_user_id, notes or "Repair work commenced on-site."))

        if task["complaint_id"]:
            cursor.execute("UPDATE complaints SET status = 'In Progress', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (task["complaint_id"],))
            cursor.execute("""
                INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
                VALUES (?, ?, 'Assigned', 'In Progress', 'Physical repair work in progress.');
            """, (task["complaint_id"], worker_user_id))

        conn.commit()
        CacheInvalidator.on_maintenance_mutation()
        return MaintenanceService.get_task_by_id(conn, task_id)

    @staticmethod
    def update_task_progress(conn: sqlite3.Connection, task_id: int, worker_user_id: int, data: MaintenanceTaskProgress) -> Dict[str, Any]:
        """Record intermediate repair progress notes or spare parts consumption."""
        cursor = conn.cursor()
        task = cursor.execute("SELECT id, status, complaint_id FROM maintenance_tasks WHERE id = ?;", (task_id,)).fetchone()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance task not found.")

        cursor.execute("""
            INSERT INTO maintenance_history (task_id, updated_by, status, notes)
            VALUES (?, ?, ?, ?);
        """, (task_id, worker_user_id, task["status"], data.notes))

        if task["complaint_id"]:
            cursor.execute("""
                INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
                VALUES (?, ?, ?, ?, ?);
            """, (task["complaint_id"], worker_user_id, "In Progress", "In Progress", f"Progress update: {data.notes}"))

        conn.commit()
        return MaintenanceService.get_task_by_id(conn, task_id)

    @staticmethod
    def hold_task(conn: sqlite3.Connection, task_id: int, worker_user_id: int, data: MaintenanceTaskHold) -> Dict[str, Any]:
        """Put maintenance task on hold due to missing parts or access constraints."""
        cursor = conn.cursor()
        task = cursor.execute("SELECT id, status, complaint_id FROM maintenance_tasks WHERE id = ?;", (task_id,)).fetchone()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance task not found.")

        cursor.execute("""
            UPDATE maintenance_tasks
            SET status = 'On Hold', hold_reason = ?
            WHERE id = ?;
        """, (data.hold_reason, task_id))

        notes_combined = f"On Hold: {data.hold_reason}. {data.notes or ''}".strip()
        cursor.execute("""
            INSERT INTO maintenance_history (task_id, updated_by, status, notes)
            VALUES (?, ?, 'On Hold', ?);
        """, (task_id, worker_user_id, notes_combined))

        if task["complaint_id"]:
            cursor.execute("UPDATE complaints SET status = 'On Hold', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (task["complaint_id"],))
            cursor.execute("""
                INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
                VALUES (?, ?, 'In Progress', 'On Hold', ?);
            """, (task["complaint_id"], worker_user_id, notes_combined))

        conn.commit()
        CacheInvalidator.on_maintenance_mutation()
        return MaintenanceService.get_task_by_id(conn, task_id)

    @staticmethod
    def complete_task(conn: sqlite3.Connection, task_id: int, worker_user_id: int, data: MaintenanceTaskComplete) -> Dict[str, Any]:
        """Technician completes repairs and logs materials/cost."""
        cursor = conn.cursor()
        task = cursor.execute("SELECT id, status, complaint_id, task_code, title FROM maintenance_tasks WHERE id = ?;", (task_id,)).fetchone()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance task not found.")

        cursor.execute("""
            UPDATE maintenance_tasks
            SET status = 'Completed',
                resolution_notes = ?,
                actual_cost = ?,
                completion_photo_url = ?,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """, (data.resolution_notes, data.actual_cost, data.completion_photo_url, task_id))

        cursor.execute("""
            INSERT INTO maintenance_history (task_id, updated_by, status, notes)
            VALUES (?, ?, 'Completed', ?);
        """, (task_id, worker_user_id, f"Completed: {data.resolution_notes} (Cost: ₹{data.actual_cost})"))

        if task["complaint_id"]:
            cursor.execute("""
                UPDATE complaints
                SET status = 'Resolved',
                    resolved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (task["complaint_id"],))

            cursor.execute("""
                INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
                VALUES (?, ?, 'In Progress', 'Resolved', ?);
            """, (task["complaint_id"], worker_user_id, f"Repairs completed: {data.resolution_notes}"))

        conn.commit()
        CacheInvalidator.on_maintenance_mutation()
        logger.info(f"Maintenance Task #{task_id} Completed by worker #{worker_user_id}")
        return MaintenanceService.get_task_by_id(conn, task_id)

    @staticmethod
    def verify_task(conn: sqlite3.Connection, task_id: int, verified_by_user_id: int, data: MaintenanceTaskVerify) -> Dict[str, Any]:
        """Warden or Facility Manager inspects repairs, restores infrastructure status, and closes ticket."""
        cursor = conn.cursor()
        task = cursor.execute("""
            SELECT id, status, complaint_id, room_id, task_code
            FROM maintenance_tasks WHERE id = ?;
        """, (task_id,)).fetchone()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance task not found.")

        if data.approved:
            new_status = "Verified"
            cursor.execute("""
                UPDATE maintenance_tasks
                SET status = 'Verified',
                    verified_by = ?,
                    verified_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (verified_by_user_id, task_id))

            cursor.execute("""
                INSERT INTO maintenance_history (task_id, updated_by, status, notes)
                VALUES (?, ?, 'Verified', ?);
            """, (task_id, verified_by_user_id, data.verification_notes or "Quality check verified and approved."))

            # Poka-Yoke release: Restore room and bed from Maintenance back to Available
            if task["room_id"]:
                active_other = cursor.execute("""
                    SELECT COUNT(*) FROM maintenance_tasks
                    WHERE room_id = ? AND id != ? AND status IN ('Assigned', 'Accepted', 'In Progress', 'On Hold');
                """, (task["room_id"], task_id)).fetchone()[0]
                if active_other == 0:
                    cursor.execute("UPDATE rooms SET status = 'Available', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'Maintenance';", (task["room_id"],))
                    cursor.execute("UPDATE beds SET status = 'Available' WHERE room_id = ? AND status = 'Maintenance';", (task["room_id"],))

            if task["complaint_id"]:
                cursor.execute("""
                    UPDATE complaints
                    SET status = 'Closed',
                        closed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                """, (task["complaint_id"],))

                cursor.execute("""
                    INSERT INTO complaint_updates (complaint_id, updated_by, previous_status, new_status, comment)
                    VALUES (?, ?, 'Resolved', 'Closed', ?);
                """, (task["complaint_id"], verified_by_user_id, f"Inspection passed: {data.verification_notes or 'Service quality approved'}. Grievance closed."))

                # Notify student to rate service
                c_row = cursor.execute("SELECT student_id, title FROM complaints WHERE id = ?;", (task["complaint_id"],)).fetchone()
                if c_row:
                    s_user = cursor.execute("SELECT id FROM users WHERE linked_student_id = ?;", (c_row["student_id"],)).fetchone()
                    if s_user:
                        cursor.execute("""
                            INSERT INTO notifications (user_id, title, message, notification_type)
                            VALUES (?, 'Grievance Verified & Closed', ?, 'complaint');
                        """, (
                            s_user["id"],
                            f"Your grievance '{c_row['title']}' has been verified by the Warden and closed. Please submit your satisfaction rating."
                        ))
        else:
            # Rejection / rework required
            new_status = "In Progress"
            cursor.execute("""
                UPDATE maintenance_tasks
                SET status = 'In Progress',
                    resolution_notes = resolution_notes || ' [Rework requested: ' || ? || ']'
                WHERE id = ?;
            """, (data.verification_notes, task_id))

            cursor.execute("""
                INSERT INTO maintenance_history (task_id, updated_by, status, notes)
                VALUES (?, ?, 'In Progress', ?);
            """, (task_id, verified_by_user_id, f"Verification failed. Rework requested: {data.verification_notes}"))

        conn.commit()
        CacheInvalidator.on_maintenance_mutation()
        logger.info(f"Maintenance Task #{task_id} Verified (Approved: {data.approved}) by user #{verified_by_user_id}")
        return MaintenanceService.get_task_by_id(conn, task_id)

    @staticmethod
    def get_staff_availability(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        """Return maintenance staff workload, current task counts, and availability status."""
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT 
                u.id AS user_id, u.username, u.first_name, u.last_name, u.email, u.phone,
                COUNT(CASE WHEN mt.status IN ('Assigned', 'Accepted', 'In Progress', 'On Hold') THEN 1 END) AS active_task_count,
                COUNT(CASE WHEN mt.status = 'Completed' THEN 1 END) AS completed_task_count
            FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            JOIN roles r ON ur.role_id = r.id
            LEFT JOIN maintenance_tasks mt ON u.id = mt.assigned_to
            WHERE r.name = 'maintenance_staff' AND u.is_active = 1
            GROUP BY u.id
            ORDER BY active_task_count ASC, u.first_name ASC;
        """).fetchall()

        staff_list = []
        for r in rows:
            worker = dict(r)
            worker["is_available"] = worker["active_task_count"] < 4
            worker["workload_level"] = "Low" if worker["active_task_count"] < 2 else ("Medium" if worker["active_task_count"] < 4 else "High")
            staff_list.append(worker)

        return staff_list
