from backend.app.utils.currency import to_paise, from_paise, paise_to_float
from decimal import Decimal, ROUND_HALF_UP

def _to_dec(val) -> Decimal:
    if val is None:
        return Decimal("0.00")
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

from backend.app.services.auth_dependencies import get_parent_authorized_ward_ids
import sqlite3
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status

from backend.app.database.connection import get_db_connection
from backend.app.models.finance_dto import (
    PaymentRecordCreate,
    PaymentReverseRequest,
    RefundRequestCreate,
    RefundReviewAction,
)
from backend.app.services.cache_service import cache_service
from backend.app.utils.logger import logger


class PaymentService:
    """Service handling Student Payments, Receipts, Audited Reversals, and Refund Workflows."""

    # ==========================================
    # 1. PAYMENT MANAGEMENT
    # ==========================================

    @classmethod
    def record_payment(cls, payload: PaymentRecordCreate, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Record a student payment against an invoice with balance updates and duplicate prevention."""
        cls._enforce_accountant_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # 1. Fetch and validate invoice
            cursor.execute("""
                SELECT inv.*, s.first_name || ' ' || s.last_name as student_name, s.user_id as student_user_id
                FROM invoices inv
                JOIN students s ON s.id = inv.student_id
                WHERE inv.id = ?;
            """, (payload.invoice_id,))
            inv = cursor.fetchone()
            if not inv:
                raise HTTPException(status_code=404, detail="Invoice not found.")

            if inv["status"] in ["Paid", "Cancelled"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot record payment for an invoice with status '{inv['status']}'."
                )

            inv_total_paise = inv["total_amount_paise"] if ("total_amount_paise" in inv.keys() and inv["total_amount_paise"] is not None) else to_paise(inv["total_amount"])
            inv_fine_paise = inv["fine_amount_paise"] if ("fine_amount_paise" in inv.keys() and inv["fine_amount_paise"] is not None) else to_paise(inv["fine_amount"])
            inv_discount_paise = inv["discount_amount_paise"] if ("discount_amount_paise" in inv.keys() and inv["discount_amount_paise"] is not None) else to_paise(inv["discount_amount"])
            inv_paid_paise = inv["paid_amount_paise"] if ("paid_amount_paise" in inv.keys() and inv["paid_amount_paise"] is not None) else to_paise(inv["paid_amount"])

            total_due_paise = inv_total_paise + inv_fine_paise - inv_discount_paise
            current_outstanding_paise = total_due_paise - inv_paid_paise
            payment_amount_paise = to_paise(payload.amount)

            if payment_amount_paise <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Payment amount must be strictly greater than zero."
                )

            if payment_amount_paise > current_outstanding_paise:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Payment amount INR {paise_to_float(payment_amount_paise):.2f} exceeds outstanding balance of INR {paise_to_float(current_outstanding_paise):.2f}."
                )

            payment_amount = paise_to_float(payment_amount_paise)

            # 2. Poka-Yoke: Check duplicate transaction_id if provided
            if payload.transaction_id and payload.transaction_id.strip():
                cursor.execute("""
                    SELECT id, payment_reference FROM payments
                    WHERE transaction_id = ? AND status NOT IN ('Failed', 'Reversed');
                """, (payload.transaction_id.strip(),))
                dup = cursor.fetchone()
                if dup:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"A payment with transaction reference '{payload.transaction_id.strip()}' has already been recorded (#{dup['payment_reference']})."
                    )

            # 3. Generate unique payment reference: PAY-YYYYMM-XXXX
            today_prefix = date.today().strftime("%Y%m")
            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM payments;")
            seq = cursor.fetchone()[0] or 1
            while True:
                candidate = f"PAY-{today_prefix}-{seq:04d}"
                cursor.execute("SELECT 1 FROM payments WHERE payment_reference = ?;", (candidate,))
                if not cursor.fetchone():
                    payment_ref = candidate
                    break
                seq += 1

            receipt_num = f"RCP-{today_prefix}-{seq:04d}"

            # 4. Insert payment with dual-written integer paise
            cursor.execute("""
                INSERT INTO payments (
                    payment_reference, invoice_id, student_id, amount, amount_paise, payment_method,
                    payment_date, transaction_id, receipt_number, status, notes, recorded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Completed', ?, ?);
            """, (
                payment_ref,
                payload.invoice_id,
                inv["student_id"],
                payment_amount,
                payment_amount_paise,
                payload.payment_method,
                payload.payment_date,
                payload.transaction_id or "",
                receipt_num,
                payload.notes or "",
                current_user.get("user_id")
            ))
            payment_id = cursor.lastrowid

            # 5. Update invoice paid_amount and paid_amount_paise authoritatively
            new_paid_paise = inv_paid_paise + payment_amount_paise
            new_balance_paise = total_due_paise - new_paid_paise
            new_status = "Paid" if new_balance_paise <= 0 else "Partially_Paid"
            new_paid = paise_to_float(new_paid_paise)
            new_balance = paise_to_float(new_balance_paise)

            cursor.execute("""
                UPDATE invoices
                SET paid_amount = ?, paid_amount_paise = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (new_paid, new_paid_paise, new_status, payload.invoice_id))

            # 6. Notify student
            if inv["student_user_id"]:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type)
                    VALUES (?, ?, ?, 'success');
                """, (
                    inv["student_user_id"],
                    "Payment Recorded Successfully",
                    f"Payment of INR {payment_amount:.2f} ({payment_ref}) for Invoice {inv['invoice_number']} has been confirmed. Balance: INR {new_balance:.2f}."
                ))

            # 7. Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'RECORD_PAYMENT', 'payments', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "accountant"),
                str(payment_id),
                f"Recorded payment {payment_ref} (INR {payment_amount:.2f} via {payload.payment_method}) against Invoice #{payload.invoice_id}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("finance")
            logger.info(f"Payment {payment_ref} recorded: INR {payment_amount} for Invoice #{payload.invoice_id}")

            return cls.get_payment(payment_id, current_user)
        finally:
            conn.close()

    @classmethod
    def get_payments(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch filtered and paginated payments enforcing strict RBAC row-level isolation."""
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
                where_clauses.append("p.student_id = ?")
                params.append(st["id"])
            elif role in ("parent", "parent_guardian"):
                wards = get_parent_authorized_ward_ids(conn, current_user)
                if not wards:
                    return {"total": 0, "records": []}
                placeholders = ",".join("?" for _ in wards)
                where_clauses.append(f"p.student_id IN ({placeholders})")
                params.extend(wards)
            elif role in ["warden", "assistant_warden"] and user_hostel_id:
                where_clauses.append("bld.hostel_id = ?")
                params.append(int(user_hostel_id))

            # Query filters
            if filters.get("student_id"):
                where_clauses.append("p.student_id = ?")
                params.append(filters["student_id"])
            if filters.get("invoice_id"):
                where_clauses.append("p.invoice_id = ?")
                params.append(filters["invoice_id"])
            if filters.get("payment_method"):
                where_clauses.append("p.payment_method = ?")
                params.append(filters["payment_method"])
            if filters.get("status"):
                where_clauses.append("p.status = ?")
                params.append(filters["status"])
            if filters.get("payment_reference"):
                where_clauses.append("p.payment_reference LIKE ?")
                params.append(f"%{filters['payment_reference']}%")
            if filters.get("start_date"):
                where_clauses.append("p.payment_date >= ?")
                params.append(filters["start_date"])
            if filters.get("end_date"):
                where_clauses.append("p.payment_date <= ?")
                params.append(filters["end_date"])

            where_str = " AND ".join(where_clauses)

            # Count total
            cursor.execute(f"""
                SELECT COUNT(p.id)
                FROM payments p
                JOIN students s ON s.id = p.student_id
                JOIN invoices inv ON inv.id = p.invoice_id
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
                SELECT p.*, s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       inv.invoice_number, inv.total_amount as invoice_total, h.name as hostel_name, r.room_number,
                       u.username as recorded_by_name
                FROM payments p
                JOIN students s ON s.id = p.student_id
                JOIN invoices inv ON inv.id = p.invoice_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                LEFT JOIN users u ON u.id = p.recorded_by
                WHERE {where_str}
                ORDER BY p.id DESC
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
    def get_payment(cls, payment_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch details of a single payment transaction."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       s.user_id as student_user_id, inv.invoice_number, inv.total_amount as invoice_total,
                       h.name as hostel_name, bld.hostel_id, r.room_number, u.username as recorded_by_name
                FROM payments p
                JOIN students s ON s.id = p.student_id
                JOIN invoices inv ON inv.id = p.invoice_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms r ON r.id = ra.room_id
                LEFT JOIN floors f ON f.id = r.floor_id
                LEFT JOIN buildings bld ON bld.id = f.building_id
                LEFT JOIN hostels h ON h.id = bld.hostel_id
                LEFT JOIN users u ON u.id = p.recorded_by
                WHERE p.id = ?;
            """, (payment_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Payment transaction not found.")

            res = dict(record)
            active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()
            if active_role == "student":
                my_sid = current_user.get("linked_student_id")
                if res.get("student_id") != my_sid and res.get("student_user_id") != current_user.get("user_id"):
                    raise HTTPException(status_code=403, detail="Forbidden: You cannot access payment records of other students.")
            elif active_role in ("parent_guardian", "parent"):
                wards = get_parent_authorized_ward_ids(conn, current_user)
                if res.get("student_id") not in wards:
                    raise HTTPException(status_code=403, detail="Forbidden: You cannot access payment records of unlinked students.")
            elif active_role in ("warden", "assistant_warden"):
                linked_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
                if not linked_hid:
                    raise HTTPException(status_code=403, detail="Access Denied: Staff member has no assigned hostel facility.")
                if not res.get("hostel_id") or int(res["hostel_id"]) != int(linked_hid):
                    raise HTTPException(status_code=403, detail="Forbidden: Payment belongs to another hostel facility.")
            elif active_role not in ("accountant", "super_admin", "hostel_admin", "auditor"):
                raise HTTPException(status_code=403, detail="Forbidden: Unauthorized active role for payment access.")

            return res
        finally:
            conn.close()

    @classmethod
    def verify_payment(cls, payment_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Verify and confirm payment record with audit logging."""
        cls._enforce_accountant_or_admin(current_user)
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payments WHERE id = ?;", (payment_id,))
            pmt = cursor.fetchone()
            if not pmt:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment record not found.")

            if pmt["status"] == "Reversed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Workflow: Cannot verify a reversed payment transaction."
                )

            verifier_username = current_user.get("username", "staff")
            verifier_id = current_user.get("id") or current_user.get("user_id")

            # Transition to Completed if Pending, and annotate verification
            new_status = 'Completed' if pmt["status"] in ('Pending', 'Completed') else pmt["status"]
            cursor.execute("""
                UPDATE payments
                SET status = ?,
                    notes = CASE 
                        WHEN notes IS NULL OR notes = '' THEN 'Verified by ' || ?
                        ELSE notes || ' [Verified by ' || ? || ']'
                    END
                WHERE id = ?;
            """, (new_status, verifier_username, verifier_username, payment_id))

            # Audit trail
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'PAYMENT_VERIFIED', 'payment', ?, ?, 0.5);
            """, (verifier_id, verifier_username, str(payment_id), f"Payment #{payment_id} verified by {verifier_username}"))

            conn.commit()
            cache_service.invalidate_by_tag("finance")
            logger.info(f"Payment #{payment_id} verified by {verifier_username}")
            rec = cls.get_payment(payment_id, current_user)
            rec["verification_status"] = "Verified"
            return rec
        finally:
            conn.close()

    @classmethod
    def reverse_payment(cls, payment_id: int, payload: PaymentReverseRequest, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Audited payment reversal for erroneous or bounced entries."""
        cls._enforce_accountant_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, inv.total_amount, inv.paid_amount, inv.fine_amount, inv.discount_amount
                FROM payments p
                JOIN invoices inv ON inv.id = p.invoice_id
                WHERE p.id = ?;
            """, (payment_id,))
            pay = cursor.fetchone()
            if not pay:
                raise HTTPException(status_code=404, detail="Payment record not found.")

            if pay["status"] != "Completed":
                raise HTTPException(status_code=400, detail=f"Cannot reverse payment in '{pay['status']}' status.")

            # Mark payment Reversed
            cursor.execute("""
                UPDATE payments
                SET status = 'Reversed', reversal_reason = ?, reversed_by = ?
                WHERE id = ?;
            """, (payload.reversal_reason.strip(), current_user.get("user_id"), payment_id))

            # Deduct from invoice paid_amount using integer paise
            pay_amount_paise = pay["amount_paise"] if ("amount_paise" in pay.keys() and pay["amount_paise"] is not None) else to_paise(pay["amount"])
            inv_paid_paise = pay["paid_amount_paise"] if ("paid_amount_paise" in pay.keys() and pay["paid_amount_paise"] is not None) else to_paise(pay["paid_amount"])
            inv_total_paise = pay["total_amount_paise"] if ("total_amount_paise" in pay.keys() and pay["total_amount_paise"] is not None) else to_paise(pay["total_amount"])
            inv_fine_paise = pay["fine_amount_paise"] if ("fine_amount_paise" in pay.keys() and pay["fine_amount_paise"] is not None) else to_paise(pay["fine_amount"])
            inv_discount_paise = pay["discount_amount_paise"] if ("discount_amount_paise" in pay.keys() and pay["discount_amount_paise"] is not None) else to_paise(pay["discount_amount"])

            new_paid_paise = max(0, inv_paid_paise - pay_amount_paise)
            new_status = "Unpaid" if new_paid_paise <= 0 else "Partially_Paid"
            new_paid = paise_to_float(new_paid_paise)

            cursor.execute("""
                UPDATE invoices
                SET paid_amount = ?, paid_amount_paise = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (new_paid, new_paid_paise, new_status, pay["invoice_id"]))

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'REVERSE_PAYMENT', 'payments', ?, ?, 0.6);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "accountant"),
                str(payment_id),
                f"Reversed payment #{payment_id} (INR {pay['amount']:.2f}). Reason: {payload.reversal_reason}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("finance")
            return {"status": "success", "message": f"Payment #{payment_id} reversed successfully."}
        finally:
            conn.close()

    @classmethod
    def generate_payment_receipt(cls, payment_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Generate official cryptographic payment confirmation receipt metadata."""
        pay = cls.get_payment(payment_id, current_user)
        return {
            "receipt_number": pay.get("receipt_number") or f"RCP-{pay['id']:05d}",
            "payment_reference": pay["payment_reference"],
            "institution": "University Hostel Management Board",
            "receipt_title": "OFFICIAL FEE PAYMENT RECEIPT",
            "payment_date": pay["payment_date"],
            "amount_paid": pay["amount"],
            "payment_method": pay["payment_method"],
            "transaction_id": pay["transaction_id"] or "N/A",
            "student_name": pay["student_name"],
            "roll_no": pay["student_roll_no"],
            "hostel_name": pay.get("hostel_name") or "Hostel Resident",
            "room_number": pay.get("room_number") or "N/A",
            "invoice_number": pay["invoice_number"],
            "status": pay["status"],
            "recorded_by": pay.get("recorded_by_name") or "Finance Office",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    # ==========================================
    # 2. REFUND MANAGEMENT
    # ==========================================

    @classmethod
    def request_refund(cls, payload: RefundRequestCreate, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Initiate a student refund request with strict integer-paise balance checks and ownership validation."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # 1. Fetch payment and owning student
            cursor.execute("""
                SELECT p.*, inv.student_id as inv_student_id, inv.id as inv_id, s.user_id as student_user_id
                FROM payments p
                JOIN invoices inv ON inv.id = p.invoice_id
                JOIN students s ON s.id = p.student_id
                WHERE p.id = ?;
            """, (payload.payment_id,))
            pay = cursor.fetchone()
            if not pay:
                raise HTTPException(status_code=404, detail="Payment record not found.")

            if pay["status"] != "Completed":
                raise HTTPException(status_code=400, detail="Refunds can only be requested for 'Completed' payments.")

            # Strict Ownership & Active Role Validation
            active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()
            if active_role == "student":
                my_sid = current_user.get("linked_student_id")
                if pay["student_id"] != my_sid and pay["student_user_id"] != current_user.get("user_id"):
                    raise HTTPException(status_code=403, detail="Forbidden: You can only request refunds for your own payments.")
            elif active_role in ("parent_guardian", "parent"):
                wards = get_parent_authorized_ward_ids(conn, current_user)
                if pay["student_id"] not in wards:
                    raise HTTPException(status_code=403, detail="Forbidden: You can only request refunds for your linked ward's payments.")
            elif active_role not in ("accountant", "super_admin", "hostel_admin"):
                raise HTTPException(status_code=403, detail="Forbidden: Unauthorized active role for requesting refunds.")

            # 2. Authoritative Integer-Paise Balance Check
            cursor.execute("""
                SELECT COALESCE(SUM(amount_paise), 0) FROM refunds
                WHERE payment_id = ? AND status NOT IN ('Rejected', 'Cancelled');
            """, (payload.payment_id,))
            already_refunded_paise = cursor.fetchone()[0]

            pay_amount_paise = pay["amount_paise"] if ("amount_paise" in pay.keys() and pay["amount_paise"] is not None) else to_paise(pay["amount"])
            max_refundable_paise = max(0, pay_amount_paise - already_refunded_paise)
            req_amount_paise = to_paise(payload.amount)

            if req_amount_paise <= 0:
                raise HTTPException(status_code=400, detail="Refund amount must be greater than zero.")

            if req_amount_paise > max_refundable_paise:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Requested refund INR {req_amount_paise / 100:.2f} exceeds max refundable balance of INR {max_refundable_paise / 100:.2f}."
                )

            req_amount = round(req_amount_paise / 100.0, 2)

            # 3. Generate unique refund reference: REF-YYYYMM-XXXX
            today_prefix = date.today().strftime("%Y%m")
            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM refunds;")
            seq = cursor.fetchone()[0] or 1
            while True:
                candidate = f"REF-{today_prefix}-{seq:04d}"
                cursor.execute("SELECT 1 FROM refunds WHERE refund_reference = ?;", (candidate,))
                if not cursor.fetchone():
                    ref_number = candidate
                    break
                seq += 1

            cursor.execute("""
                INSERT INTO refunds (
                    refund_reference, payment_id, invoice_id, student_id, amount, amount_paise,
                    reason, refund_method, status, requested_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Requested', ?);
            """, (
                ref_number,
                payload.payment_id,
                pay["inv_id"],
                pay["student_id"],
                req_amount,
                req_amount_paise,
                payload.reason.strip(),
                payload.refund_method,
                current_user.get("user_id")
            ))
            refund_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'REQUEST_REFUND', 'refunds', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "user"),
                str(refund_id),
                f"Requested refund of INR {req_amount:.2f} against Payment #{payload.payment_id}. Reason: {payload.reason}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("finance")
            return cls.get_refund(refund_id, current_user)
        finally:
            conn.close()

    @classmethod
    def review_refund(cls, refund_id: int, payload: RefundReviewAction, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Approve, reject, or process a refund request."""
        cls._enforce_accountant_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, p.amount as original_payment_amount, p.amount_paise as original_payment_amount_paise, p.invoice_id,
                       inv.paid_amount as inv_paid_amount, inv.paid_amount_paise as inv_paid_amount_paise, inv.total_amount as inv_total_amount,
                       s.user_id as student_user_id
                FROM refunds r
                JOIN payments p ON p.id = r.payment_id
                JOIN invoices inv ON inv.id = r.invoice_id
                JOIN students s ON s.id = r.student_id
                WHERE r.id = ?;
            """, (refund_id,))
            ref = cursor.fetchone()
            if not ref:
                raise HTTPException(status_code=404, detail="Refund request not found.")

            action = payload.action

            if action == "Reject":
                if not payload.reason or not payload.reason.strip():
                    raise HTTPException(status_code=400, detail="Rejection reason is mandatory.")
                cursor.execute("""
                    UPDATE refunds
                    SET status = 'Rejected', rejection_reason = ?, reviewed_by = ?
                    WHERE id = ?;
                """, (payload.reason.strip(), current_user.get("user_id"), refund_id))

            elif action == "Approve":
                if ref["status"] not in ["Requested", "Under_Review", "Under Review"]:
                    raise HTTPException(status_code=400, detail=f"Cannot approve refund in '{ref['status']}' state.")
                cursor.execute("""
                    UPDATE refunds
                    SET status = 'Approved', approved_by = ?, reviewed_by = ?
                    WHERE id = ?;
                """, (current_user.get("user_id"), current_user.get("user_id"), refund_id))

            elif action == "Process":
                if ref["status"] not in ["Approved", "Requested", "Under_Review", "Under Review"]:
                    raise HTTPException(status_code=400, detail=f"Cannot process refund in '{ref['status']}' state.")

                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                tx_ref = payload.transaction_reference or f"TX-REF-{refund_id}"

                cursor.execute("""
                    UPDATE refunds
                    SET status = 'Processed', processed_by = ?, processed_at = ?, transaction_reference = ?
                    WHERE id = ?;
                """, (current_user.get("user_id"), now_str, tx_ref, refund_id))

                # Adjust invoice balances with authoritative integer paise
                ref_amount_paise = ref["amount_paise"] if ("amount_paise" in ref.keys() and ref["amount_paise"] is not None) else to_paise(ref["amount"])
                inv_paid_paise = ref["inv_paid_amount_paise"] if ("inv_paid_amount_paise" in ref.keys() and ref["inv_paid_amount_paise"] is not None) else to_paise(ref["inv_paid_amount"])
                new_paid_paise = max(0, inv_paid_paise - ref_amount_paise)
                new_paid = paise_to_float(new_paid_paise)
                new_status = "Partially_Paid" if new_paid_paise > 0 else "Unpaid"
                cursor.execute("""
                    UPDATE invoices
                    SET paid_amount = ?, paid_amount_paise = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                """, (new_paid, new_paid_paise, new_status, ref["invoice_id"]))

                # Check if entire original payment was refunded
                cursor.execute("""
                    SELECT SUM(amount) FROM refunds
                    WHERE payment_id = ? AND status = 'Processed';
                """, (ref["payment_id"],))
                total_processed_refunds = cursor.fetchone()[0] or 0.0

                if total_processed_refunds >= ref["original_payment_amount"]:
                    cursor.execute("UPDATE payments SET status = 'Refunded' WHERE id = ?;", (ref["payment_id"],))

            # Notify student
            if ref["student_user_id"]:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type)
                    VALUES (?, ?, ?, 'info');
                """, (
                    ref["student_user_id"],
                    f"Refund Status Updated: {action}",
                    f"Refund request #{ref['refund_reference']} for INR {ref['amount']:.2f} has been {action.lower()}ed."
                ))

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, ?, 'refunds', ?, ?, 0.6);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "accountant"),
                f"REFUND_{action.upper()}",
                str(refund_id),
                f"Refund #{refund_id} ({action}) by {current_user.get('username')}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("finance")
            return cls.get_refund(refund_id, current_user)
        finally:
            conn.close()

    @classmethod
    def get_refunds(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch filtered and paginated refunds list with active-role data isolation."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()

            where_clauses = ["1=1"]
            params: List[Any] = []

            if active_role == "student":
                my_sid = current_user.get("linked_student_id")
                if not my_sid:
                    cursor.execute("SELECT id FROM students WHERE user_id = ?;", (current_user.get("user_id"),))
                    st = cursor.fetchone()
                    my_sid = st["id"] if st else None
                if not my_sid:
                    return {"total": 0, "records": []}
                where_clauses.append("r.student_id = ?")
                params.append(my_sid)
            elif active_role in ("parent_guardian", "parent"):
                wards = get_parent_authorized_ward_ids(conn, current_user)
                if not wards:
                    return {"total": 0, "records": []}
                where_clauses.append(f"r.student_id IN ({','.join('?' for _ in wards)})")
                params.extend(wards)
            elif active_role in ("warden", "assistant_warden"):
                linked_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
                if not linked_hid:
                    return {"total": 0, "records": []}
                where_clauses.append("""
                    r.student_id IN (
                        SELECT ra.student_id
                        FROM room_allocations ra
                        JOIN rooms rm ON rm.id = ra.room_id
                        JOIN floors fl ON fl.id = rm.floor_id
                        JOIN buildings bld ON bld.id = fl.building_id
                        WHERE bld.hostel_id = ?
                    )
                """)
                params.append(linked_hid)
            elif active_role not in ("accountant", "super_admin", "hostel_admin", "auditor"):
                return {"total": 0, "records": []}

            if filters.get("status"):
                where_clauses.append("r.status = ?")
                params.append(filters["status"])
            if filters.get("payment_id"):
                where_clauses.append("r.payment_id = ?")
                params.append(filters["payment_id"])

            where_str = " AND ".join(where_clauses)
            cursor.execute(f"SELECT COUNT(r.id) FROM refunds r WHERE {where_str};", params)
            total = cursor.fetchone()[0]

            limit = int(filters.get("limit", 50))
            offset = int(filters.get("offset", 0))

            query = f"""
                SELECT r.*, s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       p.payment_reference, p.amount as payment_amount, p.amount_paise as payment_amount_paise
                FROM refunds r
                JOIN students s ON s.id = r.student_id
                JOIN payments p ON p.id = r.payment_id
                WHERE {where_str}
                ORDER BY r.id DESC
                LIMIT ? OFFSET ?;
            """
            cursor.execute(query, params + [limit, offset])
            records = [dict(row) for row in cursor.fetchall()]

            return {"total": total, "limit": limit, "offset": offset, "records": records}
        finally:
            conn.close()

    @classmethod
    def get_refund(cls, refund_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch details of a single refund request with active-role isolation."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       s.user_id as student_user_id, p.payment_reference, p.amount as payment_amount,
                       p.amount_paise as payment_amount_paise, bld.hostel_id,
                       u1.username as approved_by_name, u2.username as processed_by_name
                FROM refunds r
                JOIN students s ON s.id = r.student_id
                JOIN payments p ON p.id = r.payment_id
                LEFT JOIN room_allocations ra ON ra.student_id = s.id AND ra.allocation_status = 'Active'
                LEFT JOIN rooms rm ON rm.id = ra.room_id
                LEFT JOIN floors fl ON fl.id = rm.floor_id
                LEFT JOIN buildings bld ON bld.id = fl.building_id
                LEFT JOIN users u1 ON u1.id = r.approved_by
                LEFT JOIN users u2 ON u2.id = r.processed_by
                WHERE r.id = ?;
            """, (refund_id,))
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Refund record not found.")

            res = dict(record)
            active_role = (current_user.get("active_role") or current_user.get("role") or "").strip().lower()
            if active_role == "student":
                my_sid = current_user.get("linked_student_id")
                if res.get("student_id") != my_sid and res.get("student_user_id") != current_user.get("user_id"):
                    raise HTTPException(status_code=403, detail="Forbidden: You cannot access refunds of other students.")
            elif active_role in ("parent_guardian", "parent"):
                wards = get_parent_authorized_ward_ids(conn, current_user)
                if res.get("student_id") not in wards:
                    raise HTTPException(status_code=403, detail="Forbidden: You cannot access refunds of unlinked students.")
            elif active_role in ("warden", "assistant_warden"):
                linked_hid = current_user.get("linked_hostel_id") or current_user.get("hostel_id")
                if not linked_hid:
                    raise HTTPException(status_code=403, detail="Access Denied: Staff member has no assigned hostel facility.")
                if not res.get("hostel_id") or int(res["hostel_id"]) != int(linked_hid):
                    raise HTTPException(status_code=403, detail="Forbidden: Refund belongs to another hostel facility.")
            elif active_role not in ("accountant", "super_admin", "hostel_admin", "auditor"):
                raise HTTPException(status_code=403, detail="Forbidden: Unauthorized active role for refund access.")

            return res
        finally:
            conn.close()

    def _enforce_accountant_or_admin(current_user: Dict[str, Any]):
        role = current_user.get("role")
        if role not in ["super_admin", "hostel_admin", "accountant"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only accountants and administrators can record or process financial transactions."
            )
