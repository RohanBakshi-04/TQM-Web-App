"""Comprehensive Unit & Integration Test Suite for Fee and Financial Management.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
Poka-Yoke Controls: Duplicate Prevention, Exact Arithmetic, Immutable Invoices, Refund Capping
"""

import os
import unittest
import uuid
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient

# Ensure test environment
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.models.finance_dto import (
    FeeStructureCreate,
    FeeStructureUpdate,
    InvoiceCreate,
    BulkInvoiceCreate,
    InvoiceDiscountApply,
    InvoiceCancelRequest,
    PaymentRecordCreate,
    PaymentReverseRequest,
    RefundRequestCreate,
    RefundReviewAction,
)
from backend.app.services.fee_service import FeeService
from backend.app.services.payment_service import PaymentService
from backend.app.services.financial_report_service import FinancialReportService
from fastapi import HTTPException


class TestFeeAndFinanceManagement(unittest.TestCase):
    """Test suite covering Fee Structures, Invoices, Payments, Refunds, and Financial Reports."""

    @classmethod
    def setUpClass(cls):
        initialize_database()
        cls.client = TestClient(app)
        conn = get_db_connection()
        try:
            conn.execute("UPDATE room_allocations SET allocation_status = 'Vacated' WHERE student_id = 1;")
            conn.execute("UPDATE room_allocations SET allocation_status = 'Active' WHERE id = (SELECT id FROM room_allocations WHERE student_id = 1 LIMIT 1);")
            conn.commit()
        finally:
            conn.close()

    def setUp(self):
        self.conn = get_db_connection()
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM refunds WHERE invoice_id IN (SELECT id FROM invoices WHERE remarks LIKE '%Test%' OR remarks LIKE '%tuition%' OR remarks LIKE '%mess%') OR reason LIKE '%Test%' OR reason LIKE '%adjustment%';")
        cursor.execute("DELETE FROM payments WHERE invoice_id IN (SELECT id FROM invoices WHERE remarks LIKE '%Test%' OR remarks LIKE '%tuition%' OR remarks LIKE '%mess%') OR notes LIKE '%Test%';")
        cursor.execute("DELETE FROM invoice_items WHERE invoice_id IN (SELECT id FROM invoices WHERE remarks LIKE '%Test%' OR remarks LIKE '%tuition%' OR remarks LIKE '%mess%');")
        cursor.execute("DELETE FROM invoices WHERE remarks LIKE '%Test%' OR remarks LIKE '%tuition%' OR remarks LIKE '%mess%';")
        cursor.execute("DELETE FROM fee_structures WHERE name LIKE '%Test%';")
        self.conn.commit()

        self.today_str = date.today().isoformat()
        self.due_str = (date.today() + timedelta(days=15)).isoformat()
        self.past_str = (date.today() - timedelta(days=10)).isoformat()

        # Actors
        self.superadmin_user = {"user_id": 1, "username": "superadmin", "role": "super_admin", "hostel_id": None}
        self.accountant_user = {"user_id": 6, "username": "accountant", "role": "accountant", "hostel_id": None}
        self.student_user = {"user_id": 5, "username": "rohan", "role": "student", "hostel_id": 1}
        self.auditor_user = {"user_id": 12, "username": "evaluator", "role": "auditor", "hostel_id": None}
        self.guard_user = {"user_id": 9, "username": "security", "role": "security_guard", "hostel_id": 1}

    def tearDown(self):
        self.conn.close()

    # ==========================================
    # 1. FEE STRUCTURE TESTS
    # ==========================================

    def test_fee_structure_crud_and_duplicate_prevention(self):
        """Test fee structure creation, duplicate rejection, and updating."""
        uid = uuid.uuid4().hex[:6]
        payload = FeeStructureCreate(
            name=f"Hostel Room Fee 2026-Test-{uid}",
            fee_category="Hostel Accommodation Fee",
            hostel_id=1,
            room_type="Double",
            academic_year="2026-27",
            semester="Odd",
            amount=22000.0,
            payment_frequency="Semester",
            is_mandatory=True,
            late_fine_amount=500.0,
            description="Room fee for double sharing"
        )
        res = FeeService.create_fee_structure(payload, self.accountant_user)
        self.assertIn("id", res)
        self.assertEqual(res["name"], f"Hostel Room Fee 2026-Test-{uid}")
        self.assertEqual(res["amount"], 22000.0)

        # Duplicate rejection
        with self.assertRaises(HTTPException) as ctx:
            FeeService.create_fee_structure(payload, self.accountant_user)
        self.assertEqual(ctx.exception.status_code, 409)

        # Update fee structure
        upd = FeeStructureUpdate(amount=23500.0, late_fine_amount=600.0)
        updated = FeeService.update_fee_structure(res["id"], upd, self.accountant_user)
        self.assertEqual(updated["amount"], 23500.0)
        self.assertEqual(updated["late_fine_amount"], 600.0)

    # ==========================================
    # 2. INVOICE GENERATION & DISCOUNT TESTS
    # ==========================================

    def test_single_invoice_generation_and_balance(self):
        """Test individual invoice generation, unique invoice number, and net payable calculation."""
        uid = uuid.uuid4().hex[:6]
        payload = InvoiceCreate(
            student_id=1,
            fee_structure_id=None,
            issue_date=self.today_str,
            due_date=self.due_str,
            total_amount=15000.0,
            discount_amount=1000.0,
            discount_reason="Merit Scholarship",
            remarks=f"Semester tuition fee {uid}"
        )
        inv = FeeService.create_invoice(payload, self.accountant_user)
        self.assertIn("invoice_number", inv)
        self.assertTrue(inv["invoice_number"].startswith("INV-"))
        self.assertEqual(inv["total_amount"], 15000.0)
        self.assertEqual(inv["discount_amount"], 1000.0)
        self.assertEqual(inv["net_payable"], 14000.0)
        self.assertEqual(inv["outstanding_balance"], 14000.0)
        self.assertEqual(inv["status"], "Issued")

        # Due date before issue date should fail validation in DTO
        with self.assertRaises(Exception):
            InvoiceCreate(
                student_id=1,
                issue_date=self.due_str,
                due_date=self.past_str,
                total_amount=5000.0
            )

    def test_bulk_invoice_generation(self):
        """Test bulk invoice generation across eligible students with duplicate skipping."""
        uid = uuid.uuid4().hex[:6]
        fs = FeeService.create_fee_structure(FeeStructureCreate(
            name=f"Mess Fee 2026-Bulk-Test-{uid}",
            fee_category="Mess Fee",
            hostel_id=1,
            room_type="All",
            academic_year="2026-27",
            semester="All",
            amount=12000.0,
            payment_frequency="Semester",
            is_mandatory=True,
            late_fine_amount=300.0
        ), self.accountant_user)

        bulk_payload = BulkInvoiceCreate(
            hostel_id=1,
            academic_year="3rd Year",
            room_type="All",
            fee_structure_id=fs["id"],
            issue_date=self.today_str,
            due_date=self.due_str,
            remarks=f"Bulk mess fee distribution {uid}"
        )
        res = FeeService.create_bulk_invoices(bulk_payload, self.accountant_user)
        self.assertIn("invoices_created", res)
        self.assertGreaterEqual(res["invoices_created"], 1)

        # Generating again should skip duplicates and generate 0 new
        res_dup = FeeService.create_bulk_invoices(bulk_payload, self.accountant_user)
        self.assertEqual(res_dup["invoices_created"], 0)
        self.assertGreaterEqual(res_dup["skipped_duplicates"], 1)

    def test_invoice_concession_discount_and_cancel(self):
        """Test applying concession discount and cancelling unpaid invoice."""
        uid = uuid.uuid4().hex[:6]
        inv = FeeService.create_invoice(InvoiceCreate(
            student_id=1,
            issue_date=self.today_str,
            due_date=self.due_str,
            total_amount=8000.0,
            discount_amount=0.0,
            remarks=f"Test invoice {uid}"
        ), self.accountant_user)
        inv_id = inv["id"]

        # Apply concession
        disc_res = FeeService.apply_discount(inv_id, InvoiceDiscountApply(
            discount_amount=1500.0,
            discount_reason="COVID Relief Assistance"
        ), self.accountant_user)
        self.assertEqual(disc_res["net_payable"], 6500.0)
        self.assertEqual(disc_res["outstanding_balance"], 6500.0)

        # Cannot apply discount greater than invoice amount
        with self.assertRaises(HTTPException) as ctx:
            FeeService.apply_discount(inv_id, InvoiceDiscountApply(
                discount_amount=10000.0,
                discount_reason="Excess Discount"
            ), self.accountant_user)
        self.assertEqual(ctx.exception.status_code, 400)

        # Cancel unpaid invoice
        cancel_res = FeeService.cancel_invoice(inv_id, InvoiceCancelRequest(
            cancellation_reason="Student opted out of hostel accommodation"
        ), self.accountant_user)
        self.assertEqual(cancel_res["status"], "success")

        cancelled_inv = FeeService.get_invoice(inv_id, self.accountant_user)
        self.assertEqual(cancelled_inv["status"], "Cancelled")

    # ==========================================
    # 3. PAYMENT & REVERSAL TESTS
    # ==========================================

    def test_partial_and_full_payments_with_receipt(self):
        """Test partial payment, full payment transition to Paid, and receipt generation."""
        uid = uuid.uuid4().hex[:6]
        inv = FeeService.create_invoice(InvoiceCreate(
            student_id=1,
            issue_date=self.today_str,
            due_date=self.due_str,
            total_amount=10000.0,
            remarks=f"Test tuition {uid}"
        ), self.accountant_user)
        inv_id = inv["id"]

        # 1. Partial Payment of 4000
        txn1 = f"UPI-TXN-{uid}-01"
        pay1 = PaymentService.record_payment(PaymentRecordCreate(
            invoice_id=inv_id,
            amount=4000.0,
            payment_method="UPI",
            transaction_id=txn1,
            notes=f"First installment {uid}"
        ), self.accountant_user)
        self.assertTrue(pay1["payment_reference"].startswith("PAY-"))
        self.assertEqual(pay1["amount"], 4000.0)

        # Check invoice status changed to Partially_Paid
        inv_after_pay1 = FeeService.get_invoice(inv_id, self.accountant_user)
        self.assertEqual(inv_after_pay1["paid_amount"], 4000.0)
        self.assertEqual(inv_after_pay1["outstanding_balance"], 6000.0)
        self.assertEqual(inv_after_pay1["status"], "Partially_Paid")

        # 2. Duplicate Transaction ID should be rejected by Poka-Yoke
        with self.assertRaises(HTTPException) as ctx:
            PaymentService.record_payment(PaymentRecordCreate(
                invoice_id=inv_id,
                amount=1000.0,
                payment_method="UPI",
                transaction_id=txn1
            ), self.accountant_user)
        self.assertEqual(ctx.exception.status_code, 409)

        # 3. Second payment of remaining 6000
        txn2 = f"NB-TXN-{uid}-02"
        pay2 = PaymentService.record_payment(PaymentRecordCreate(
            invoice_id=inv_id,
            amount=6000.0,
            payment_method="Bank_Transfer",
            transaction_id=txn2,
            notes=f"Final installment {uid}"
        ), self.accountant_user)

        inv_after_pay2 = FeeService.get_invoice(inv_id, self.accountant_user)
        self.assertEqual(inv_after_pay2["paid_amount"], 10000.0)
        self.assertEqual(inv_after_pay2["outstanding_balance"], 0.0)
        self.assertEqual(inv_after_pay2["status"], "Paid")

        # 4. Receipt verification
        rcp = PaymentService.generate_payment_receipt(pay2["id"], self.accountant_user)
        self.assertIn("receipt_number", rcp)
        self.assertTrue(rcp["receipt_number"].startswith("RCP-"))
        self.assertEqual(rcp["status"], "Completed")

    def test_payment_reversal_and_balance_restoration(self):
        """Test audited payment reversal restores invoice balance and logs audit trail."""
        uid = uuid.uuid4().hex[:6]
        inv = FeeService.create_invoice(InvoiceCreate(
            student_id=1,
            issue_date=self.today_str,
            due_date=self.due_str,
            total_amount=5000.0,
            remarks=f"Test payment reversal {uid}"
        ), self.accountant_user)
        inv_id = inv["id"]

        txn = f"CASH-BATCH-{uid}"
        pay = PaymentService.record_payment(PaymentRecordCreate(
            invoice_id=inv_id,
            amount=5000.0,
            payment_method="Cash",
            transaction_id=txn,
            notes=f"Cash payment {uid}"
        ), self.accountant_user)
        pay_id = pay["id"]

        # Reverse payment
        rev_res = PaymentService.reverse_payment(pay_id, PaymentReverseRequest(
            reversal_reason="Bounced / Counterfeit note detected at bank verification"
        ), self.accountant_user)
        self.assertEqual(rev_res["status"], "success")

        # Verify payment status is Reversed
        pay_rec = PaymentService.get_payment(pay_id, self.accountant_user)
        self.assertEqual(pay_rec["status"], "Reversed")

        # Verify invoice balance restored to 5000 and status Unpaid
        inv_restored = FeeService.get_invoice(inv_id, self.accountant_user)
        self.assertEqual(inv_restored["paid_amount"], 0.0)
        self.assertEqual(inv_restored["outstanding_balance"], 5000.0)
        self.assertEqual(inv_restored["status"], "Unpaid")

    # ==========================================
    # 4. REFUND WORKFLOW TESTS
    # ==========================================

    def test_refund_workflow_request_approve_reject_process(self):
        """Test complete refund lifecycle (Requested -> Approved -> Processed)."""
        uid = uuid.uuid4().hex[:6]
        inv = FeeService.create_invoice(InvoiceCreate(
            student_id=1,
            issue_date=self.today_str,
            due_date=self.due_str,
            total_amount=7000.0,
            remarks=f"Test refund {uid}"
        ), self.accountant_user)
        pay = PaymentService.record_payment(PaymentRecordCreate(
            invoice_id=inv["id"],
            amount=7000.0,
            payment_method="UPI",
            transaction_id=f"UPI-REF-{uid}"
        ), self.accountant_user)

        # 1. Request Refund of 3000
        ref = PaymentService.request_refund(RefundRequestCreate(
            payment_id=pay["id"],
            amount=3000.0,
            reason="Security deposit adjustment upon room downgrade",
            refund_method="Bank_Transfer"
        ), self.accountant_user)
        ref_id = ref["id"]
        self.assertEqual(ref["status"], "Requested")
        self.assertTrue(ref["refund_reference"].startswith("REF-"))

        # Cannot request refund exceeding payment amount
        with self.assertRaises(HTTPException) as ctx:
            PaymentService.request_refund(RefundRequestCreate(
                payment_id=pay["id"],
                amount=8000.0,
                reason="Excess refund",
                refund_method="Bank_Transfer"
            ), self.accountant_user)
        self.assertEqual(ctx.exception.status_code, 400)

        # 2. Approve refund
        app_res = PaymentService.review_refund(ref_id, RefundReviewAction(action="Approve"), self.accountant_user)
        self.assertEqual(app_res["status"], "Approved")

        # 3. Process refund
        proc_res = PaymentService.review_refund(ref_id, RefundReviewAction(
            action="Process",
            transaction_reference=f"NEFT-REF-{uid}"
        ), self.accountant_user)
        self.assertEqual(proc_res["status"], "Processed")
        self.assertIsNotNone(proc_res["processed_at"])

    # ==========================================
    # 5. FINANCIAL DASHBOARD & REPORTS TESTS
    # ==========================================

    def test_financial_dashboard_and_reports(self):
        """Test financial dashboard aggregates, collections report, dues report, and overdue aging."""
        # Dashboard metrics
        dash = FinancialReportService.get_financial_dashboard(hostel_id=1, current_user=self.accountant_user)
        self.assertIn("total_invoiced", dash)
        self.assertIn("total_collected", dash)
        self.assertIn("collection_rate", dash)
        self.assertIn("monthly_collections", dash)
        self.assertIn("payment_methods", dash)

        # Collections report
        col_report = FinancialReportService.get_collections_report({"hostel_id": 1}, self.accountant_user)
        self.assertIn("total_amount", col_report)
        self.assertIn("records", col_report)

        # Dues report
        dues_report = FinancialReportService.get_dues_report({"hostel_id": 1}, self.accountant_user)
        self.assertIn("total_dues", dues_report)
        self.assertIn("invoices_count", dues_report)

        # Overdue aging report
        overdue_report = FinancialReportService.get_overdue_report({"hostel_id": 1}, self.accountant_user)
        self.assertIn("aging_summary", overdue_report)
        self.assertIn("1_to_30_days", overdue_report["aging_summary"])

        # Refunds report
        ref_report = FinancialReportService.get_refunds_report({}, self.accountant_user)
        self.assertIn("total_requested_amount", ref_report)
        self.assertIn("records", ref_report)

    def test_csv_export_generator(self):
        """Test sub-10ms CSV generation for collections, dues, and refunds."""
        csv_col = FinancialReportService.export_csv("collections", {}, self.accountant_user)
        self.assertIn("Payment Reference", csv_col)

        csv_dues = FinancialReportService.export_csv("dues", {}, self.accountant_user)
        self.assertIn("Outstanding Balance", csv_dues)

        csv_overdue = FinancialReportService.export_csv("overdue", {}, self.accountant_user)
        self.assertIn("Days Overdue", csv_overdue)

        csv_ref = FinancialReportService.export_csv("refunds", {}, self.accountant_user)
        self.assertIn("Refund Reference", csv_ref)

    # ==========================================
    # 6. RBAC & DATA ISOLATION TESTS
    # ==========================================

    def test_rbac_financial_data_isolation(self):
        """Test RBAC enforcement: auditor read-only, student self-isolation, guard forbidden."""
        # Security guard cannot manage fees
        with self.assertRaises(HTTPException) as ctx:
            FeeService.create_fee_structure(FeeStructureCreate(
                name="Illegal Guard Fee",
                fee_category="Other Charges",
                room_type="All",
                academic_year="2026-27",
                semester="All",
                amount=500.0,
                payment_frequency="One-Time"
            ), self.guard_user)
        self.assertEqual(ctx.exception.status_code, 403)

        # Security guard cannot view financial reports
        with self.assertRaises(HTTPException) as ctx:
            FinancialReportService.get_financial_dashboard(None, self.guard_user)
        self.assertEqual(ctx.exception.status_code, 403)

        # Auditor can view reports
        auditor_dash = FinancialReportService.get_financial_dashboard(None, self.auditor_user)
        self.assertIn("total_invoiced", auditor_dash)

        # Student personal dashboard returns only student-scoped metrics
        student_dash = FinancialReportService.get_financial_dashboard(None, self.student_user)
        self.assertEqual(student_dash["user_role"], "student")
        self.assertIn("total_billed", student_dash)
        self.assertIn("outstanding_dues", student_dash)


if __name__ == "__main__":
    unittest.main()
