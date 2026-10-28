"""Dashboard Telemetry & Aggregation API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from backend.app.database.connection import get_db_connection
from backend.app.services.auth_dependencies import get_current_user

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard Telemetry"])


@router.get("/stats")
def get_dashboard_stats(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Return live database aggregation statistics across operational domains."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Hostels & Capacity
        cursor.execute("SELECT COUNT(*) FROM hostels;")
        total_hostels = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM rooms;")
        total_rooms = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM beds;")
        total_beds = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM beds WHERE status = 'Occupied';")
        occupied_beds = cursor.fetchone()[0]

        occupancy_rate = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0.0

        # Users & Students
        cursor.execute("SELECT COUNT(*) FROM students;")
        total_students = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users;")
        total_users = cursor.fetchone()[0]

        # Financials
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM invoices;")
        inv_row = cursor.fetchone()
        total_invoices = inv_row[0]
        total_invoiced_amount = inv_row[1]

        cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE status = 'Completed';")
        pay_row = cursor.fetchone()
        total_payments = pay_row[0]
        total_collected_amount = pay_row[1]

        # Operations & Complaints
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE status IN ('Open', 'In_Progress');")
        pending_complaints = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE status = 'Pending';")
        pending_leaves = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM visitor_logs WHERE check_out_time IS NULL;")
        active_visitors = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM admission_applications WHERE application_status = 'Submitted';")
        pending_admissions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM maintenance_tasks WHERE status IN ('Pending', 'Assigned');")
        pending_maintenance = cursor.fetchone()[0]

        # Recent Login / System Activity
        cursor.execute("""
            SELECT id, username_or_email_attempted, status, timestamp
            FROM login_history
            ORDER BY id DESC
            LIMIT 5;
        """)
        recent_logins = [dict(r) for r in cursor.fetchall()]

        return {
            "hostels": {
                "total": total_hostels,
                "rooms": total_rooms,
                "beds": total_beds,
                "occupied_beds": occupied_beds,
                "available_beds": total_beds - occupied_beds,
                "occupancy_rate": occupancy_rate
            },
            "students": {
                "total": total_students,
                "active": total_students
            },
            "users": {
                "total": total_users
            },
            "finance": {
                "total_invoices": total_invoices,
                "total_invoiced": total_invoiced_amount,
                "total_collected": total_collected_amount,
                "outstanding_dues": max(0.0, total_invoiced_amount - total_collected_amount)
            },
            "operations": {
                "pending_complaints": pending_complaints,
                "pending_leaves": pending_leaves,
                "active_visitors": active_visitors,
                "pending_admissions": pending_admissions,
                "pending_maintenance": pending_maintenance
            },
            "recent_activity": recent_logins
        }
    finally:
        conn.close()
