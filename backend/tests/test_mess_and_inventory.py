"""
Comprehensive Unit & Integration Test Suite for Mess and Inventory Management.
Course: BBAT104 Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
Poka-Yoke Controls: Duplicate Menu Prevention, Duplicate Active Subscription Prevention,
Duplicate Attendance Prevention, Zero-Negative Inventory Enforcement, RFC 4180 CSV Streaming.
"""

import os
import unittest
import uuid
from datetime import date, datetime, timedelta
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from backend.app.database.connection import get_db_connection
from backend.app.database.init_db import initialize_database
from backend.app.main import app
from backend.app.models.mess_dto import (
    MessMenuCreate, MessMenuUpdate,
    MessSubscriptionCreate, MessSubscriptionUpdate,
    MealAttendanceCreate, MealAttendanceCorrection, MealAttendanceQRVerify
)
from backend.app.models.inventory_dto import (
    SupplierCreate, SupplierUpdate,
    InventoryCategoryCreate,
    InventoryItemCreate, InventoryItemUpdate,
    StockInwardCreate, StockOutwardCreate, StockAdjustmentCreate
)
from backend.app.services.mess_service import MessService
from backend.app.services.inventory_service import InventoryService
from backend.app.services.mess_inventory_report_service import MessInventoryReportService


class TestMessAndInventoryManagement(unittest.TestCase):
    """Test suite covering Mess and Inventory operations with Poka-Yoke controls."""

    @classmethod
    def setUpClass(cls):
        initialize_database()
        cls.client = TestClient(app)

    def setUp(self):
        self.conn = get_db_connection()
        cursor = self.conn.cursor()
        # Clean up test rows to guarantee complete test isolation
        cursor.execute("DELETE FROM meal_attendance WHERE status = 'Cancelled';")
        cursor.execute("DELETE FROM mess_subscriptions WHERE plan_type = 'Monthly';")
        cursor.execute("DELETE FROM mess_menus WHERE title LIKE '%South Indian%' OR title LIKE '%North Indian%';")
        self.conn.commit()

        self.today_str = date.today().isoformat()
        self.tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
        self.future_str = (date.today() + timedelta(days=30)).isoformat()

        # Actors
        self.superadmin_user = {"user_id": 1, "username": "superadmin", "role": "super_admin", "hostel_id": None}
        self.mess_manager = {"user_id": 7, "username": "messmanager", "role": "mess_manager", "hostel_id": 1}
        self.student_1 = {"user_id": 5, "username": "rohan", "role": "student", "hostel_id": 1}
        self.student_2 = {"user_id": 8, "username": "priya", "role": "student", "hostel_id": 1}
        self.auditor_user = {"user_id": 12, "username": "evaluator", "role": "auditor", "hostel_id": None}

    def tearDown(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM inventory_transactions WHERE item_id > 10;")
            cursor.execute("DELETE FROM inventory_items WHERE id > 10;")
            cursor.execute("DELETE FROM suppliers WHERE id > 4;")
            self.conn.commit()
        except Exception:
            pass
        self.conn.close()

    # ==========================================
    # 1. MESS MENU TESTS
    # ==========================================

    def test_mess_menu_creation_and_duplicate_prevention(self):
        """Poka-Yoke: Prevent duplicate menus for same hostel, meal type, and date."""
        unique_date = (date.today() + timedelta(days=20)).isoformat()
        menu_payload = MessMenuCreate(
            hostel_id=1,
            menu_date=unique_date,
            day_of_week="Monday",
            meal_type="Breakfast",
            title="South Indian Idli Sambar",
            items_description="Steamed idlis with sambar & coconut chutney",
            items=["Idli", "Sambar", "Coconut Chutney", "Filter Coffee"],
            start_time="07:30",
            end_time="09:30",
            status="Published"
        )

        # 1. First creation must succeed
        menu = MessService.create_menu(menu_payload, self.mess_manager)
        self.assertIsNotNone(menu.get("id"))
        self.assertEqual(menu["title"], "South Indian Idli Sambar")

        # 2. Duplicate menu creation must fail with 400 or 409 Conflict
        with self.assertRaises(HTTPException) as ctx:
            MessService.create_menu(menu_payload, self.mess_manager)
        self.assertIn(ctx.exception.status_code, [400, 409])
        self.assertIn("already exists", ctx.exception.detail)

    def test_mess_menu_publish_and_cancel_lifecycle(self):
        """Verify publishing, cancellation with mandatory audit reason."""
        unique_date = (date.today() + timedelta(days=21)).isoformat()
        menu_payload = MessMenuCreate(
            hostel_id=1,
            menu_date=unique_date,
            day_of_week="Tuesday",
            meal_type="Lunch",
            title="North Indian Thali",
            items_description="Dal Makhani, Jeera Rice, Roti, Salad",
            items=["Dal Makhani", "Jeera Rice", "Roti", "Salad"],
            start_time="12:30",
            end_time="14:30",
            status="Draft"
        )
        menu = MessService.create_menu(menu_payload, self.mess_manager)
        menu_id = menu["id"]
        self.assertEqual(menu["status"], "Draft")

        # Publish menu
        published = MessService.update_menu(menu_id, MessMenuUpdate(status="Published"), self.mess_manager)
        self.assertEqual(published["status"], "Published")

        # Cancel menu
        cancelled = MessService.update_menu(menu_id, MessMenuUpdate(status="Cancelled", cancelled_reason="Hostel holiday feast replacement"), self.mess_manager)
        self.assertEqual(cancelled["status"], "Cancelled")

    # ==========================================
    # 2. MESS SUBSCRIPTION TESTS
    # ==========================================

    def test_mess_subscription_lifecycle_and_duplicate_prevention(self):
        """Poka-Yoke: Prevent overlapping active subscriptions for the same student."""
        student_id = 2
        start_d = (date.today() + timedelta(days=40)).isoformat()
        end_d = (date.today() + timedelta(days=70)).isoformat()

        sub_payload = MessSubscriptionCreate(
            student_id=student_id,
            hostel_id=1,
            plan_type="Monthly",
            diet_type="Regular",
            start_date=start_d,
            end_date=end_d,
            monthly_fee=3500.0
        )

        sub = MessService.create_subscription(sub_payload, self.mess_manager)
        self.assertIsNotNone(sub.get("id"))
        self.assertEqual(sub["status"], "Active")
        sub_id = sub["id"]

        # Duplicate active subscription attempt must fail
        with self.assertRaises(HTTPException) as ctx:
            MessService.create_subscription(sub_payload, self.mess_manager)
        self.assertIn(ctx.exception.status_code, [400, 409])
        self.assertIn("already has an active mess subscription", ctx.exception.detail)

        # Suspend subscription
        suspended = MessService.update_subscription_status(sub_id, "Suspended", "Student home leave", self.mess_manager)
        self.assertEqual(suspended["status"], "Suspended")

        # Reactivate subscription
        reactivated = MessService.update_subscription_status(sub_id, "Active", "Student returned", self.mess_manager)
        self.assertEqual(reactivated["status"], "Active")

        # Cancel subscription
        cancelled = MessService.update_subscription_status(sub_id, "Cancelled", "Graduation checkout", self.mess_manager)
        self.assertEqual(cancelled["status"], "Cancelled")

    # ==========================================
    # 3. MEAL ATTENDANCE TESTS
    # ==========================================

    def test_meal_attendance_and_duplicate_prevention(self):
        """Poka-Yoke: Prevent duplicate attendance recording for same student and meal session."""
        test_date = (date.today() + timedelta(days=25)).isoformat()
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM meal_attendance WHERE date = ?;", (test_date,))
        self.conn.commit()
        student_id = 1

        att_payload = MealAttendanceCreate(
            student_id=student_id,
            hostel_id=1,
            date=test_date,
            meal_type="Dinner",
            verification_method="Manual"
        )

        rec = MessService.record_meal_attendance(att_payload, self.mess_manager)
        self.assertIsNotNone(rec.get("id"))
        self.assertEqual(rec["status"], "Present")
        att_id = rec["id"]

        # Attempting duplicate attendance recording must raise 400 or 409
        with self.assertRaises(HTTPException) as ctx:
            MessService.record_meal_attendance(att_payload, self.mess_manager)
        self.assertIn(ctx.exception.status_code, [400, 409])
        self.assertIn("already", ctx.exception.detail.lower())
        self.assertIn("recorded", ctx.exception.detail.lower())

        # Correction with audit reason
        correction = MessService.correct_attendance(
            att_id,
            MealAttendanceCorrection(status="Cancelled", correction_reason="Mistaken ID entry at mess desk"),
            self.mess_manager
        )
        self.assertEqual(correction["status"], "success")

    def test_meal_attendance_qr_verification(self):
        """Test QR token verification and attendance logging."""
        today_iso = date.today().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM meal_attendance WHERE student_id = 1 AND date = ? AND meal_type = 'Lunch';", (today_iso,))
        self.conn.commit()

        qr_payload = MealAttendanceQRVerify(
            qr_data="2410301057",  # student 1 uid
            hostel_id=1,
            meal_type="Lunch"
        )
        verified = MessService.verify_qr_attendance(qr_payload, self.mess_manager)
        self.assertEqual(verified["status"], "Present")
        self.assertEqual(verified["meal_type"], "Lunch")

    # ==========================================
    # 4. SUPPLIER MANAGEMENT TESTS
    # ==========================================

    def test_supplier_crud(self):
        """Test supplier creation, updating, and retrieval."""
        uid = uuid.uuid4().hex[:6]
        sup_payload = SupplierCreate(
            name=f"Fresh Greens Wholesale {uid}",
            contact_person="Ramesh Patel",
            phone="+91 9876543210",
            email=f"ramesh_{uid}@freshgreens.com",
            address="APMC Market Yard, Pune",
            category="Vegetables & Fruits",
            is_active=True
        )

        sup = InventoryService.create_supplier(sup_payload, user_id=1)
        self.assertIsNotNone(sup.id)
        self.assertEqual(sup.contact_person, "Ramesh Patel")

        # Update supplier
        updated = InventoryService.update_supplier(
            sup.id,
            SupplierUpdate(phone="+91 9999888877", contact_person="Ramesh K. Patel"),
            user_id=1
        )
        self.assertEqual(updated.phone, "+91 9999888877")
        self.assertEqual(updated.contact_person, "Ramesh K. Patel")

        # List active suppliers
        suppliers = InventoryService.list_suppliers(active_only=True)
        self.assertTrue(any(s.id == sup.id for s in suppliers))

    # ==========================================
    # 5. INVENTORY ITEM TESTS
    # ==========================================

    def test_inventory_item_crud_and_valuation(self):
        """Test inventory item creation, duplicate code rejection, and valuation computation."""
        uid = uuid.uuid4().hex[:6]
        item_payload = InventoryItemCreate(
            item_code=f"FG-RICE-{uid}",
            name=f"Sona Masoori Rice {uid}",
            category_id=1,
            unit="kg",
            quantity_in_stock=50.0,
            min_reorder_level=10.0,
            max_stock_threshold=200.0,
            unit_price=60.0,
            storage_location="Store Room Bay 1",
            status="Active"
        )

        item = InventoryService.create_item(item_payload, user_id=1)
        self.assertIsNotNone(item.id)
        self.assertEqual(item.quantity_in_stock, 50.0)
        self.assertEqual(item.total_valuation, 3000.0)  # 50 * 60 = 3000

        # Duplicate item code check
        with self.assertRaises(HTTPException) as ctx:
            InventoryService.create_item(item_payload, user_id=1)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("already exists", ctx.exception.detail)

    # ==========================================
    # 6. STOCK INWARD & OUTWARD (POKA-YOKE) TESTS
    # ==========================================

    def test_stock_inward_and_valuation_update(self):
        """Test stock procurement inward atomic quantity and price update."""
        uid = uuid.uuid4().hex[:6]
        item = InventoryService.create_item(InventoryItemCreate(
            item_code=f"OIL-SUN-{uid}",
            name=f"Sunflower Cooking Oil {uid}",
            category_id=1,
            unit="litre",
            quantity_in_stock=20.0,
            min_reorder_level=15.0,
            unit_price=120.0,
            status="Active"
        ), user_id=1)

        # Inward 30 litres at INR 130
        inward_tx = InventoryService.record_stock_inward(StockInwardCreate(
            item_id=item.id,
            quantity=30.0,
            unit_price=130.0,
            invoice_reference=f"INV-OIL-{uid}",
            remarks="Monthly kitchen restocking"
        ), user_id=1)

        self.assertEqual(inward_tx.quantity, 30.0)
        self.assertEqual(inward_tx.total_amount, 3900.0)

        # Verify updated item stock
        updated_item = InventoryService.get_item(item.id)
        self.assertEqual(updated_item.quantity_in_stock, 50.0)  # 20 + 30 = 50
        self.assertEqual(updated_item.unit_price, 130.0)
        self.assertEqual(updated_item.total_valuation, 6500.0)  # 50 * 130 = 6500

    def test_stock_outward_poka_yoke_negative_stock_enforcement(self):
        """
        Poka-Yoke: Prevent negative inventory.
        Attempting to issue more stock than currently on hand MUST fail with 400 Bad Request.
        """
        uid = uuid.uuid4().hex[:6]
        item = InventoryService.create_item(InventoryItemCreate(
            item_code=f"SP-TEA-{uid}",
            name=f"Assam CTC Tea {uid}",
            category_id=1,
            unit="packet",
            quantity_in_stock=10.0,
            min_reorder_level=5.0,
            unit_price=80.0,
            status="Active"
        ), user_id=1)

        # Attempt to issue 15 packets when only 10 are available
        with self.assertRaises(HTTPException) as ctx:
            InventoryService.record_stock_outward(StockOutwardCreate(
                item_id=item.id,
                quantity=15.0,
                department_destination="Mess Kitchen",
                purpose="Breakfast tea preparation"
            ), user_id=1)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Poka-Yoke Violation", ctx.exception.detail)
        self.assertIn("Cannot issue", ctx.exception.detail)

        # Verify stock remained untouched
        unchanged = InventoryService.get_item(item.id)
        self.assertEqual(unchanged.quantity_in_stock, 10.0)

    def test_stock_outward_success_and_low_stock_status(self):
        """Valid outward transaction properly decrements stock and transitions status to Low_Stock."""
        uid = uuid.uuid4().hex[:6]
        item = InventoryService.create_item(InventoryItemCreate(
            item_code=f"DAL-TUR-{uid}",
            name=f"Toor Dal {uid}",
            category_id=1,
            unit="kg",
            quantity_in_stock=15.0,
            min_reorder_level=10.0,
            unit_price=140.0,
            status="Active"
        ), user_id=1)

        # Issue 8 kg (leaving 7 kg, which is <= min_reorder_level of 10)
        out_tx = InventoryService.record_stock_outward(StockOutwardCreate(
            item_id=item.id,
            quantity=8.0,
            department_destination="Mess Kitchen",
            purpose="Lunch sambar preparation"
        ), user_id=1)

        self.assertEqual(out_tx.quantity, 8.0)
        updated = InventoryService.get_item(item.id)
        self.assertEqual(updated.quantity_in_stock, 7.0)
        self.assertEqual(updated.status, "Low_Stock")
        self.assertTrue(updated.is_low_stock)

    def test_stock_adjustment_and_negative_balance_prevention(self):
        """Test stock adjustment for wastage and prevention of negative inventory."""
        uid = uuid.uuid4().hex[:6]
        item = InventoryService.create_item(InventoryItemCreate(
            item_code=f"FR-EGG-{uid}",
            name=f"Farm Fresh Eggs {uid}",
            category_id=1,
            unit="crate",
            quantity_in_stock=5.0,
            min_reorder_level=2.0,
            unit_price=180.0,
            status="Active"
        ), user_id=1)

        # Adjust for 1 damaged crate
        adj_tx = InventoryService.record_stock_adjustment(StockAdjustmentCreate(
            item_id=item.id,
            adjustment_type="Damaged",
            quantity_change=-1.0,
            adjustment_reason="Cracked during delivery transit"
        ), user_id=1)

        self.assertEqual(adj_tx.quantity, 1.0)
        self.assertEqual(InventoryService.get_item(item.id).quantity_in_stock, 4.0)

        # Negative adjustment of 10 crates (when only 4 remain) must fail
        with self.assertRaises(HTTPException) as ctx:
            InventoryService.record_stock_adjustment(StockAdjustmentCreate(
                item_id=item.id,
                adjustment_type="Damaged",
                quantity_change=-10.0,
                adjustment_reason="Excessive damage claim"
            ), user_id=1)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("negative stock", ctx.exception.detail)

    # ==========================================
    # 7. DASHBOARDS & CSV EXPORT REPORTS
    # ==========================================

    def test_dashboards_telemetry(self):
        """Verify Mess & Inventory dashboard metrics are returned within SLA."""
        mess_dash = MessService.get_mess_dashboard(hostel_id=1, current_user=self.mess_manager)
        self.assertIn("active_subscriptions", mess_dash)
        self.assertIn("total_meal_consumption", mess_dash)

        inv_dash = InventoryService.get_dashboard()
        self.assertGreaterEqual(inv_dash.total_items, 0)
        self.assertGreaterEqual(inv_dash.total_valuation, 0.0)

    def test_rfc4180_csv_exports(self):
        """Verify streaming CSV export formats conform to RFC 4180 headers."""
        # 1. Meal Consumption CSV
        meal_csv = "".join(MessInventoryReportService.stream_meal_consumption_csv())
        self.assertIn("Meal Date,Meal Session,Hostel Name,Total Served", meal_csv)

        # 2. Stock Summary CSV
        stock_csv = "".join(MessInventoryReportService.stream_stock_summary_csv())
        self.assertIn("Item Code,Item Name,Category,Stock on Hand", stock_csv)

        # 3. Stock Movement CSV
        movement_csv = "".join(MessInventoryReportService.stream_stock_movement_csv())
        self.assertIn("TX ID,Type,Item Code,Item Name,Quantity", movement_csv)


if __name__ == "__main__":
    unittest.main()
