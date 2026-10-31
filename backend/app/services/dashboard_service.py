"""Dashboard Aggregation and Metrics Service with Q05 Cache Acceleration.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

import sqlite3
import time
from typing import Any, Dict, List, Optional
from backend.app.services.cache_service import cache_service, make_dashboard_cache_key
from backend.app.utils.logger import logger


class DashboardService:
    """Computes and caches comprehensive operational dashboard metrics with strict multi-tenant isolation."""

    @staticmethod
    def get_dashboard_metrics(
        conn: sqlite3.Connection,
        user_roles: List[str],
        user_id: Optional[int] = None,
        linked_hostel_id: Optional[int] = None,
        linked_student_id: Optional[int] = None,
        requested_hostel_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """Fetch dashboard statistics from in-memory cache, or compute from SQL and cache."""
        t0 = time.perf_counter()

        # 1. Determine effective scope and authorization
        roles = set(user_roles or [])
        primary_role = next(iter(user_roles), "student") if user_roles else "student"

        # Hostel scoping:
        effective_hostel_id: Optional[int] = None
        if roles.intersection({"super_admin", "auditor", "accountant", "admission_officer"}):
            # Privileged roles can query global or specific hostel
            effective_hostel_id = requested_hostel_id
        else:
            # Facility-scoped roles cannot view other hostels
            effective_hostel_id = linked_hostel_id

        cache_key = make_dashboard_cache_key(
            role=primary_role,
            hostel_id=effective_hostel_id,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to
        )

        # 2. Check in-memory cache if not bypassed
        if not bypass_cache:
            cached_data = cache_service.get(cache_key)
            if cached_data is not None:
                duration_ms = round((time.perf_counter() - t0) * 1000, 3)
                cached_copy = dict(cached_data)
                cached_copy["cache_status"] = "HIT"
                cached_copy["execution_time_ms"] = duration_ms
                return cached_copy

        # 3. Compute metrics via optimized SQL aggregates
        metrics = DashboardService._compute_metrics_from_db(
            conn=conn,
            roles=roles,
            primary_role=primary_role,
            hostel_id=effective_hostel_id,
            student_id=linked_student_id,
            date_from=date_from,
            date_to=date_to
        )

        # 4. Associate dependency tags for fine-grained invalidation
        tags = ["dashboard"]
        if effective_hostel_id:
            tags.append(f"hostel_{effective_hostel_id}")
        else:
            tags.append("global")
        tags.extend(["students", "hostels", "rooms", "beds", "allocations", "complaints", "maintenance", "finance", "admissions"])

        # Store in cache (60s TTL)
        cache_service.set(cache_key, metrics, ttl=60.0, tags=tags)

        duration_ms = round((time.perf_counter() - t0) * 1000, 3)
        metrics["cache_status"] = "MISS"
        metrics["execution_time_ms"] = duration_ms

        return metrics

    @staticmethod
    def _compute_metrics_from_db(
        conn: sqlite3.Connection,
        roles: Set[str],
        primary_role: str,
        hostel_id: Optional[int],
        student_id: Optional[int],
        date_from: Optional[str],
        date_to: Optional[str]
    ) -> Dict[str, Any]:
        """Execute optimized, parameterized aggregate SQL queries with indexed conditions."""
        cursor = conn.cursor()

        # 1. Hostels & Infrastructure Capacity
        if hostel_id is not None:
            # Single hostel facility scope
            cursor.execute("SELECT COUNT(*) FROM hostels WHERE id = ?;", (hostel_id,))
            total_hostels = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM buildings WHERE hostel_id = ?;", (hostel_id,))
            total_buildings = cursor.fetchone()[0]

            cursor.execute("""
                SELECT 
                    COUNT(r.id) AS total_rooms,
                    COUNT(bd.id) AS total_beds,
                    SUM(CASE WHEN bd.status = 'Occupied' THEN 1 ELSE 0 END) AS occupied_beds,
                    SUM(CASE WHEN bd.status = 'Available' THEN 1 ELSE 0 END) AS available_beds
                FROM rooms r
                JOIN floors f ON r.floor_id = f.id
                JOIN buildings b ON f.building_id = b.id
                LEFT JOIN beds bd ON bd.room_id = r.id
                WHERE b.hostel_id = ?;
            """, (hostel_id,))
            room_stats = cursor.fetchone()
            total_rooms = room_stats[0] or 0
            total_beds = room_stats[1] or 0
            occupied_beds = room_stats[2] or 0
            available_beds = room_stats[3] or 0

        else:
            # Global institution scope
            cursor.execute("SELECT COUNT(*) FROM hostels;")
            total_hostels = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM buildings;")
            total_buildings = cursor.fetchone()[0]

            cursor.execute("""
                SELECT 
                    COUNT(r.id) AS total_rooms,
                    COUNT(bd.id) AS total_beds,
                    SUM(CASE WHEN bd.status = 'Occupied' THEN 1 ELSE 0 END) AS occupied_beds,
                    SUM(CASE WHEN bd.status = 'Available' THEN 1 ELSE 0 END) AS available_beds
                FROM rooms r
                LEFT JOIN beds bd ON bd.room_id = r.id;
            """)
            room_stats = cursor.fetchone()
            total_rooms = room_stats[0] or 0
            total_beds = room_stats[1] or 0
            occupied_beds = room_stats[2] or 0
            available_beds = room_stats[3] or 0

        occupancy_rate = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0.0

        # 2. Students (Active vs Inactive)
        if hostel_id is not None:
            cursor.execute("""
                SELECT 
                    COUNT(s.id) AS total_students,
                    SUM(CASE WHEN s.status = 'Active' THEN 1 ELSE 0 END) AS active_students
                FROM students s
                JOIN room_allocations ra ON ra.student_id = s.id
                JOIN rooms r ON ra.room_id = r.id
                JOIN floors f ON r.floor_id = f.id
                JOIN buildings b ON f.building_id = b.id
                WHERE b.hostel_id = ? AND ra.allocation_status = 'Active';
            """, (hostel_id,))
            stud_stats = cursor.fetchone()
            total_students = stud_stats[0] or 0
            active_students = stud_stats[1] or 0
        else:
            cursor.execute("""
                SELECT 
                    COUNT(id) AS total_students,
                    SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) AS active_students
                FROM students;
            """)
            stud_stats = cursor.fetchone()
            total_students = stud_stats[0] or 0
            active_students = stud_stats[1] or 0

        # 3. Complaints (Pending vs Resolved)
        if hostel_id is not None:
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN c.status IN ('Open', 'In_Progress') THEN 1 ELSE 0 END) AS pending_complaints,
                    SUM(CASE WHEN c.status = 'Resolved' THEN 1 ELSE 0 END) AS resolved_complaints
                FROM complaints c
                JOIN rooms r ON c.room_id = r.id
                JOIN floors f ON r.floor_id = f.id
                JOIN buildings b ON f.building_id = b.id
                WHERE b.hostel_id = ?;
            """, (hostel_id,))
            comp_stats = cursor.fetchone()
            pending_complaints = comp_stats[0] or 0
            resolved_complaints = comp_stats[1] or 0
        else:
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN status IN ('Open', 'In_Progress') THEN 1 ELSE 0 END) AS pending_complaints,
                    SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) AS resolved_complaints
                FROM complaints;
            """)
            comp_stats = cursor.fetchone()
            pending_complaints = comp_stats[0] or 0
            resolved_complaints = comp_stats[1] or 0

        # 4. Maintenance Tasks
        if hostel_id is not None:
            cursor.execute("""
                SELECT COUNT(mt.id) 
                FROM maintenance_tasks mt
                JOIN buildings b ON mt.building_id = b.id
                WHERE b.hostel_id = ? AND mt.status IN ('Pending', 'Assigned');
            """, (hostel_id,))
            pending_maintenance = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT COUNT(*) FROM maintenance_tasks WHERE status IN ('Pending', 'Assigned');")
            pending_maintenance = cursor.fetchone()[0]

        # 5. Financial Management (Total Collections vs Outstanding Fees)
        # Note: If student role, finance is hidden or restricted to own dues
        if "student" in roles and not roles.intersection({"super_admin", "accountant", "hostel_admin"}):
            total_collections = 0.0
            outstanding_fees = 0.0
            if student_id:
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(inv.total_amount), 0),
                        COALESCE(SUM(p.amount), 0)
                    FROM invoices inv
                    LEFT JOIN payments p ON p.invoice_id = inv.id AND p.status = 'Completed'
                    WHERE inv.student_id = ?;
                """, (student_id,))
                f_row = cursor.fetchone()
                total_invoiced = f_row[0] or 0.0
                total_collections = f_row[1] or 0.0
                outstanding_fees = max(0.0, total_invoiced - total_collections)
        else:
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(total_amount), 0)
                FROM invoices;
            """)
            total_invoiced = cursor.fetchone()[0] or 0.0

            cursor.execute("""
                SELECT 
                    COALESCE(SUM(amount), 0)
                FROM payments
                WHERE status = 'Completed';
            """)
            total_collections = cursor.fetchone()[0] or 0.0
            outstanding_fees = max(0.0, total_invoiced - total_collections)

        # 6. Admission Applications (Pending)
        cursor.execute("SELECT COUNT(*) FROM admission_applications WHERE application_status = 'Submitted';")
        pending_admissions = cursor.fetchone()[0]

        # 7. Recent Logins
        cursor.execute("""
            SELECT id, username_or_email_attempted, status, timestamp
            FROM login_history
            ORDER BY id DESC
            LIMIT 5;
        """)
        recent_logins = [dict(r) for r in cursor.fetchall()]

        return {
            "scope": {
                "role": primary_role,
                "hostel_id": hostel_id,
                "is_global": hostel_id is None
            },
            "metrics": {
                "total_students": total_students,
                "active_students": active_students,
                "total_hostels": total_hostels,
                "total_buildings": total_buildings,
                "total_rooms": total_rooms,
                "total_beds": total_beds,
                "occupied_beds": occupied_beds,
                "available_beds": available_beds,
                "hostel_occupancy_percentage": occupancy_rate,
                "pending_complaints": pending_complaints,
                "resolved_complaints": resolved_complaints,
                "pending_maintenance_tasks": pending_maintenance,
                "total_fee_collections": round(total_collections, 2),
                "outstanding_fees": round(outstanding_fees, 2),
                "pending_admission_applications": pending_admissions
            },
            # Compatibility structure for existing dashboards
            "hostels": {
                "total": total_hostels,
                "buildings": total_buildings,
                "rooms": total_rooms,
                "beds": total_beds,
                "occupied_beds": occupied_beds,
                "available_beds": available_beds,
                "occupancy_rate": occupancy_rate
            },
            "students": {
                "total": total_students,
                "active": active_students
            },
            "finance": {
                "total_collected": round(total_collections, 2),
                "outstanding_dues": round(outstanding_fees, 2)
            },
            "operations": {
                "pending_complaints": pending_complaints,
                "resolved_complaints": resolved_complaints,
                "pending_maintenance": pending_maintenance,
                "pending_admissions": pending_admissions
            },
            "recent_activity": recent_logins
        }
