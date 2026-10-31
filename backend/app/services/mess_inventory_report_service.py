"""
Mess and Inventory Reporting & CSV Export Service
Course: BBAT104 Fundamentals of TQM
Quality Goal: Q05 - Response Time < 10ms SLA
RFC 4180 Streaming CSV Export
"""

import csv
import io
import logging
from typing import List, Dict, Any, Generator, Optional
from datetime import datetime, date, timedelta

from backend.app.database.connection import get_db_connection

logger = logging.getLogger("hms_app")


class MessInventoryReportService:

    # ==================== MESS REPORTS ====================
    @staticmethod
    def get_meal_consumption_report(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        hostel_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT 
                    a.date AS meal_date,
                    a.meal_type,
                    h.name AS hostel_name,
                    COUNT(a.id) AS total_served,
                    SUM(CASE WHEN a.verification_method = 'QR_Scan' THEN 1 ELSE 0 END) AS qr_verified,
                    SUM(CASE WHEN a.verification_method = 'Manual' THEN 1 ELSE 0 END) AS manual_verified,
                    SUM(CASE WHEN a.status = 'Cancelled' THEN 1 ELSE 0 END) AS revoked_scans
                FROM meal_attendance a
                LEFT JOIN hostels h ON a.hostel_id = h.id
                WHERE 1=1
            """
            params: List[Any] = []
            if start_date:
                query += " AND a.date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND a.date <= ?"
                params.append(end_date)
            if hostel_id:
                query += " AND a.hostel_id = ?"
                params.append(hostel_id)

            query += " GROUP BY a.date, a.meal_type, h.name ORDER BY a.date DESC, a.meal_type ASC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def stream_meal_consumption_csv(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        hostel_id: Optional[int] = None
    ) -> Generator[str, None, None]:
        output = io.StringIO()
        writer = csv.writer(output, dialect="excel")

        writer.writerow([
            "Meal Date", "Meal Session", "Hostel Name", "Total Served",
            "QR Scanned", "Manual Verified", "Revoked Scans"
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        data = MessInventoryReportService.get_meal_consumption_report(start_date, end_date, hostel_id)
        for row in data:
            writer.writerow([
                row.get("meal_date", ""),
                row.get("meal_type", ""),
                row.get("hostel_name", "All Hostels"),
                row.get("total_served", 0),
                row.get("qr_verified", 0),
                row.get("manual_verified", 0),
                row.get("revoked_scans", 0)
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    # ==================== INVENTORY REPORTS ====================
    @staticmethod
    def get_stock_summary_report(category_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT 
                    i.item_code,
                    i.name AS item_name,
                    c.name AS category_name,
                    i.unit,
                    i.quantity_in_stock,
                    i.min_reorder_level,
                    i.unit_price,
                    ROUND(i.quantity_in_stock * i.unit_price, 2) AS total_valuation,
                    i.storage_location AS location,
                    i.expiry_date,
                    i.status,
                    s.name AS supplier_name
                FROM inventory_items i
                LEFT JOIN inventory_categories c ON i.category_id = c.id
                LEFT JOIN suppliers s ON i.supplier_id = s.id
                WHERE 1=1
            """
            params: List[Any] = []
            if category_id:
                query += " AND i.category_id = ?"
                params.append(category_id)

            query += " ORDER BY c.name ASC, i.name ASC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def stream_stock_summary_csv(category_id: Optional[int] = None) -> Generator[str, None, None]:
        output = io.StringIO()
        writer = csv.writer(output, dialect="excel")

        writer.writerow([
            "Item Code", "Item Name", "Category", "Stock on Hand", "Unit",
            "Min Reorder Lvl", "Unit Price (INR)", "Total Valuation (INR)",
            "Storage Location", "Expiry Date", "Status", "Preferred Vendor"
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        data = MessInventoryReportService.get_stock_summary_report(category_id)
        for row in data:
            writer.writerow([
                row.get("item_code", ""),
                row.get("item_name", ""),
                row.get("category_name", ""),
                row.get("quantity_in_stock", 0.0),
                row.get("unit", ""),
                row.get("min_reorder_level", 0.0),
                f"{float(row.get('unit_price') or 0.0):.2f}",
                f"{float(row.get('total_valuation') or 0.0):.2f}",
                row.get("location", ""),
                row.get("expiry_date", ""),
                row.get("status", ""),
                row.get("supplier_name", "")
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    @staticmethod
    def get_stock_movement_report(
        transaction_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT 
                    t.id,
                    t.transaction_type,
                    i.item_code,
                    i.name AS item_name,
                    t.quantity,
                    i.unit,
                    t.unit_price,
                    t.total_amount,
                    s.name AS supplier_name,
                    t.invoice_reference AS invoice_ref,
                    t.department_destination AS department,
                    t.purpose AS issued_to,
                    t.adjustment_reason,
                    t.approval_status,
                    (u.first_name || ' ' || u.last_name) AS approved_by_name,
                    t.created_at
                FROM inventory_transactions t
                JOIN inventory_items i ON t.item_id = i.id
                LEFT JOIN suppliers s ON t.supplier_id = s.id
                LEFT JOIN users u ON t.approved_by = u.id
                WHERE 1=1
            """
            params: List[Any] = []
            if transaction_type:
                query += " AND t.transaction_type = ?"
                params.append(transaction_type)
            if start_date:
                query += " AND t.created_at >= ?"
                params.append(start_date)
            if end_date:
                query += " AND t.created_at <= ?"
                params.append(end_date + "T23:59:59")

            query += " ORDER BY t.created_at DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def stream_stock_movement_csv(
        transaction_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Generator[str, None, None]:
        output = io.StringIO()
        writer = csv.writer(output, dialect="excel")

        writer.writerow([
            "TX ID", "Type", "Item Code", "Item Name", "Quantity", "Unit",
            "Unit Price (INR)", "Total Value (INR)", "Vendor / Dept", "Invoice / Reason",
            "Authorized By", "Timestamp", "Status"
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        data = MessInventoryReportService.get_stock_movement_report(transaction_type, start_date, end_date)
        for row in data:
            party_or_dept = row.get("supplier_name") or row.get("department") or row.get("issued_to") or ""
            ref_or_reason = row.get("invoice_ref") or row.get("adjustment_reason") or ""
            writer.writerow([
                row.get("id"),
                row.get("transaction_type", ""),
                row.get("item_code", ""),
                row.get("item_name", ""),
                row.get("quantity", 0.0),
                row.get("unit", ""),
                f"{float(row.get('unit_price') or 0.0):.2f}",
                f"{float(row.get('total_amount') or 0.0):.2f}",
                party_or_dept,
                ref_or_reason,
                row.get("approved_by_name", ""),
                row.get("created_at", ""),
                row.get("approval_status", "")
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
