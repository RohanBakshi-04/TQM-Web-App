"""Dashboard Aggregation and Metrics Service with Q05 Cache Acceleration.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

import datetime
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Set
from backend.app.database.connection import get_db_path
from backend.app.services.cache_service import cache_service, make_dashboard_cache_key
from backend.app.utils.logger import logger
from backend.app.services.database_integrity_service import integrity_monitor



_last_integrity_check = None
_last_integrity_check_time = 0.0

def _get_database_integrity(conn: sqlite3.Connection) -> str:
    """Cached database integrity diagnostic (PRAGMA quick_check) with 300s TTL to prevent page-scan overhead."""
    global _last_integrity_check, _last_integrity_check_time
    now = time.time()
    if _last_integrity_check is not None and (now - _last_integrity_check_time) < 300.0:
        return _last_integrity_check.get("status", "ok")
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA quick_check(1);")
        res = str(cur.fetchone()[0]).lower()
        _last_integrity_check = {"status": res}
        _last_integrity_check_time = now
        return res
    except Exception:
        return "ok"

def _clean_date_iso(val):
    if not val or not str(val).strip():
        return None
    val_str = str(val).strip()
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(val_str.split("T")[0])
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


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
                    COUNT(DISTINCT r.id) AS total_rooms,
                    COUNT(DISTINCT bd.id) AS total_beds,
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
                    COUNT(DISTINCT r.id) AS total_rooms,
                    COUNT(DISTINCT bd.id) AS total_beds,
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

    @staticmethod
    def get_super_admin_executive_metrics(
        conn: sqlite3.Connection,
        user_roles: Optional[List[str]] = None,
        user_id: Optional[int] = None,
        academic_session: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        campus: Optional[str] = None,
        hostel_id: Optional[int] = None,
        department: Optional[str] = None,
        bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """Fetch SA-01 Super Admin Executive Overview with Q05 in-memory caching (<10ms SLA)."""
        t0 = time.perf_counter()

        # Sanitize filter inputs with Poka-Yoke validation
        clean_campus = campus.strip() if campus and campus.strip() and campus.lower() != "all" else None
        clean_dept = department.strip() if department and department.strip() and department.lower() != "all" else None
        clean_session = academic_session.strip() if academic_session and academic_session.strip() and academic_session.lower() != "all" else None
        clean_date_from = _clean_date_iso(date_from)
        clean_date_to = _clean_date_iso(date_to)

        primary_role = next(iter(user_roles or []), "super_admin")
        cache_key = f"sa_executive_{primary_role}_{hostel_id}_{clean_campus}_{clean_dept}_{clean_session}_{clean_date_from}_{clean_date_to}"

        if not bypass_cache:
            cached_data = cache_service.get(cache_key)
            if cached_data is not None:
                duration_ms = round((time.perf_counter() - t0) * 1000, 3)
                cached_copy = dict(cached_data)
                cached_copy["metadata"] = dict(cached_copy.get("metadata", {}))
                cached_copy["metadata"]["cache_status"] = "HIT"
                cached_copy["metadata"]["execution_time_ms"] = duration_ms
                return cached_copy

        metrics = DashboardService._compute_super_admin_executive_metrics(
            conn=conn,
            academic_session=clean_session,
            date_from=clean_date_from,
            date_to=clean_date_to,
            campus=clean_campus,
            hostel_id=hostel_id,
            department=clean_dept
        )

        tags = [
            "dashboard", "executive", "global",
            "students", "hostels", "buildings", "rooms", "beds",
            "allocations", "complaints", "maintenance", "finance",
            "admissions", "visitors", "leaves"
        ]
        if hostel_id:
            tags.append(f"hostel_{hostel_id}")
        cache_service.set(cache_key, metrics, ttl=30.0, tags=tags)

        duration_ms = round((time.perf_counter() - t0) * 1000, 3)
        metrics["metadata"]["cache_status"] = "MISS"
        metrics["metadata"]["execution_time_ms"] = duration_ms
        return metrics

    @staticmethod
    def _compute_super_admin_executive_metrics(
        conn: sqlite3.Connection,
        academic_session: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        campus: Optional[str] = None,
        hostel_id: Optional[int] = None,
        department: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compute institutional executive overview telemetry across all 13 core operational sections."""
        cursor = conn.cursor()

        # ------------------------------------------------------------------
        # 1. Section A: Metadata, Institution Settings & Sync State
        # ------------------------------------------------------------------
        settings_map: Dict[str, str] = {}
        try:
            cursor.execute("SELECT setting_key, setting_value FROM system_settings;")
            for row in cursor.fetchall():
                settings_map[row["setting_key"]] = row["setting_value"]
        except Exception:
            pass

        institution_name = settings_map.get("institution_name", "University College of Engineering")
        active_session = academic_session or settings_map.get("academic_session", "2026-27")
        currency_symbol = settings_map.get("currency_symbol", "₹")
        institution_contact = settings_map.get("institution_contact", "+91-20-25507000, contact@uce.edu.in")
        server_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ------------------------------------------------------------------
        # 2. Section G & B: Infrastructure, Capacity & Hierarchy
        # ------------------------------------------------------------------
        campus_pattern = f"%{campus}%" if campus else None
        cursor.execute("""
            SELECT 
                h.id, h.name, h.code, h.hostel_type, h.address, h.is_active,
                COUNT(DISTINCT b.id) AS buildings_count,
                COUNT(DISTINCT f.id) AS floors_count,
                COUNT(DISTINCT r.id) AS rooms_count,
                COUNT(DISTINCT bd.id) AS total_beds,
                SUM(CASE WHEN bd.status = 'Occupied' THEN 1 ELSE 0 END) AS occupied_beds,
                SUM(CASE WHEN bd.status = 'Available' THEN 1 ELSE 0 END) AS available_beds,
                SUM(CASE WHEN bd.status = 'Maintenance' THEN 1 ELSE 0 END) AS maintenance_beds
            FROM hostels h
            LEFT JOIN buildings b ON b.hostel_id = h.id
            LEFT JOIN floors f ON f.building_id = b.id
            LEFT JOIN rooms r ON r.floor_id = f.id
            LEFT JOIN beds bd ON bd.room_id = r.id
            WHERE (? IS NULL OR h.id = ?)
              AND (? IS NULL OR h.address LIKE ?)
            GROUP BY h.id
            ORDER BY h.id ASC;
        """, (hostel_id, hostel_id, campus_pattern, campus_pattern))

        hostels_list: List[Dict[str, Any]] = []
        campus_names: Set[str] = set()
        for row in cursor.fetchall():
            h_dict = dict(row)
            t_beds = h_dict["total_beds"] or 0
            o_beds = h_dict["occupied_beds"] or 0
            m_beds = h_dict["maintenance_beds"] or 0
            a_beds = h_dict["available_beds"] or 0
            h_dict["occupancy_rate_pct"] = round((o_beds / t_beds * 100.0), 1) if t_beds > 0 else 0.0
            
            # Resolve campus
            addr = h_dict.get("address") or ""
            if "North" in addr:
                c_name = "North Campus"
            elif "South" in addr:
                c_name = "South Campus"
            else:
                c_name = "Main Campus"
            h_dict["campus"] = c_name
            campus_names.add(c_name)
            hostels_list.append(h_dict)

        total_hostels = len(hostels_list)
        total_buildings = sum(h["buildings_count"] for h in hostels_list)
        total_floors = sum(h["floors_count"] for h in hostels_list)
        total_rooms = sum(h["rooms_count"] for h in hostels_list)
        total_beds = sum(h["total_beds"] for h in hostels_list)
        occupied_beds = sum(h["occupied_beds"] for h in hostels_list)
        available_beds = sum(h["available_beds"] for h in hostels_list)
        maintenance_beds = sum(h["maintenance_beds"] for h in hostels_list)
        overall_occupancy_rate = round((occupied_beds / total_beds * 100.0), 1) if total_beds > 0 else 0.0
        campuses_count = len(campus_names)

        # ------------------------------------------------------------------
        # 3. Section C: Critical KPI Grid (Students, Users, Roles, Admissions)
        # ------------------------------------------------------------------
        # Deduplicated student metrics with facility, campus, and session isolation
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT s.id) AS total_students,
                COUNT(DISTINCT CASE WHEN s.status = 'Active' THEN s.id ELSE NULL END) AS active_students,
                COUNT(DISTINCT CASE WHEN s.status != 'Active' THEN s.id ELSE NULL END) AS inactive_students,
                COUNT(DISTINCT CASE WHEN s.status = 'Pending' THEN s.id ELSE NULL END) AS pending_students,
                COUNT(DISTINCT CASE WHEN s.status = 'Withdrawn' THEN s.id ELSE NULL END) AS withdrawn_students
            FROM students s
            LEFT JOIN users u ON s.user_id = u.id
            LEFT JOIN (
                SELECT student_id, room_id FROM room_allocations WHERE allocation_status = 'Active' GROUP BY student_id
            ) ra ON ra.student_id = s.id
            LEFT JOIN rooms r ON ra.room_id = r.id
            LEFT JOIN floors f ON r.floor_id = f.id
            LEFT JOIN buildings b ON f.building_id = b.id
            LEFT JOIN hostels h ON h.id = COALESCE(b.hostel_id, u.linked_hostel_id)
            WHERE (? IS NULL OR h.id = ?)
              AND (? IS NULL OR h.address LIKE ?)
              AND (? IS NULL OR s.academic_year = ? OR s.academic_year LIKE ?);
        """, (hostel_id, hostel_id, campus_pattern, campus_pattern, academic_session, academic_session, f"%{academic_session}%" if academic_session else None))
        s_row = cursor.fetchone()
        total_students = s_row[0] or 0
        active_students = s_row[1] or 0
        inactive_students = s_row[2] or 0
        pending_students = s_row[3] or 0
        withdrawn_students = s_row[4] or 0
        student_retention_rate = round((active_students / total_students * 100.0), 1) if total_students > 0 else 100.0

        # System Users (scoped by department if requested)
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT u.id) AS total_users,
                COUNT(DISTINCT CASE WHEN u.is_active = 1 THEN u.id ELSE NULL END) AS active_users,
                COUNT(DISTINCT CASE WHEN u.is_active = 0 THEN u.id ELSE NULL END) AS inactive_users
            FROM users u
            LEFT JOIN user_departments ud ON ud.user_id = u.id
            LEFT JOIN departments d ON ud.department_id = d.id
            WHERE (? IS NULL OR d.code = ? OR d.name = ?);
        """, (department, department, department))
        u_row = cursor.fetchone()
        total_users = u_row[0] or 0
        active_users = u_row[1] or 0
        inactive_users = u_row[2] or 0

        # Actual database counts (Zero fabricated fallbacks)
        cursor.execute("SELECT COUNT(*) FROM roles;")
        r_cnt = cursor.fetchone()
        total_roles = int(r_cnt[0] if r_cnt and r_cnt[0] is not None else 0)

        cursor.execute("SELECT COUNT(*) FROM dashboards;")
        d_cnt = cursor.fetchone()
        total_dashboards = int(d_cnt[0] if d_cnt and d_cnt[0] is not None else 0)

        # Admission Applications
        cursor.execute("""
            SELECT 
                COUNT(id) AS total_applications,
                SUM(CASE WHEN application_status = 'Submitted' THEN 1 ELSE 0 END) AS submitted_apps,
                SUM(CASE WHEN application_status = 'Under_Review' THEN 1 ELSE 0 END) AS under_review_apps,
                SUM(CASE WHEN application_status = 'Approved' THEN 1 ELSE 0 END) AS approved_apps,
                SUM(CASE WHEN application_status = 'Rejected' THEN 1 ELSE 0 END) AS rejected_apps
            FROM admission_applications
            WHERE (? IS NULL OR academic_year = ? OR academic_year LIKE ?);
        """, (academic_session, academic_session, f"%{academic_session}%" if academic_session else None))
        adm_row = cursor.fetchone()
        total_admissions = adm_row[0] or 0
        submitted_admissions = adm_row[1] or 0
        under_review_admissions = adm_row[2] or 0
        approved_admissions = adm_row[3] or 0
        rejected_admissions = adm_row[4] or 0
        admission_conversion_rate = round((approved_admissions / total_admissions * 100.0), 1) if total_admissions > 0 else 0.0

        # Branch & Gender breakdown for admission overview
        cursor.execute("""
            SELECT COALESCE(branch, 'General') AS branch_name, COUNT(*) AS count
            FROM students
            GROUP BY branch
            ORDER BY count DESC
            LIMIT 5;
        """, ())
        branch_distribution = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT COALESCE(gender, 'Unspecified') AS gender_name, COUNT(*) AS count
            FROM students
            GROUP BY gender;
        """, ())
        gender_distribution = {r["gender_name"]: r["count"] for r in cursor.fetchall()}

        # ------------------------------------------------------------------
        # 4. Section D: Operational Performance (Complaints, Maintenance, Leaves, Visitors, Security)
        # ------------------------------------------------------------------
        # Complaints (scoped by hostel, campus, and date range)
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT c.id) AS total_complaints,
                COUNT(DISTINCT CASE WHEN c.status IN ('Open', 'In_Progress', 'Submitted', 'Escalated') THEN c.id ELSE NULL END) AS open_complaints,
                COUNT(DISTINCT CASE WHEN c.status IN ('Resolved', 'Closed') THEN c.id ELSE NULL END) AS resolved_complaints,
                COUNT(DISTINCT CASE WHEN (c.severity IN ('High', 'Critical', 'Emergency') OR c.escalated = 1) AND c.status IN ('Open', 'In_Progress', 'Submitted', 'Escalated') THEN c.id ELSE NULL END) AS high_critical_open
            FROM complaints c
            LEFT JOIN rooms r ON c.room_id = r.id
            LEFT JOIN floors f ON r.floor_id = f.id
            LEFT JOIN buildings b ON f.building_id = b.id
            LEFT JOIN hostels h ON b.hostel_id = h.id
            WHERE (? IS NULL OR h.id = ?)
              AND (? IS NULL OR h.address LIKE ?)
              AND (? IS NULL OR date(c.created_at) >= date(?))
              AND (? IS NULL OR date(c.created_at) <= date(?));
        """, (hostel_id, hostel_id, campus_pattern, campus_pattern, date_from, date_from, date_to, date_to))
        comp_row = cursor.fetchone()
        total_complaints = comp_row[0] or 0
        open_complaints = comp_row[1] or 0
        resolved_complaints = comp_row[2] or 0
        high_critical_complaints = comp_row[3] or 0
        complaint_resolution_rate = round((resolved_complaints / total_complaints * 100.0), 1) if total_complaints > 0 else 100.0

        # Maintenance (scoped by hostel, campus, and date range)
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT m.id) AS total_maintenance,
                COUNT(DISTINCT CASE WHEN m.status IN ('Pending', 'Assigned') THEN m.id ELSE NULL END) AS pending_maintenance,
                COUNT(DISTINCT CASE WHEN m.status = 'Completed' THEN m.id ELSE NULL END) AS completed_maintenance,
                COUNT(DISTINCT CASE WHEN m.priority IN ('High', 'Critical', 'Emergency', 'Urgent') AND m.status IN ('Pending', 'Assigned') THEN m.id ELSE NULL END) AS emergency_maintenance
            FROM maintenance_tasks m
            LEFT JOIN buildings b ON m.building_id = b.id
            LEFT JOIN hostels h ON b.hostel_id = h.id
            WHERE (? IS NULL OR h.id = ?)
              AND (? IS NULL OR h.address LIKE ?)
              AND (? IS NULL OR date(m.created_at) >= date(?))
              AND (? IS NULL OR date(m.created_at) <= date(?));
        """, (hostel_id, hostel_id, campus_pattern, campus_pattern, date_from, date_from, date_to, date_to))
        maint_row = cursor.fetchone()
        total_maintenance = maint_row[0] or 0
        pending_maintenance = maint_row[1] or 0
        completed_maintenance = maint_row[2] or 0
        emergency_maintenance = maint_row[3] or 0
        maintenance_completion_rate = round((completed_maintenance / total_maintenance * 100.0), 1) if total_maintenance > 0 else 100.0

        # Leaves & Outpasses (scoped by hostel, campus, and date range)
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT lr.id) AS active_leaves
            FROM leave_requests lr
            LEFT JOIN students s ON lr.student_id = s.id
            LEFT JOIN users u ON s.user_id = u.id
            LEFT JOIN (
                SELECT student_id, room_id FROM room_allocations WHERE allocation_status = 'Active' GROUP BY student_id
            ) ra ON ra.student_id = s.id
            LEFT JOIN rooms r ON ra.room_id = r.id
            LEFT JOIN floors f ON r.floor_id = f.id
            LEFT JOIN buildings b ON f.building_id = b.id
            LEFT JOIN hostels h ON h.id = COALESCE(b.hostel_id, u.linked_hostel_id)
            WHERE lr.status IN ('Submitted', 'Pending', 'Approved')
              AND (? IS NULL OR h.id = ?)
              AND (? IS NULL OR h.address LIKE ?)
              AND (? IS NULL OR date(lr.created_at) >= date(?))
              AND (? IS NULL OR date(lr.created_at) <= date(?));
        """, (hostel_id, hostel_id, campus_pattern, campus_pattern, date_from, date_from, date_to, date_to))
        active_leaves = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT 
                COUNT(DISTINCT op.id) AS active_outpasses,
                COUNT(DISTINCT CASE WHEN op.actual_return_time IS NULL AND datetime('now') > datetime(op.expected_return_time) THEN op.id ELSE NULL END) AS overdue_outpasses
            FROM outpasses op
            LEFT JOIN students s ON op.student_id = s.id
            LEFT JOIN users u ON s.user_id = u.id
            LEFT JOIN (
                SELECT student_id, room_id FROM room_allocations WHERE allocation_status = 'Active' GROUP BY student_id
            ) ra ON ra.student_id = s.id
            LEFT JOIN rooms r ON ra.room_id = r.id
            LEFT JOIN floors f ON r.floor_id = f.id
            LEFT JOIN buildings b ON f.building_id = b.id
            LEFT JOIN hostels h ON h.id = COALESCE(b.hostel_id, u.linked_hostel_id)
            WHERE (? IS NULL OR h.id = ?)
              AND (? IS NULL OR h.address LIKE ?)
              AND (? IS NULL OR date(op.created_at) >= date(?))
              AND (? IS NULL OR date(op.created_at) <= date(?));
        """, (hostel_id, hostel_id, campus_pattern, campus_pattern, date_from, date_from, date_to, date_to))
        op_row = cursor.fetchone()
        active_outpasses = op_row[0] or 0
        overdue_outpasses = op_row[1] or 0

        # Visitors (scoped by hostel, campus, and date range)
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT v.id) AS total_visitors,
                COUNT(DISTINCT CASE WHEN v.status = 'Checked_In' THEN v.id ELSE NULL END) AS active_inside,
                COUNT(DISTINCT CASE WHEN v.status = 'Checked_In' AND (v.check_out_time IS NULL AND datetime('now') > datetime(v.check_in_time, '+12 hours')) THEN v.id ELSE NULL END) AS overdue_visitors
            FROM visitor_logs v
            LEFT JOIN hostels h ON v.hostel_id = h.id
            WHERE (? IS NULL OR h.id = ?)
              AND (? IS NULL OR h.address LIKE ?)
              AND (? IS NULL OR date(v.check_in_time) >= date(?))
              AND (? IS NULL OR date(v.check_in_time) <= date(?));
        """, (hostel_id, hostel_id, campus_pattern, campus_pattern, date_from, date_from, date_to, date_to))
        vis_row = cursor.fetchone()
        total_visitors = vis_row[0] or 0
        active_inside_visitors = vis_row[1] or 0
        overdue_visitors = vis_row[2] or 0

        # Security Daily Verifications
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM outpasses WHERE date(actual_exit_time) = date('now') OR date(actual_return_time) = date('now')) +
                (SELECT COUNT(*) FROM visitor_logs WHERE date(check_in_time) = date('now') OR date(check_out_time) = date('now'));
        """, ())
        security_verifications_today = cursor.fetchone()[0] or 0

        # ------------------------------------------------------------------
        # 5. Section E: Authoritative Integer-Paise Financial Overview
        # ------------------------------------------------------------------
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN inv.status != 'Cancelled' THEN inv.total_amount_paise ELSE 0 END), 0) AS total_invoiced_paise,
                COALESCE(SUM(CASE WHEN inv.status != 'Cancelled' THEN inv.paid_amount_paise ELSE 0 END), 0) AS total_paid_paise
            FROM invoices inv
            LEFT JOIN students s ON inv.student_id = s.id
            LEFT JOIN users u ON s.user_id = u.id
            LEFT JOIN (
                SELECT student_id, room_id FROM room_allocations WHERE allocation_status = 'Active' GROUP BY student_id
            ) ra ON ra.student_id = s.id
            LEFT JOIN rooms r ON ra.room_id = r.id
            LEFT JOIN floors f ON r.floor_id = f.id
            LEFT JOIN buildings b ON f.building_id = b.id
            LEFT JOIN hostels h ON h.id = COALESCE(b.hostel_id, u.linked_hostel_id)
            WHERE (? IS NULL OR h.id = ?)
              AND (? IS NULL OR h.address LIKE ?)
              AND (? IS NULL OR date(inv.created_at) >= date(?))
              AND (? IS NULL OR date(inv.created_at) <= date(?));
        """, (hostel_id, hostel_id, campus_pattern, campus_pattern, date_from, date_from, date_to, date_to))
        inv_row = cursor.fetchone()
        total_invoiced_paise = inv_row[0] or 0

        cursor.execute("""
            SELECT COALESCE(SUM(p.amount_paise), 0) AS total_collected_paise
            FROM payments p
            LEFT JOIN invoices inv ON p.invoice_id = inv.id
            LEFT JOIN students s ON p.student_id = s.id
            LEFT JOIN users u ON s.user_id = u.id
            LEFT JOIN (
                SELECT student_id, room_id FROM room_allocations WHERE allocation_status = 'Active' GROUP BY student_id
            ) ra ON ra.student_id = s.id
            LEFT JOIN rooms r ON ra.room_id = r.id
            LEFT JOIN floors f ON r.floor_id = f.id
            LEFT JOIN buildings b ON f.building_id = b.id
            LEFT JOIN hostels h ON h.id = COALESCE(b.hostel_id, u.linked_hostel_id)
            WHERE p.status = 'Completed'
              AND (? IS NULL OR h.id = ?)
              AND (? IS NULL OR h.address LIKE ?)
              AND (? IS NULL OR date(p.payment_date) >= date(?))
              AND (? IS NULL OR date(p.payment_date) <= date(?));
        """, (hostel_id, hostel_id, campus_pattern, campus_pattern, date_from, date_from, date_to, date_to))
        pay_row = cursor.fetchone()
        total_collected_paise = pay_row[0] or 0

        outstanding_dues_paise = max(0, total_invoiced_paise - total_collected_paise)
        collection_efficiency_pct = round((total_collected_paise / total_invoiced_paise * 100.0), 1) if total_invoiced_paise > 0 else 0.0

        cursor.execute("""
            SELECT status, COUNT(*) AS count
            FROM payments
            GROUP BY status;
        """, ())
        pay_status_counts = {r["status"]: r["count"] for r in cursor.fetchall()}

        # Monthly collection trend (last 6 months)
        cursor.execute("""
            SELECT 
                strftime('%Y-%m', payment_date) AS month,
                COALESCE(SUM(amount_paise), 0) AS collected_paise,
                COUNT(id) AS payment_count
            FROM payments
            WHERE status = 'Completed' AND payment_date IS NOT NULL
            GROUP BY strftime('%Y-%m', payment_date)
            ORDER BY month ASC
            LIMIT 6;
        """, ())
        monthly_trend = []
        for r in cursor.fetchall():
            c_paise = r["collected_paise"] or 0
            monthly_trend.append({
                "month": r["month"],
                "collected_inr": round(c_paise / 100.0, 2),
                "payment_count": r["payment_count"]
            })

        # Hostel-wise fee breakdown
        cursor.execute("""
            SELECT 
                h.id AS hostel_id, h.name AS hostel_name,
                COALESCE(SUM(CASE WHEN inv.status != 'Cancelled' THEN inv.total_amount_paise ELSE 0 END), 0) AS invoiced_paise,
                COALESCE(SUM(CASE WHEN inv.status != 'Cancelled' THEN inv.paid_amount_paise ELSE 0 END), 0) AS collected_paise
            FROM hostels h
            LEFT JOIN buildings b ON b.hostel_id = h.id
            LEFT JOIN floors f ON f.building_id = b.id
            LEFT JOIN rooms r ON r.floor_id = f.id
            LEFT JOIN room_allocations ra ON ra.room_id = r.id AND ra.allocation_status = 'Active'
            LEFT JOIN invoices inv ON inv.student_id = ra.student_id
            GROUP BY h.id
            ORDER BY h.id ASC;
        """, ())
        hostel_financials = []
        for r in cursor.fetchall():
            inv_p = r["invoiced_paise"] or 0
            col_p = r["collected_paise"] or 0
            hostel_financials.append({
                "hostel_id": r["hostel_id"],
                "hostel_name": r["hostel_name"],
                "invoiced_inr": round(inv_p / 100.0, 2),
                "collected_inr": round(col_p / 100.0, 2),
                "dues_inr": round(max(0, inv_p - col_p) / 100.0, 2)
            })

        # ------------------------------------------------------------------
        # 6. Section H: Workforce & 17 Departments Overview
        # ------------------------------------------------------------------
        cursor.execute("""
            SELECT 
                d.id AS department_id, d.code, d.name, d.description,
                COUNT(DISTINCT ud.user_id) AS staff_count,
                COUNT(DISTINCT CASE WHEN u.is_active = 1 THEN u.id ELSE NULL END) AS active_count
            FROM departments d
            LEFT JOIN user_departments ud ON ud.department_id = d.id
            LEFT JOIN users u ON u.id = ud.user_id
            WHERE (? IS NULL OR d.code = ? OR d.name = ?)
            GROUP BY d.id
            ORDER BY d.id ASC;
        """, (department, department, department))
        dept_rows = cursor.fetchall()
        total_departments_count = len(dept_rows)
        total_staff_in_depts = sum(r["staff_count"] for r in dept_rows)
        active_staff_in_depts = sum(r["active_count"] for r in dept_rows)

        department_distribution = []
        for r in dept_rows:
            sc = r["staff_count"] or 0
            ac = r["active_count"] or 0
            pct = round((sc / total_staff_in_depts * 100.0), 1) if total_staff_in_depts > 0 else 0.0
            department_distribution.append({
                "department_id": r["department_id"],
                "code": r["code"],
                "name": r["name"],
                "description": r["description"] or "",
                "staff_count": sc,
                "active_count": ac,
                "pct_of_total": pct
            })

        # ------------------------------------------------------------------
        # 7. Section K: Real-Time Critical Alert Center
        # ------------------------------------------------------------------
        cursor.execute("SELECT COUNT(*) FROM registration_requests WHERE status = 'Pending';")
        pending_registrations = cursor.fetchone()[0] or 0

        critical_alerts = []
        if overdue_visitors > 0:
            critical_alerts.append({
                "severity": "critical",
                "type": "visitor_overstay",
                "title": "Overdue Campus Visitors",
                "message": f"{overdue_visitors} visitor log(s) currently marked inside past departure limit.",
                "action_label": "Review Visitors",
                "action_tab": "visitors"
            })
        if overdue_outpasses > 0:
            critical_alerts.append({
                "severity": "critical",
                "type": "outpass_overdue",
                "title": "Overdue Student Outpasses",
                "message": f"{overdue_outpasses} student outpass(es) unverified past expected campus check-in.",
                "action_label": "Gate Control",
                "action_tab": "leaves"
            })
        if high_critical_complaints > 0:
            critical_alerts.append({
                "severity": "high",
                "type": "critical_complaint",
                "title": "High Priority Grievances",
                "message": f"{high_critical_complaints} urgent/critical safety or facility complaint(s) require intervention.",
                "action_label": "View Complaints",
                "action_tab": "complaints"
            })
        if emergency_maintenance > 0:
            critical_alerts.append({
                "severity": "high",
                "type": "emergency_maintenance",
                "title": "Urgent Maintenance Work Orders",
                "message": f"{emergency_maintenance} critical equipment/infrastructure task(s) unassigned or pending.",
                "action_label": "Maintenance Desk",
                "action_tab": "maintenance"
            })
        if pending_registrations > 0:
            critical_alerts.append({
                "severity": "medium",
                "type": "pending_registrations",
                "title": "Pending Account Registrations",
                "message": f"{pending_registrations} applicant verification request(s) awaiting administrative approval.",
                "action_label": "Approvals Center",
                "action_tab": "registrations"
            })
        if not critical_alerts:
            critical_alerts.append({
                "severity": "low",
                "type": "all_clear",
                "title": "All Systems Normal",
                "message": "No critical security, maintenance, or overdue curfew alerts active across campus.",
                "action_label": "Audit Logs",
                "action_tab": "audit_logs"
            })

        # ------------------------------------------------------------------
        # 8. Section J: Live Activity Center (Real SQLite `audit_logs`)
        # ------------------------------------------------------------------
        cursor.execute("""
            SELECT id, user_id, username, action, entity_name, entity_id, details, ip_address, latency_ms, created_at
            FROM audit_logs
            WHERE (? IS NULL OR date(created_at) >= date(?))
              AND (? IS NULL OR date(created_at) <= date(?))
            ORDER BY id DESC
            LIMIT 15;
        """, (date_from, date_from, date_to, date_to))
        recent_activity_logs = [dict(r) for r in cursor.fetchall()]

        # ------------------------------------------------------------------
        # 9. Section M: System Health Telemetry & Database Integrity Freshness
        # ------------------------------------------------------------------
        journal_mode = "unknown"
        integrity_diag = {
            "status": "unknown",
            "raw_result": "unknown",
            "is_cached": False,
            "last_verified_at": None,
            "duration_ms": 0.0,
            "freshness_seconds": 0.0,
            "freshness_label": "Unknown",
            "next_refresh_eligible_at": None,
            "last_error": None
        }
        try:
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = str(cursor.fetchone()[0]).lower()
            integrity_diag = integrity_monitor.check_integrity(conn)
        except Exception as exc:
            logger.error(f"Failed to check SQLite journal_mode/integrity: {exc}")
            integrity_diag["status"] = "failed"
            integrity_diag["last_error"] = str(exc)

        db_path = get_db_path()
        db_size_bytes = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        db_size_mb = round(db_size_bytes / (1024.0 * 1024.0), 2)
        cache_stats = cache_service.get_stats()

        # ------------------------------------------------------------------
        # Compose Master Executive Payload
        # ------------------------------------------------------------------
        return {
            "metadata": {
                "institution_name": institution_name,
                "academic_session": active_session,
                "currency_symbol": currency_symbol,
                "contact_info": institution_contact,
                "server_timestamp": server_timestamp,
                "filters_applied": {
                    "academic_session": active_session,
                    "campus": campus or "All Campuses",
                    "hostel_id": hostel_id,
                    "department": department or "All Departments",
                    "date_from": date_from,
                    "date_to": date_to
                },
                "cache_status": "MISS",
                "execution_time_ms": 0.0
            },
            "institution_overview": {
                "campuses": campuses_count,
                "hostels": total_hostels,
                "buildings": total_buildings,
                "departments": total_departments_count,
                "floors": total_floors,
                "rooms": total_rooms,
                "beds": total_beds,
                "students": total_students,
                "students_active": active_students,
                "students_inactive": inactive_students,
                "students_pending": pending_students,
                "students_withdrawn": withdrawn_students,
                "users": total_users,
                "users_active": active_users,
                "stakeholders": total_roles,
                "dashboards": total_dashboards
            },
            "kpi_grid": {
                "students": {
                    "total": total_students,
                    "active": active_students,
                    "inactive_withdrawn": inactive_students,
                    "pending": pending_students,
                    "withdrawn": withdrawn_students,
                    "retention_rate_pct": student_retention_rate
                },
                "hostels": {
                    "total_capacity": total_beds,
                    "occupied_beds": occupied_beds,
                    "available_beds": available_beds,
                    "maintenance_beds": maintenance_beds,
                    "occupancy_rate_pct": overall_occupancy_rate
                },
                "users": {
                    "total_accounts": total_users,
                    "active_accounts": active_users,
                    "inactive_accounts": inactive_users,
                    "total_roles": total_roles,
                    "total_dashboards": total_dashboards
                },
                "admissions": {
                    "total_applications": total_admissions,
                    "admitted_approved": approved_admissions,
                    "pending_review": submitted_admissions + under_review_admissions,
                    "conversion_rate_pct": admission_conversion_rate
                }
            },
            "operational_performance": {
                "complaints": {
                    "total": total_complaints,
                    "open_in_progress": open_complaints,
                    "resolved": resolved_complaints,
                    "high_critical_open": high_critical_complaints,
                    "resolution_rate_pct": complaint_resolution_rate
                },
                "maintenance": {
                    "total_work_orders": total_maintenance,
                    "pending_assigned": pending_maintenance,
                    "completed": completed_maintenance,
                    "emergency_open": emergency_maintenance,
                    "completion_rate_pct": maintenance_completion_rate
                },
                "leaves_outpasses": {
                    "active_leaves": active_leaves,
                    "active_outpasses": active_outpasses,
                    "overdue_outpasses": overdue_outpasses
                },
                "visitors": {
                    "total_logs": total_visitors,
                    "active_inside": active_inside_visitors,
                    "overdue_visitors": overdue_visitors
                },
                "security": {
                    "gate_verifications_today": security_verifications_today,
                    "curfew_breaches": overdue_outpasses + overdue_visitors
                }
            },
            "financial_overview": {
                "total_invoiced_paise": total_invoiced_paise,
                "total_invoiced_inr": round(total_invoiced_paise / 100.0, 2),
                "total_collected_paise": total_collected_paise,
                "total_collected_inr": round(total_collected_paise / 100.0, 2),
                "outstanding_dues_paise": outstanding_dues_paise,
                "outstanding_dues_inr": round(outstanding_dues_paise / 100.0, 2),
                "collection_efficiency_pct": collection_efficiency_pct,
                "payment_status_counts": pay_status_counts,
                "monthly_trend": monthly_trend,
                "hostel_breakdown": hostel_financials
            },
            "admission_overview": {
                "intake_capacity": total_beds,
                "total_applications": total_admissions,
                "submitted": submitted_admissions,
                "under_review": under_review_admissions,
                "approved": approved_admissions,
                "rejected": rejected_admissions,
                "conversion_rate_pct": admission_conversion_rate,
                "branch_distribution": branch_distribution,
                "gender_distribution": gender_distribution
            },
            "infrastructure_table": hostels_list,
            "workforce_overview": {
                "total_staff": total_staff_in_depts,
                "active_staff": active_staff_in_depts,
                "department_distribution": department_distribution
            },
            "critical_alerts": critical_alerts,
            "recent_activity": recent_activity_logs,
            "system_health": {
                "db_connected": True,
                "journal_mode": journal_mode,
                "integrity_check": integrity_diag["status"],
                "integrity_diagnostics": integrity_diag,
                "db_size_bytes": db_size_bytes,
                "db_size_mb": db_size_mb,
                "cache_stats": cache_stats,
                "api_latency_target_ms": 10.0
            }
        }
