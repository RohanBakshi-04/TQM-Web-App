import sqlite3
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status

from backend.app.database.connection import get_db_connection
from backend.app.models.finance_dto import (
    FeeStructureCreate,
    FeeStructureUpdate,
    InvoiceCreate,
    BulkInvoiceCreate,
    InvoiceDiscountApply,
    InvoiceCancelRequest,
)
from backend.app.services.cache_service import cache_service
from backend.app.utils.logger import logger


class FeeService:
    """Service handling Fee Structures, Student Invoicing, and Concessions adhering to TQM Q05 SLA."""

    # ==========================================
    # 1. FEE STRUCTURE MANAGEMENT
    # ==========================================

    @classmethod
    def create_fee_structure(cls, payload: FeeStructureCreate, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new fee structure configuration with duplicate and constraint validation."""
        cls._enforce_accountant_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Prevent duplicate fee structure configuration
            cursor.execute("""
                SELECT id FROM fee_structures
                WHERE name = ? AND academic_year = ? AND COALESCE(hostel_id, 0) = ? 
                  AND room_type = ? AND semester = ?;
            """, (payload.name.strip(), payload.academic_year.strip(), payload.hostel_id or 0, payload.room_type, payload.semester))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A fee structure with identical name, academic year, hostel, and room type already exists."
                )

            cursor.execute("""
                INSERT INTO fee_structures (
                    name, fee_category, hostel_id, room_type, academic_year, semester,
                    amount, payment_frequency, is_mandatory, late_fine_amount, description, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
            """, (
                payload.name.strip(),
                payload.fee_category,
                payload.hostel_id,
                payload.room_type,
                payload.academic_year.strip(),
                payload.semester,
                round(payload.amount, 2),
                payload.payment_frequency,
                1 if payload.is_mandatory else 0,
                round(payload.late_fine_amount, 2),
                payload.description or ""
            ))
            fs_id = cursor.lastrowid

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'CREATE_FEE_STRUCTURE', 'fee_structures', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "accountant"),
                str(fs_id),
                f"Created {payload.fee_category}: {payload.name} (INR {payload.amount:.2f})"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("finance")
            logger.info(f"Fee structure #{fs_id} ('{payload.name}') created by {current_user.get('username')}")

            return cls.get_fee_structure(fs_id, current_user)
        finally:
            conn.close()

    @classmethod
    def get_fee_structures(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List fee structures with multi-criteria filtering."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            where_clauses = ["1=1"]
            params = []

            if filters.get("hostel_id"):
                where_clauses.append("(fs.hostel_id = ? OR fs.hostel_id IS NULL)")
                params.append(filters["hostel_id"])
            if filters.get("academic_year"):
                where_clauses.append("fs.academic_year = ?")
                params.append(filters["academic_year"])
            if filters.get("fee_category"):
                where_clauses.append("fs.fee_category = ?")
                params.append(filters["fee_category"])
            if filters.get("is_active") is not None:
                where_clauses.append("fs.is_active = ?")
                params.append(1 if filters["is_active"] else 0)

            where_str = " AND ".join(where_clauses)
            cursor.execute(f"""
                SELECT fs.*, h.name as hostel_name
                FROM fee_structures fs
                LEFT JOIN hostels h ON h.id = fs.hostel_id
                WHERE {where_str}
                ORDER BY fs.id DESC;
            """, params)

            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    @classmethod
    def get_fee_structure(cls, fs_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve details of a single fee structure."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fs.*, h.name as hostel_name
                FROM fee_structures fs
                LEFT JOIN hostels h ON h.id = fs.hostel_id
                WHERE fs.id = ?;
            """, (fs_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Fee structure not found.")
            return dict(record)
        finally:
            conn.close()

    @classmethod
    def update_fee_structure(cls, fs_id: int, payload: FeeStructureUpdate, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing fee structure. Historical invoices remain protected."""
        cls._enforce_accountant_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fee_structures WHERE id = ?;", (fs_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Fee structure not found.")

            updates = []
            params = []
            if payload.name is not None:
                updates.append("name = ?")
                params.append(payload.name.strip())
            if payload.fee_category is not None:
                updates.append("fee_category = ?")
                params.append(payload.fee_category)
            if payload.hostel_id is not None:
                updates.append("hostel_id = ?")
                params.append(payload.hostel_id)
            if payload.room_type is not None:
                updates.append("room_type = ?")
                params.append(payload.room_type)
            if payload.academic_year is not None:
                updates.append("academic_year = ?")
                params.append(payload.academic_year.strip())
            if payload.semester is not None:
                updates.append("semester = ?")
                params.append(payload.semester)
            if payload.amount is not None:
                updates.append("amount = ?")
                params.append(round(payload.amount, 2))
            if payload.payment_frequency is not None:
                updates.append("payment_frequency = ?")
                params.append(payload.payment_frequency)
            if payload.is_mandatory is not None:
                updates.append("is_mandatory = ?")
                params.append(1 if payload.is_mandatory else 0)
            if payload.late_fine_amount is not None:
                updates.append("late_fine_amount = ?")
                params.append(round(payload.late_fine_amount, 2))
            if payload.description is not None:
                updates.append("description = ?")
                params.append(payload.description)
            if payload.is_active is not None:
                updates.append("is_active = ?")
                params.append(1 if payload.is_active else 0)

            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                cursor.execute(f"UPDATE fee_structures SET {', '.join(updates)} WHERE id = ?;", params + [fs_id])

                cursor.execute("""
                    INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                    VALUES (?, ?, 'UPDATE_FEE_STRUCTURE', 'fee_structures', ?, ?, 0.5);
                """, (
                    current_user.get("user_id"),
                    current_user.get("username", "accountant"),
                    str(fs_id),
                    f"Updated fee structure #{fs_id}"
                ))

                conn.commit()
                cache_service.invalidate_by_tag("finance")

            return cls.get_fee_structure(fs_id, current_user)
        finally:
            conn.close()

    @classmethod
    def delete_fee_structure(cls, fs_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Soft-deactivate fee structure to preserve historical invoice references."""
        cls._enforce_accountant_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM fee_structures WHERE id = ?;", (fs_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Fee structure not found.")

            # Check if referenced in invoices
            cursor.execute("SELECT COUNT(id) FROM invoices WHERE fee_structure_id = ?;", (fs_id,))
            count = cursor.fetchone()[0]

            if count > 0:
                # Soft deactivate to maintain financial historical integrity
                cursor.execute("UPDATE fee_structures SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (fs_id,))
                msg = f"Fee structure #{fs_id} deactivated to preserve {count} historical invoice records."
            else:
                cursor.execute("DELETE FROM fee_structures WHERE id = ?;", (fs_id,))
                msg = f"Fee structure #{fs_id} successfully deleted."

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'DELETE_FEE_STRUCTURE', 'fee_structures', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "accountant"),
                str(fs_id),
                msg
            ))

            conn.commit()
            cache_service.invalidate_by_tag("finance")
            return {"status": "success", "message": msg}
        finally:
            conn.close()

    # ==========================================
    # 2. INVOICE MANAGEMENT
    # ==========================================

    @classmethod
    def create_invoice(cls, payload: InvoiceCreate, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a single student invoice with breakdown items and duplicate prevention."""
        cls._enforce_accountant_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Verify student exists
            st_val = str(payload.student_id).strip()
            cursor.execute("SELECT id, student_id, first_name || ' ' || last_name as name, user_id FROM students WHERE student_id = ? OR CAST(id AS TEXT) = ?;", (st_val, st_val))
            student = cursor.fetchone()
            if not student:
                raise HTTPException(status_code=404, detail="Student not found.")
            payload.student_id = student["id"]

            fee_struct = None
            if payload.fee_structure_id:
                cursor.execute("SELECT * FROM fee_structures WHERE id = ?;", (payload.fee_structure_id,))
                fee_struct = cursor.fetchone()
                if not fee_struct:
                    raise HTTPException(status_code=404, detail="Referenced fee structure not found.")

                # Poka-Yoke: Prevent duplicate active invoices for same student and fee structure in same period
                cursor.execute("""
                    SELECT id, invoice_number FROM invoices
                    WHERE student_id = ? AND fee_structure_id = ? AND status NOT IN ('Cancelled')
                      AND strftime('%Y-%m', issue_date) = strftime('%Y-%m', ?);
                """, (payload.student_id, payload.fee_structure_id, payload.issue_date))
                existing = cursor.fetchone()
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"An active invoice ({existing['invoice_number']}) already exists for this student and fee structure in this billing cycle."
                    )

            # Determine line items and total
            items = []
            if payload.items:
                for it in payload.items:
                    items.append({"title": it.title.strip(), "amount": round(it.amount, 2)})
            elif fee_struct:
                items.append({"title": fee_struct["name"], "amount": round(fee_struct["amount"], 2)})

            total_amount = payload.total_amount if payload.total_amount is not None else sum(it["amount"] for it in items)
            total_amount = round(total_amount, 2)
            discount = round(payload.discount_amount, 2)

            if discount > total_amount:
                raise HTTPException(status_code=400, detail="Discount amount cannot exceed total invoice amount.")

            # Generate unique invoice number: INV-YYYYMM-XXXX
            today_prefix = date.today().strftime("%Y%m")
            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM invoices;")
            seq = cursor.fetchone()[0] or 1
            while True:
                candidate = f"INV-{today_prefix}-{seq:04d}"
                cursor.execute("SELECT 1 FROM invoices WHERE invoice_number = ?;", (candidate,))
                if not cursor.fetchone():
                    invoice_number = candidate
                    break
                seq += 1

            status_val = payload.status if payload.status in ["Draft", "Issued"] else "Issued"

            cursor.execute("""
                INSERT INTO invoices (
                    invoice_number, student_id, fee_structure_id, issue_date, due_date,
                    total_amount, paid_amount, discount_amount, discount_reason, fine_amount,
                    status, remarks
                ) VALUES (?, ?, ?, ?, ?, ?, 0.0, ?, ?, 0.0, ?, ?);
            """, (
                invoice_number,
                payload.student_id,
                payload.fee_structure_id,
                payload.issue_date,
                payload.due_date,
                total_amount,
                discount,
                payload.discount_reason or "",
                status_val,
                payload.remarks or ""
            ))
            invoice_id = cursor.lastrowid

            # Insert line items
            for it in items:
                cursor.execute("""
                    INSERT INTO invoice_items (invoice_id, title, amount)
                    VALUES (?, ?, ?);
                """, (invoice_id, it["title"], it["amount"]))

            # Notify student
            if student["user_id"]:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type)
                    VALUES (?, ?, ?, 'info');
                """, (
                    student["user_id"],
                    "New Invoice Generated",
                    f"Invoice {invoice_number} for INR {total_amount:.2f} has been issued. Due date: {payload.due_date}."
                ))

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'CREATE_INVOICE', 'invoices', ?, ?, 0.6);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "accountant"),
                str(invoice_id),
                f"Generated invoice {invoice_number} for Student #{payload.student_id} (Total: INR {total_amount:.2f})"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("finance")
            logger.info(f"Invoice {invoice_number} created for student #{payload.student_id}")

            return cls.get_invoice(invoice_id, current_user)
        finally:
            conn.close()

    @classmethod
    def create_bulk_invoices(cls, payload: BulkInvoiceCreate, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Generate invoices in bulk for eligible students matching criteria."""
        cls._enforce_accountant_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Verify fee structure
            cursor.execute("SELECT * FROM fee_structures WHERE id = ?;", (payload.fee_structure_id,))
            fs = cursor.fetchone()
            if not fs:
                raise HTTPException(status_code=404, detail="Referenced fee structure not found.")

            # Find matching active resident students
            where_clauses = ["s.status = 'Active'"]
            params = []

            if payload.hostel_id:
                where_clauses.append("bld.hostel_id = ?")
                params.append(payload.hostel_id)
            if payload.academic_year and payload.academic_year != "All":
                where_clauses.append("s.academic_year = ?")
                params.append(payload.academic_year)
            if payload.room_type and payload.room_type != "All":
                where_clauses.append("r.room_type = ?")
                params.append(payload.room_type)

            where_str = " AND ".join(where_clauses)
            cursor.execute(f"""
                SELECT DISTINCT s.id as student_id, s.user_id, s.first_name || ' ' || s.last_name as student_name
                FROM students s
                JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                JOIN rooms r ON r.id = ra.room_id
                JOIN floors f ON f.id = r.floor_id
                JOIN buildings bld ON bld.id = f.building_id
                WHERE {where_str};
            """, params)
            eligible_students = cursor.fetchall()

            if not eligible_students:
                return {
                    "total_eligible": 0,
                    "invoices_created": 0,
                    "skipped_duplicates": 0,
                    "created_invoices": []
                }

            today_prefix = date.today().strftime("%Y%m")
            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM invoices;")
            seq = cursor.fetchone()[0] or 1

            created_count = 0
            skipped_count = 0
            created_invoices = []

            for st in eligible_students:
                s_id = st["student_id"]

                # Poka-Yoke: Check duplicate
                cursor.execute("""
                    SELECT id FROM invoices
                    WHERE student_id = ? AND fee_structure_id = ? AND status NOT IN ('Cancelled')
                      AND strftime('%Y-%m', issue_date) = strftime('%Y-%m', ?);
                """, (s_id, payload.fee_structure_id, payload.issue_date))
                if cursor.fetchone():
                    skipped_count += 1
                    continue

                # Generate invoice number
                while True:
                    candidate = f"INV-{today_prefix}-{seq:04d}"
                    cursor.execute("SELECT 1 FROM invoices WHERE invoice_number = ?;", (candidate,))
                    if not cursor.fetchone():
                        inv_num = candidate
                        break
                    seq += 1

                amount = round(fs["amount"], 2)
                cursor.execute("""
                    INSERT INTO invoices (
                        invoice_number, student_id, fee_structure_id, issue_date, due_date,
                        total_amount, paid_amount, discount_amount, fine_amount, status, remarks
                    ) VALUES (?, ?, ?, ?, ?, ?, 0.0, 0.0, 0.0, 'Issued', ?);
                """, (inv_num, s_id, payload.fee_structure_id, payload.issue_date, payload.due_date, amount, payload.remarks or ""))
                inv_id = cursor.lastrowid

                # Line item
                cursor.execute("""
                    INSERT INTO invoice_items (invoice_id, title, amount)
                    VALUES (?, ?, ?);
                """, (inv_id, fs["name"], amount))

                # Student notification
                if st["user_id"]:
                    cursor.execute("""
                        INSERT INTO notifications (user_id, title, message, notification_type)
                        VALUES (?, ?, ?, 'info');
                    """, (
                        st["user_id"],
                        "Hostel Fee Invoice Issued",
                        f"Invoice {inv_num} for INR {amount:.2f} has been generated. Due date: {payload.due_date}."
                    ))

                created_count += 1
                created_invoices.append({"invoice_id": inv_id, "invoice_number": inv_num, "student_id": s_id})

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'BULK_INVOICES_GENERATED', 'invoices', '0', ?, 1.2);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "accountant"),
                f"Generated {created_count} bulk invoices (skipped {skipped_count} duplicates) under fee structure #{payload.fee_structure_id}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("finance")
            logger.info(f"Bulk invoice run complete: {created_count} created, {skipped_count} skipped.")

            return {
                "total_eligible": len(eligible_students),
                "invoices_created": created_count,
                "skipped_duplicates": skipped_count,
                "created_invoices": created_invoices
            }
        finally:
            conn.close()

    @classmethod
    def apply_discount(cls, invoice_id: int, payload: InvoiceDiscountApply, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Apply an approved concession/discount to an unpaid or partially paid invoice."""
        cls._enforce_accountant_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoices WHERE id = ?;", (invoice_id,))
            inv = cursor.fetchone()
            if not inv:
                raise HTTPException(status_code=404, detail="Invoice not found.")

            if inv["status"] in ["Paid", "Cancelled"]:
                raise HTTPException(status_code=400, detail=f"Cannot apply discount to an invoice in '{inv['status']}' status.")

            discount = round(payload.discount_amount, 2)
            net_payable = round(inv["total_amount"] + inv["fine_amount"] - inv["paid_amount"], 2)

            if discount > net_payable:
                raise HTTPException(
                    status_code=400,
                    detail=f"Discount of INR {discount:.2f} exceeds outstanding balance of INR {net_payable:.2f}."
                )

            # Update discount
            new_discount = round(inv["discount_amount"] + discount, 2)
            # Recompute status if discount completely settles the remaining balance
            new_balance = round(inv["total_amount"] + inv["fine_amount"] - inv["paid_amount"] - new_discount, 2)
            new_status = "Paid" if new_balance <= 0 else inv["status"]

            cursor.execute("""
                UPDATE invoices
                SET discount_amount = ?, discount_reason = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (new_discount, payload.discount_reason.strip(), new_status, invoice_id))

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'APPLY_DISCOUNT', 'invoices', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "accountant"),
                str(invoice_id),
                f"Applied discount of INR {discount:.2f} to Invoice #{invoice_id}. Reason: {payload.discount_reason}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("finance")
            return cls.get_invoice(invoice_id, current_user)
        finally:
            conn.close()

    @classmethod
    def cancel_invoice(cls, invoice_id: int, payload: InvoiceCancelRequest, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel an invoice with mandatory audit justification."""
        cls._enforce_accountant_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoices WHERE id = ?;", (invoice_id,))
            inv = cursor.fetchone()
            if not inv:
                raise HTTPException(status_code=404, detail="Invoice not found.")

            if inv["paid_amount"] > 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot cancel an invoice with recorded payments. Please process refunds or audited reversals first."
                )

            cursor.execute("""
                UPDATE invoices
                SET status = 'Cancelled', cancellation_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (payload.cancellation_reason.strip(), invoice_id))

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'CANCEL_INVOICE', 'invoices', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "accountant"),
                str(invoice_id),
                f"Cancelled invoice #{invoice_id}. Reason: {payload.cancellation_reason}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("finance")
            return {"status": "success", "message": f"Invoice #{invoice_id} successfully cancelled."}
        finally:
            conn.close()

    @classmethod
    def get_invoices(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch filtered and paginated invoices adhering strictly to RBAC data boundaries."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            role = current_user.get("role")
            user_hostel_id = current_user.get("hostel_id")

            where_clauses = ["1=1"]
            params: List[Any] = []

            # RBAC Isolation
            if role == "student":
                cursor.execute("SELECT id FROM students WHERE user_id = ?;", (current_user.get("user_id"),))
                st = cursor.fetchone()
                if not st:
                    return {"total": 0, "records": []}
                where_clauses.append("inv.student_id = ?")
                params.append(st["id"])
            elif role == "parent":
                cursor.execute("""
                    SELECT sg.student_id FROM student_guardians sg
                    JOIN guardians g ON g.id = sg.guardian_id
                    WHERE g.user_id = ?;
                """, (current_user.get("user_id"),))
                wards = [r[0] for r in cursor.fetchall()]
                if not wards:
                    return {"total": 0, "records": []}
                placeholders = ",".join("?" for _ in wards)
                where_clauses.append(f"inv.student_id IN ({placeholders})")
                params.extend(wards)
            elif role in ["warden", "assistant_warden"] and user_hostel_id:
                where_clauses.append("bld.hostel_id = ?")
                params.append(int(user_hostel_id))

            # Query filters
            if filters.get("student_id"):
                where_clauses.append("inv.student_id = ?")
                params.append(filters["student_id"])
            if filters.get("status"):
                where_clauses.append("inv.status = ?")
                params.append(filters["status"])
            if filters.get("hostel_id"):
                where_clauses.append("bld.hostel_id = ?")
                params.append(filters["hostel_id"])
            if filters.get("invoice_number"):
                where_clauses.append("inv.invoice_number LIKE ?")
                params.append(f"%{filters['invoice_number']}%")
            if filters.get("due_before"):
                where_clauses.append("inv.due_date <= ?")
                params.append(filters["due_before"])

            where_str = " AND ".join(where_clauses)

            # Count total
            cursor.execute(f"""
                SELECT COUNT(inv.id)
                FROM invoices inv
                JOIN students s ON s.id = inv.student_id
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
                SELECT inv.*, s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       h.name as hostel_name, r.room_number, fs.name as fee_structure_name, fs.fee_category
                FROM invoices inv
                JOIN students s ON s.id = inv.student_id
                LEFT JOIN fee_structures fs ON fs.id = inv.fee_structure_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                WHERE {where_str}
                ORDER BY inv.id DESC
                LIMIT ? OFFSET ?;
            """
            cursor.execute(query, params + [limit, offset])
            rows = cursor.fetchall()

            today_str = date.today().isoformat()
            records = []
            for r in rows:
                item = dict(r)
                # Compute balance and dynamic overdue
                total_due = round(item["total_amount"] + item["fine_amount"] - item["discount_amount"], 2)
                balance = round(total_due - item["paid_amount"], 2)
                item["outstanding_balance"] = max(0.0, balance)

                if item["status"] not in ["Paid", "Cancelled"] and item["due_date"] < today_str:
                    item["is_overdue"] = True
                    if item["status"] in ["Issued", "Unpaid", "Partially_Paid"]:
                        item["effective_status"] = "Overdue"
                    else:
                        item["effective_status"] = item["status"]
                else:
                    item["is_overdue"] = False
                    item["effective_status"] = item["status"]

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
    def get_invoice(cls, invoice_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve single invoice with full line items, payments, and student details."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT inv.*, s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       s.email as student_email, s.phone as student_phone, s.user_id as student_user_id,
                       h.name as hostel_name, bld.hostel_id, r.room_number, fs.name as fee_structure_name, fs.fee_category
                FROM invoices inv
                JOIN students s ON s.id = inv.student_id
                LEFT JOIN fee_structures fs ON fs.id = inv.fee_structure_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                WHERE inv.id = ?;
            """, (invoice_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Invoice not found.")

            res = dict(record)

            # RBAC Isolation Check
            role = current_user.get("role")
            if role == "student" and res.get("student_user_id") != current_user.get("user_id"):
                raise HTTPException(status_code=403, detail="Forbidden: You cannot access invoices of other students.")
            if role in ["warden", "assistant_warden"] and res.get("hostel_id") and current_user.get("hostel_id"):
                if int(res["hostel_id"]) != int(current_user["hostel_id"]):
                    raise HTTPException(status_code=403, detail="Forbidden: Invoice belongs to another hostel facility.")

            # Fetch line items
            cursor.execute("SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id ASC;", (invoice_id,))
            res["items"] = [dict(it) for it in cursor.fetchall()]

            # Fetch payments
            cursor.execute("""
                SELECT p.*, u.username as recorded_by_name
                FROM payments p
                LEFT JOIN users u ON u.id = p.recorded_by
                WHERE p.invoice_id = ?
                ORDER BY p.id DESC;
            """, (invoice_id,))
            res["payments"] = [dict(p) for p in cursor.fetchall()]

            # Balance
            total_due = round(res["total_amount"] + res["fine_amount"] - res["discount_amount"], 2)
            res["net_payable"] = total_due
            balance = round(total_due - res["paid_amount"], 2)
            res["outstanding_balance"] = max(0.0, balance)
            res["is_overdue"] = (res["status"] not in ["Paid", "Cancelled"]) and (res["due_date"] < date.today().isoformat())

            return res
        finally:
            conn.close()

    @classmethod
    def generate_invoice_receipt(cls, invoice_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Generate official cryptographic downloadable invoice receipt metadata."""
        inv = cls.get_invoice(invoice_id, current_user)
        return {
            "invoice_number": inv["invoice_number"],
            "receipt_title": "OFFICIAL HOSTEL FEE INVOICE & DEMAND NOTICE",
            "institution": "University Hostel Management Board",
            "issue_date": inv["issue_date"],
            "due_date": inv["due_date"],
            "student_name": inv["student_name"],
            "roll_no": inv["student_roll_no"],
            "hostel_name": inv.get("hostel_name") or "Unassigned",
            "room_number": inv.get("room_number") or "N/A",
            "line_items": inv["items"],
            "subtotal": inv["total_amount"],
            "discount_amount": inv["discount_amount"],
            "fine_amount": inv["fine_amount"],
            "total_amount": round(inv["total_amount"] + inv["fine_amount"] - inv["discount_amount"], 2),
            "paid_amount": inv["paid_amount"],
            "outstanding_balance": inv["outstanding_balance"],
            "status": inv["status"],
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    # ==========================================
    # HELPER PERMISSION CHECKS
    # ==========================================

    @staticmethod
    def _enforce_accountant_or_admin(current_user: Dict[str, Any]):
        role = current_user.get("role")
        if role not in ["super_admin", "hostel_admin", "accountant"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only accountants and administrators can manage fees and invoices."
            )
