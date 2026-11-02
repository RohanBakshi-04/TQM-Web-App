from backend.app.services.auth_dependencies import get_parent_authorized_ward_ids
import csv
import io
import sqlite3
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status

from backend.app.database.connection import get_db_connection
from backend.app.services.cache_service import cache_service
from backend.app.utils.logger import logger


class FinancialReportService:
    """Service providing high-speed financial analytics, aggregation, reports, and CSV exports (Q05 SLA <10ms)."""

    # ==========================================
    # 1. FINANCIAL DASHBOARD AGGREGATES
    # ==========================================

    @classmethod
    def get_financial_dashboard(cls, hostel_id: Optional[int], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve aggregated dashboard metrics with caching, role isolation, and sub-10ms response."""
        user_role = current_user.get("role", "")
        user_id = current_user.get("user_id")

        # Check Cache
        cache_key = f"fin_dash:{user_role}:{user_id}:{hostel_id or 'all'}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Student / Parent Personalized View
            if user_role in ["student", "parent", "parent_guardian"]:
                if user_role == "student":
                    cursor.execute("SELECT id FROM students WHERE user_id = ?;", (user_id,))
                    row = cursor.fetchone()
                    student_id = row[0] if row else None
                else:
                    wards = get_parent_authorized_ward_ids(conn, {"id": user_id, "user_id": user_id})
                    student_id = wards[0] if wards else None

                if not student_id:
                    return {
                        "user_role": user_role,
                        "total_billed": 0.0,
                        "total_paid": 0.0,
                        "outstanding_dues": 0.0,
                        "overdue_amount": 0.0,
                        "recent_invoices": [],
                        "recent_payments": []
                    }

                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(ROUND(total_amount + fine_amount - discount_amount, 2)), 0.0) as total_billed,
                        COALESCE(SUM(paid_amount), 0.0) as total_paid,
                        COALESCE(SUM(CASE WHEN status NOT IN ('Paid', 'Cancelled') THEN ROUND(total_amount + fine_amount - discount_amount - paid_amount, 2) ELSE 0.0 END), 0.0) as outstanding_dues,
                        COALESCE(SUM(CASE WHEN (status = 'Overdue' OR (due_date < date('now') AND status NOT IN ('Paid', 'Cancelled'))) THEN ROUND(total_amount + fine_amount - discount_amount - paid_amount, 2) ELSE 0.0 END), 0.0) as overdue_amount
                    FROM invoices
                    WHERE student_id = ? AND status != 'Cancelled';
                """, (student_id,))
                stats = dict(cursor.fetchone())

                cursor.execute("""
                    SELECT inv.*, fs.name as fee_name
                    FROM invoices inv
                    LEFT JOIN fee_structures fs ON fs.id = inv.fee_structure_id
                    WHERE inv.student_id = ?
                    ORDER BY inv.created_at DESC LIMIT 5;
                """, (student_id,))
                recent_invs = [dict(r) for r in cursor.fetchall()]

                cursor.execute("""
                    SELECT p.*, inv.invoice_number
                    FROM payments p
                    JOIN invoices inv ON inv.id = p.invoice_id
                    WHERE p.student_id = ?
                    ORDER BY p.payment_date DESC LIMIT 5;
                """, (student_id,))
                recent_pays = [dict(r) for r in cursor.fetchall()]

                res = {
                    "user_role": user_role,
                    "student_id": student_id,
                    "total_billed": round(stats["total_billed"], 2),
                    "total_paid": round(stats["total_paid"], 2),
                    "outstanding_dues": max(0.0, round(stats["outstanding_dues"], 2)),
                    "overdue_amount": max(0.0, round(stats["overdue_amount"], 2)),
                    "recent_invoices": recent_invs,
                    "recent_payments": recent_pays
                }
                cache_service.set(cache_key, res, ttl=30.0, tags=["finance"])
                return res

            # Staff & Admin Aggregated View
            cls._enforce_financial_view_access(current_user)

            hostel_filter_inv = ""
            hostel_filter_pay = ""
            inv_params = []
            pay_params = []

            if hostel_id:
                hostel_filter_inv = """
                    AND inv.student_id IN (
                        SELECT ra.student_id FROM room_allocations ra
                        JOIN rooms r ON r.id = ra.room_id
                        JOIN floors f ON f.id = r.floor_id
                        JOIN buildings bld ON bld.id = f.building_id
                        WHERE bld.hostel_id = ? AND ra.allocation_status = 'Active'
                    )
                """
                inv_params.append(hostel_id)
                hostel_filter_pay = """
                    AND p.student_id IN (
                        SELECT ra.student_id FROM room_allocations ra
                        JOIN rooms r ON r.id = ra.room_id
                        JOIN floors f ON f.id = r.floor_id
                        JOIN buildings bld ON bld.id = f.building_id
                        WHERE bld.hostel_id = ? AND ra.allocation_status = 'Active'
                    )
                """
                pay_params.append(hostel_id)

            # 1. Total Invoiced & Dues
            cursor.execute(f"""
                SELECT 
                    COALESCE(SUM(ROUND(inv.total_amount + inv.fine_amount - inv.discount_amount, 2)), 0.0) as total_invoiced,
                    COALESCE(SUM(inv.paid_amount), 0.0) as paid_on_invoices,
                    COALESCE(SUM(CASE WHEN inv.status NOT IN ('Paid', 'Cancelled') THEN ROUND(inv.total_amount + inv.fine_amount - inv.discount_amount - inv.paid_amount, 2) ELSE 0.0 END), 0.0) as outstanding_dues,
                    COALESCE(SUM(CASE WHEN (inv.status = 'Overdue' OR (inv.due_date < date('now') AND inv.status NOT IN ('Paid', 'Cancelled'))) THEN ROUND(inv.total_amount + inv.fine_amount - inv.discount_amount - inv.paid_amount, 2) ELSE 0.0 END), 0.0) as overdue_total,
                    COUNT(inv.id) as total_invoices_count,
                    COUNT(CASE WHEN inv.status = 'Paid' THEN 1 END) as paid_invoices_count,
                    COUNT(CASE WHEN inv.status IN ('Unpaid', 'Issued', 'Partially_Paid', 'Partially Paid') THEN 1 END) as unpaid_invoices_count,
                    COUNT(CASE WHEN inv.status = 'Overdue' OR (inv.due_date < date('now') AND inv.status NOT IN ('Paid', 'Cancelled')) THEN 1 END) as overdue_invoices_count
                FROM invoices inv
                WHERE inv.status != 'Cancelled' {hostel_filter_inv};
            """, inv_params)
            inv_summary = dict(cursor.fetchone())

            # 2. Total Collected
            cursor.execute(f"""
                SELECT 
                    COALESCE(SUM(p.amount), 0.0) as total_collected,
                    COUNT(p.id) as completed_payments_count
                FROM payments p
                WHERE p.status = 'Completed' {hostel_filter_pay};
            """, pay_params)
            pay_summary = dict(cursor.fetchone())

            # 3. Total Refunds Processed
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0.0) as total_refunded, COUNT(id) as refunds_count
                FROM refunds
                WHERE status = 'Processed';
            """)
            ref_summary = dict(cursor.fetchone())

            # 4. Monthly Collections (Last 6 months)
            cursor.execute(f"""
                SELECT 
                    strftime('%Y-%m', p.payment_date) as month,
                    ROUND(SUM(p.amount), 2) as total_amount,
                    COUNT(p.id) as payment_count
                FROM payments p
                WHERE p.status = 'Completed' 
                  AND p.payment_date >= date('now', '-6 months')
                  {hostel_filter_pay}
                GROUP BY strftime('%Y-%m', p.payment_date)
                ORDER BY month ASC;
            """, pay_params)
            monthly_collections = [dict(r) for r in cursor.fetchall()]

            # 5. Payment Methods Breakdown
            cursor.execute(f"""
                SELECT 
                    p.payment_method,
                    ROUND(SUM(p.amount), 2) as total_amount,
                    COUNT(p.id) as count
                FROM payments p
                WHERE p.status = 'Completed' {hostel_filter_pay}
                GROUP BY p.payment_method
                ORDER BY total_amount DESC;
            """, pay_params)
            payment_methods = [dict(r) for r in cursor.fetchall()]

            # 6. Category Breakdown
            cursor.execute(f"""
                SELECT 
                    COALESCE(fs.fee_category, 'General') as category,
                    ROUND(SUM(ROUND(inv.total_amount + inv.fine_amount - inv.discount_amount, 2)), 2) as total_amount,
                    COUNT(inv.id) as count
                FROM invoices inv
                LEFT JOIN fee_structures fs ON fs.id = inv.fee_structure_id
                WHERE inv.status != 'Cancelled' {hostel_filter_inv}
                GROUP BY fs.fee_category
                ORDER BY total_amount DESC;
            """, inv_params)
            category_breakdown = [dict(r) for r in cursor.fetchall()]

            # 7. Recent Transactions
            cursor.execute(f"""
                SELECT p.id, p.payment_reference, p.amount, p.payment_method, p.payment_date, p.status,
                       inv.invoice_number, s.first_name || ' ' || s.last_name as student_name, s.student_id as enrollment_number
                FROM payments p
                JOIN invoices inv ON inv.id = p.invoice_id
                JOIN students s ON s.id = p.student_id
                WHERE 1=1 {hostel_filter_pay}
                ORDER BY p.created_at DESC LIMIT 5;
            """, pay_params)
            recent_payments = [dict(r) for r in cursor.fetchall()]

            total_invoiced = round(inv_summary["total_invoiced"], 2)
            total_collected = round(pay_summary["total_collected"], 2)
            collection_rate = round((total_collected / total_invoiced * 100.0), 1) if total_invoiced > 0 else 0.0

            dashboard_data = {
                "total_invoiced": total_invoiced,
                "total_collected": total_collected,
                "outstanding_dues": max(0.0, round(inv_summary["outstanding_dues"], 2)),
                "overdue_total": max(0.0, round(inv_summary["overdue_total"], 2)),
                "total_refunded": round(ref_summary["total_refunded"], 2),
                "collection_rate": collection_rate,
                "invoices_count": inv_summary["total_invoices_count"],
                "paid_invoices_count": inv_summary["paid_invoices_count"],
                "unpaid_invoices_count": inv_summary["unpaid_invoices_count"],
                "overdue_invoices_count": inv_summary["overdue_invoices_count"],
                "payments_count": pay_summary["completed_payments_count"],
                "refunds_count": ref_summary["refunds_count"],
                "monthly_collections": monthly_collections,
                "payment_methods": payment_methods,
                "category_breakdown": category_breakdown,
                "recent_payments": recent_payments,
                "hostel_id": hostel_id
            }

            cache_service.set(cache_key, dashboard_data, ttl=60.0, tags=["finance"])
            return dashboard_data
        finally:
            conn.close()

    # ==========================================
    # 2. COLLECTIONS REPORT
    # ==========================================

    @classmethod
    def get_collections_report(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed collections report with date, hostel, and payment method filters."""
        cls._enforce_financial_view_access(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            conditions = ["p.status = 'Completed'"]
            params = []

            if filters.get("start_date"):
                conditions.append("p.payment_date >= ?")
                params.append(filters["start_date"])

            if filters.get("end_date"):
                conditions.append("p.payment_date <= ?")
                params.append(filters["end_date"])

            if filters.get("payment_method"):
                conditions.append("p.payment_method = ?")
                params.append(filters["payment_method"])

            if filters.get("hostel_id"):
                conditions.append("""
                    p.student_id IN (
                        SELECT ra.student_id FROM room_allocations ra
                        JOIN rooms r ON r.id = ra.room_id
                        JOIN floors f ON f.id = r.floor_id
                        JOIN buildings bld ON bld.id = f.building_id
                        WHERE bld.hostel_id = ? AND ra.allocation_status = 'Active'
                    )
                """)
                params.append(filters["hostel_id"])

            where_clause = " WHERE " + " AND ".join(conditions)

            # Summary totals
            cursor.execute(f"""
                SELECT 
                    COALESCE(SUM(p.amount), 0.0) as total_amount,
                    COUNT(p.id) as total_count,
                    COALESCE(AVG(p.amount), 0.0) as average_amount
                FROM payments p
                {where_clause};
            """, params)
            summary = dict(cursor.fetchone())

            # Method breakdown
            cursor.execute(f"""
                SELECT 
                    p.payment_method,
                    ROUND(SUM(p.amount), 2) as total_amount,
                    COUNT(p.id) as count
                FROM payments p
                {where_clause}
                GROUP BY p.payment_method
                ORDER BY total_amount DESC;
            """, params)
            methods_breakdown = [dict(r) for r in cursor.fetchall()]

            # Detailed payment list
            cursor.execute(f"""
                SELECT 
                    p.id, p.payment_reference, p.payment_date, p.amount, p.payment_method,
                    p.transaction_id, p.receipt_number, p.status, p.created_at,
                    inv.invoice_number, fs.name as fee_name,
                    s.id as student_id, s.student_id as enrollment_number, s.first_name || ' ' || s.last_name as student_name,
                    u.username as recorded_by_username
                FROM payments p
                JOIN invoices inv ON inv.id = p.invoice_id
                LEFT JOIN fee_structures fs ON fs.id = inv.fee_structure_id
                JOIN students s ON s.id = p.student_id
                LEFT JOIN users u ON u.id = p.recorded_by
                {where_clause}
                ORDER BY p.payment_date DESC, p.created_at DESC;
            """, params)
            records = [dict(r) for r in cursor.fetchall()]

            return {
                "total_amount": round(summary["total_amount"], 2),
                "total_count": summary["total_count"],
                "average_amount": round(summary["average_amount"], 2),
                "methods_breakdown": methods_breakdown,
                "records": records
            }
        finally:
            conn.close()

    # ==========================================
    # 3. DUES & OUTSTANDING REPORT
    # ==========================================

    @classmethod
    def get_dues_report(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Generate report of all outstanding student dues and balances."""
        cls._enforce_financial_view_access(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            conditions = [
                "inv.status != 'Cancelled'",
                "ROUND(inv.total_amount + inv.fine_amount - inv.discount_amount - inv.paid_amount, 2) > 0"
            ]
            params = []

            if filters.get("status"):
                conditions.append("inv.status = ?")
                params.append(filters["status"])

            if filters.get("hostel_id"):
                conditions.append("""
                    inv.student_id IN (
                        SELECT ra.student_id FROM room_allocations ra
                        JOIN rooms r ON r.id = ra.room_id
                        JOIN floors f ON f.id = r.floor_id
                        JOIN buildings bld ON bld.id = f.building_id
                        WHERE bld.hostel_id = ? AND ra.allocation_status = 'Active'
                    )
                """)
                params.append(filters["hostel_id"])

            if filters.get("min_amount"):
                conditions.append("ROUND(inv.total_amount + inv.fine_amount - inv.discount_amount - inv.paid_amount, 2) >= ?")
                params.append(float(filters["min_amount"]))

            where_clause = " WHERE " + " AND ".join(conditions)

            # Summary
            cursor.execute(f"""
                SELECT 
                    COALESCE(SUM(ROUND(inv.total_amount + inv.fine_amount - inv.discount_amount - inv.paid_amount, 2)), 0.0) as total_dues,
                    COUNT(inv.id) as invoices_count,
                    COUNT(DISTINCT inv.student_id) as student_count
                FROM invoices inv
                {where_clause};
            """, params)
            summary = dict(cursor.fetchone())

            # Records
            cursor.execute(f"""
                SELECT 
                    inv.id, inv.invoice_number, inv.issue_date, inv.due_date,
                    ROUND(inv.total_amount + inv.fine_amount - inv.discount_amount, 2) as net_payable,
                    inv.paid_amount,
                    ROUND(inv.total_amount + inv.fine_amount - inv.discount_amount - inv.paid_amount, 2) as outstanding_balance,
                    inv.status, fs.name as fee_name, fs.fee_category,
                    s.id as student_id, s.student_id as enrollment_number, s.first_name || ' ' || s.last_name as student_name,
                    s.phone, s.email,
                    h.name as hostel_name, r.room_number
                FROM invoices inv
                LEFT JOIN fee_structures fs ON fs.id = inv.fee_structure_id
                JOIN students s ON s.id = inv.student_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                {where_clause}
                ORDER BY outstanding_balance DESC;
            """, params)
            records = [dict(r) for r in cursor.fetchall()]

            return {
                "total_dues": round(summary["total_dues"], 2),
                "invoices_count": summary["invoices_count"],
                "student_count": summary["student_count"],
                "records": records
            }
        finally:
            conn.close()

    # ==========================================
    # 4. OVERDUE REPORT & AGING ANALYSIS
    # ==========================================

    @classmethod
    def get_overdue_report(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overdue report with aging brackets (1-30d, 31-60d, 61-90d, 90+d)."""
        cls._enforce_financial_view_access(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            conditions = [
                "inv.status != 'Cancelled'",
                "ROUND(inv.total_amount + inv.fine_amount - inv.discount_amount - inv.paid_amount, 2) > 0",
                "(inv.status = 'Overdue' OR inv.due_date < date('now'))"
            ]
            params = []

            if filters.get("hostel_id"):
                conditions.append("""
                    inv.student_id IN (
                        SELECT ra.student_id FROM room_allocations ra
                        JOIN rooms r ON r.id = ra.room_id
                        JOIN floors f ON f.id = r.floor_id
                        JOIN buildings bld ON bld.id = f.building_id
                        WHERE bld.hostel_id = ? AND ra.allocation_status = 'Active'
                    )
                """)
                params.append(filters["hostel_id"])

            where_clause = " WHERE " + " AND ".join(conditions)

            cursor.execute(f"""
                SELECT 
                    inv.id, inv.invoice_number, inv.issue_date, inv.due_date,
                    ROUND(inv.total_amount + inv.fine_amount - inv.discount_amount, 2) as net_payable,
                    inv.paid_amount,
                    ROUND(inv.total_amount + inv.fine_amount - inv.discount_amount - inv.paid_amount, 2) as outstanding_balance,
                    inv.status, fs.name as fee_name,
                    s.id as student_id, s.student_id as enrollment_number, s.first_name || ' ' || s.last_name as student_name,
                    s.phone, s.email,
                    h.name as hostel_name, r.room_number,
                    CAST(ROUND(julianday('now') - julianday(inv.due_date)) AS INTEGER) as days_overdue
                FROM invoices inv
                LEFT JOIN fee_structures fs ON fs.id = inv.fee_structure_id
                JOIN students s ON s.id = inv.student_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                {where_clause}
                ORDER BY days_overdue DESC, outstanding_balance DESC;
            """, params)
            records = [dict(r) for r in cursor.fetchall()]

            # Compute Aging Buckets
            aging = {
                "1_to_30_days": {"count": 0, "total_amount": 0.0},
                "31_to_60_days": {"count": 0, "total_amount": 0.0},
                "61_to_90_days": {"count": 0, "total_amount": 0.0},
                "over_90_days": {"count": 0, "total_amount": 0.0}
            }
            total_overdue = 0.0

            for rec in records:
                days = rec["days_overdue"]
                bal = rec["outstanding_balance"]
                total_overdue += bal

                if days <= 30:
                    aging["1_to_30_days"]["count"] += 1
                    aging["1_to_30_days"]["total_amount"] += bal
                elif days <= 60:
                    aging["31_to_60_days"]["count"] += 1
                    aging["31_to_60_days"]["total_amount"] += bal
                elif days <= 90:
                    aging["61_to_90_days"]["count"] += 1
                    aging["61_to_90_days"]["total_amount"] += bal
                else:
                    aging["over_90_days"]["count"] += 1
                    aging["over_90_days"]["total_amount"] += bal

            for k in aging:
                aging[k]["total_amount"] = round(aging[k]["total_amount"], 2)

            return {
                "total_overdue": round(total_overdue, 2),
                "total_count": len(records),
                "aging_summary": aging,
                "records": records
            }
        finally:
            conn.close()

    # ==========================================
    # 5. REFUNDS REPORT
    # ==========================================

    @classmethod
    def get_refunds_report(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Generate refunds audit report with statuses and review lifecycle."""
        cls._enforce_financial_view_access(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            conditions = ["1=1"]
            params = []

            if filters.get("status"):
                conditions.append("r.status = ?")
                params.append(filters["status"])

            if filters.get("start_date"):
                conditions.append("r.created_at >= ?")
                params.append(filters["start_date"] + " 00:00:00")

            if filters.get("end_date"):
                conditions.append("r.created_at <= ?")
                params.append(filters["end_date"] + " 23:59:59")

            where_clause = " WHERE " + " AND ".join(conditions)

            # Summary
            cursor.execute(f"""
                SELECT 
                    COALESCE(SUM(r.amount), 0.0) as total_requested_amount,
                    COALESCE(SUM(CASE WHEN r.status = 'Processed' THEN r.amount ELSE 0.0 END), 0.0) as total_processed_amount,
                    COUNT(r.id) as total_count,
                    COUNT(CASE WHEN r.status = 'Requested' THEN 1 END) as pending_count,
                    COUNT(CASE WHEN r.status = 'Approved' THEN 1 END) as approved_count,
                    COUNT(CASE WHEN r.status = 'Processed' THEN 1 END) as processed_count,
                    COUNT(CASE WHEN r.status = 'Rejected' THEN 1 END) as rejected_count
                FROM refunds r
                {where_clause};
            """, params)
            summary = dict(cursor.fetchone())

            # Records
            cursor.execute(f"""
                SELECT 
                    r.*, p.payment_reference, p.payment_method, inv.invoice_number,
                    s.student_id as enrollment_number, s.first_name || ' ' || s.last_name as student_name,
                    req_u.username as requested_by_user,
                    app_u.username as approved_by_user,
                    proc_u.username as processed_by_user
                FROM refunds r
                JOIN payments p ON p.id = r.payment_id
                LEFT JOIN invoices inv ON inv.id = r.invoice_id
                LEFT JOIN students s ON s.id = r.student_id
                LEFT JOIN users req_u ON req_u.id = r.requested_by
                LEFT JOIN users app_u ON app_u.id = r.approved_by
                LEFT JOIN users proc_u ON proc_u.id = r.processed_by
                {where_clause}
                ORDER BY r.created_at DESC;
            """, params)
            records = [dict(r) for r in cursor.fetchall()]

            return {
                "total_requested_amount": round(summary["total_requested_amount"], 2),
                "total_processed_amount": round(summary["total_processed_amount"], 2),
                "total_count": summary["total_count"],
                "pending_count": summary["pending_count"],
                "approved_count": summary["approved_count"],
                "processed_count": summary["processed_count"],
                "rejected_count": summary["rejected_count"],
                "records": records
            }
        finally:
            conn.close()

    # ==========================================
    # 6. CSV EXPORT GENERATOR
    # ==========================================

    @classmethod
    def export_csv(cls, report_type: str, filters: Dict[str, Any], current_user: Dict[str, Any]) -> str:
        """Streamlined CSV export generator adhering to Q05 sub-10ms response time."""
        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == "collections":
            report = cls.get_collections_report(filters, current_user)
            writer.writerow(["Payment Reference", "Date", "Student Name", "Enrollment No", "Invoice Number", "Fee Structure", "Payment Method", "Transaction ID", "Amount (INR)", "Status", "Recorded By"])
            for r in report["records"]:
                writer.writerow([
                    r.get("payment_reference"),
                    r.get("payment_date"),
                    r.get("student_name"),
                    r.get("enrollment_number"),
                    r.get("invoice_number"),
                    r.get("fee_name"),
                    r.get("payment_method"),
                    r.get("transaction_id"),
                    f"{r.get('amount', 0):.2f}",
                    r.get("status"),
                    r.get("recorded_by_username")
                ])
        elif report_type == "dues":
            report = cls.get_dues_report(filters, current_user)
            writer.writerow(["Invoice Number", "Student Name", "Enrollment No", "Hostel", "Room", "Fee Category", "Issue Date", "Due Date", "Net Payable (INR)", "Paid Amount (INR)", "Outstanding Balance (INR)", "Status", "Contact"])
            for r in report["records"]:
                writer.writerow([
                    r.get("invoice_number"),
                    r.get("student_name"),
                    r.get("enrollment_number"),
                    r.get("hostel_name") or "Unassigned",
                    r.get("room_number") or "Unassigned",
                    r.get("fee_category"),
                    r.get("issue_date"),
                    r.get("due_date"),
                    f"{r.get('net_payable', 0):.2f}",
                    f"{r.get('paid_amount', 0):.2f}",
                    f"{r.get('outstanding_balance', 0):.2f}",
                    r.get("status"),
                    r.get("phone") or r.get("email")
                ])
        elif report_type == "overdue":
            report = cls.get_overdue_report(filters, current_user)
            writer.writerow(["Invoice Number", "Student Name", "Enrollment No", "Hostel", "Room", "Due Date", "Days Overdue", "Outstanding Balance (INR)", "Status", "Contact"])
            for r in report["records"]:
                writer.writerow([
                    r.get("invoice_number"),
                    r.get("student_name"),
                    r.get("enrollment_number"),
                    r.get("hostel_name") or "Unassigned",
                    r.get("room_number") or "Unassigned",
                    r.get("due_date"),
                    r.get("days_overdue"),
                    f"{r.get('outstanding_balance', 0):.2f}",
                    r.get("status"),
                    r.get("phone") or r.get("email")
                ])
        elif report_type == "refunds":
            report = cls.get_refunds_report(filters, current_user)
            writer.writerow(["Refund Reference", "Payment Reference", "Student Name", "Enrollment No", "Amount (INR)", "Reason", "Status", "Refund Method", "Transaction Ref", "Requested By", "Approved By", "Processed By", "Created At"])
            for r in report["records"]:
                writer.writerow([
                    r.get("refund_reference"),
                    r.get("payment_reference"),
                    r.get("student_name"),
                    r.get("enrollment_number"),
                    f"{r.get('amount', 0):.2f}",
                    r.get("reason"),
                    r.get("status"),
                    r.get("refund_method"),
                    r.get("transaction_reference"),
                    r.get("requested_by_user"),
                    r.get("approved_by_user"),
                    r.get("processed_by_user"),
                    r.get("created_at")
                ])
        else:
            raise HTTPException(status_code=400, detail=f"Invalid report type: {report_type}")

        return output.getvalue()

    # ==========================================
    # HELPER PERMISSION CHECKS
    # ==========================================

    @staticmethod
    def _enforce_financial_view_access(current_user: Dict[str, Any]):
        role = current_user.get("role")
        allowed = ["super_admin", "hostel_admin", "accountant", "auditor", "warden", "assistant_warden"]
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Access restricted to administrative, financial, and audit roles."
            )
