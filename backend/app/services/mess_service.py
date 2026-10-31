import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status

from backend.app.database.connection import get_db_connection
from backend.app.models.mess_dto import (
    MessMenuCreate,
    MessMenuUpdate,
    MessSubscriptionCreate,
    MessSubscriptionUpdate,
    MealAttendanceCreate,
    MealAttendanceCorrection,
    MealAttendanceQRVerify,
)
from backend.app.services.cache_service import cache_service
from backend.app.utils.logger import logger


class MessService:
    """Service handling Mess Menus, Student Subscriptions, Meal Attendance, and Real-Time Dining Analytics."""

    # ==========================================
    # 1. MESS MENU MANAGEMENT
    # ==========================================

    @classmethod
    def create_menu(cls, payload: MessMenuCreate, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Create a daily or weekly menu with duplicate prevention and audit logging."""
        cls._enforce_mess_manager_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Poka-Yoke Duplicate Prevention:
            # Prevent duplicate menu for identical hostel, date (or day_of_week if template), and meal_type
            if payload.menu_date:
                cursor.execute("""
                    SELECT id FROM mess_menus
                    WHERE COALESCE(hostel_id, 0) = ? AND menu_date = ? AND meal_type = ? AND status != 'Cancelled';
                """, (payload.hostel_id or 0, payload.menu_date, payload.meal_type))
            else:
                cursor.execute("""
                    SELECT id FROM mess_menus
                    WHERE COALESCE(hostel_id, 0) = ? AND day_of_week = ? AND menu_date IS NULL 
                      AND meal_type = ? AND status != 'Cancelled';
                """, (payload.hostel_id or 0, payload.day_of_week, payload.meal_type))

            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A published menu already exists for {payload.meal_type} on {payload.menu_date or payload.day_of_week}."
                )

            items_json = json.dumps(payload.items or [])
            cursor.execute("""
                INSERT INTO mess_menus (
                    hostel_id, menu_date, day_of_week, meal_type, title, items_description,
                    items, start_time, end_time, is_special, status, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                payload.hostel_id,
                payload.menu_date,
                payload.day_of_week,
                payload.meal_type,
                payload.title or "",
                payload.items_description.strip(),
                items_json,
                payload.start_time or "",
                payload.end_time or "",
                1 if payload.is_special else 0,
                payload.status,
                current_user.get("user_id")
            ))
            menu_id = cursor.lastrowid

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'CREATE_MESS_MENU', 'mess_menus', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "messmanager"),
                str(menu_id),
                f"Created {payload.meal_type} menu for {payload.menu_date or payload.day_of_week}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("mess")
            logger.info(f"Mess menu #{menu_id} created by {current_user.get('username')}")
            return cls.get_menu(menu_id, current_user)
        finally:
            conn.close()

    @classmethod
    def get_menus(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve mess menus with date, meal_type, day_of_week, and hostel filters."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            conditions = ["1=1"]
            params = []

            # Students only see Published menus
            role = current_user.get("role")
            if role == "student":
                conditions.append("status = 'Published'")
            elif filters.get("status"):
                conditions.append("status = ?")
                params.append(filters["status"])

            if filters.get("menu_date"):
                conditions.append("(menu_date = ? OR (menu_date IS NULL AND day_of_week = ?))")
                params.append(filters["menu_date"])
                try:
                    dt = datetime.strptime(filters["menu_date"], "%Y-%m-%d")
                    params.append(dt.strftime("%A"))
                except ValueError:
                    params.append("")
            elif filters.get("day_of_week"):
                conditions.append("day_of_week = ?")
                params.append(filters["day_of_week"])

            if filters.get("meal_type"):
                conditions.append("meal_type = ?")
                params.append(filters["meal_type"])

            if filters.get("hostel_id"):
                conditions.append("(hostel_id = ? OR hostel_id IS NULL)")
                params.append(filters["hostel_id"])

            where_str = " AND ".join(conditions)
            cursor.execute(f"""
                SELECT mm.*, h.name as hostel_name, u.username as created_by_username
                FROM mess_menus mm
                LEFT JOIN hostels h ON h.id = mm.hostel_id
                LEFT JOIN users u ON u.id = mm.created_by
                WHERE {where_str}
                ORDER BY mm.menu_date DESC, mm.id DESC;
            """, params)

            rows = cursor.fetchall()
            result = []
            for r in rows:
                it = dict(r)
                try:
                    it["items"] = json.loads(it["items"]) if it.get("items") else []
                except Exception:
                    it["items"] = []
                result.append(it)
            return result
        finally:
            conn.close()

    @classmethod
    def get_menu(cls, menu_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch single mess menu details."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT mm.*, h.name as hostel_name, u.username as created_by_username
                FROM mess_menus mm
                LEFT JOIN hostels h ON h.id = mm.hostel_id
                LEFT JOIN users u ON u.id = mm.created_by
                WHERE mm.id = ?;
            """, (menu_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Mess menu not found.")
            res = dict(row)
            try:
                res["items"] = json.loads(res["items"]) if res.get("items") else []
            except Exception:
                res["items"] = []
            return res
        finally:
            conn.close()

    @classmethod
    def update_menu(cls, menu_id: int, payload: MessMenuUpdate, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Update mess menu attributes with cancellation reason tracking."""
        cls._enforce_mess_manager_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mess_menus WHERE id = ?;", (menu_id,))
            menu = cursor.fetchone()
            if not menu:
                raise HTTPException(status_code=404, detail="Mess menu not found.")

            updates = []
            params = []

            if payload.title is not None:
                updates.append("title = ?")
                params.append(payload.title.strip())

            if payload.items_description is not None:
                updates.append("items_description = ?")
                params.append(payload.items_description.strip())

            if payload.items is not None:
                updates.append("items = ?")
                params.append(json.dumps(payload.items))

            if payload.start_time is not None:
                updates.append("start_time = ?")
                params.append(payload.start_time)

            if payload.end_time is not None:
                updates.append("end_time = ?")
                params.append(payload.end_time)

            if payload.is_special is not None:
                updates.append("is_special = ?")
                params.append(1 if payload.is_special else 0)

            if payload.status is not None:
                updates.append("status = ?")
                params.append(payload.status)
                if payload.status == "Cancelled":
                    updates.append("cancelled_reason = ?")
                    params.append(payload.cancelled_reason or "Cancelled by Mess Manager")

            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                cursor.execute(f"UPDATE mess_menus SET {', '.join(updates)} WHERE id = ?;", params + [menu_id])

                cursor.execute("""
                    INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                    VALUES (?, ?, 'UPDATE_MESS_MENU', 'mess_menus', ?, ?, 0.5);
                """, (
                    current_user.get("user_id"),
                    current_user.get("username", "messmanager"),
                    str(menu_id),
                    f"Updated mess menu #{menu_id}"
                ))

                conn.commit()
                cache_service.invalidate_by_tag("mess")

            return cls.get_menu(menu_id, current_user)
        finally:
            conn.close()

    @classmethod
    def delete_menu(cls, menu_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel or remove mess menu."""
        cls._enforce_mess_manager_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mess_menus WHERE id = ?;", (menu_id,))
            menu = cursor.fetchone()
            if not menu:
                raise HTTPException(status_code=404, detail="Mess menu not found.")

            if menu["status"] == "Published":
                cursor.execute("UPDATE mess_menus SET status = 'Cancelled', cancelled_reason = 'Cancelled by Manager', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (menu_id,))
                msg = f"Mess menu #{menu_id} marked as Cancelled."
            else:
                cursor.execute("DELETE FROM mess_menus WHERE id = ?;", (menu_id,))
                msg = f"Mess menu #{menu_id} successfully deleted."

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'DELETE_MESS_MENU', 'mess_menus', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "messmanager"),
                str(menu_id),
                msg
            ))

            conn.commit()
            cache_service.invalidate_by_tag("mess")
            return {"status": "success", "message": msg}
        finally:
            conn.close()

    # ==========================================
    # 2. MESS SUBSCRIPTION MANAGEMENT
    # ==========================================

    @classmethod
    def create_subscription(cls, payload: MessSubscriptionCreate, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Enroll student in mess subscription with date validation, duplicate active check, and fee integration."""
        cls._enforce_mess_manager_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # 1. Validate student exists
            cursor.execute("SELECT id, user_id, first_name || ' ' || last_name as name FROM students WHERE id = ?;", (payload.student_id,))
            student = cursor.fetchone()
            if not student:
                raise HTTPException(status_code=404, detail="Student not found.")

            # 2. Poka-Yoke Overlapping Active Subscription Check
            cursor.execute("""
                SELECT id, subscription_reference FROM mess_subscriptions
                WHERE student_id = ? AND status IN ('Active', 'Pending')
                  AND (start_date <= ? AND end_date >= ?);
            """, (payload.student_id, payload.end_date, payload.start_date))
            existing = cursor.fetchone()
            if existing and not payload.is_exempted:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Student already has an active mess subscription (#{existing['subscription_reference']}) overlapping these dates."
                )

            # 3. Calculate total fee based on duration
            try:
                d1 = datetime.strptime(payload.start_date, "%Y-%m-%d")
                d2 = datetime.strptime(payload.end_date, "%Y-%m-%d")
                days = (d2 - d1).days + 1
                months = max(1.0, round(days / 30.0, 1))
                total_fee = round(payload.monthly_fee * months, 2)
            except Exception:
                total_fee = payload.monthly_fee

            # 4. Generate unique subscription reference
            today_prefix = date.today().strftime("%Y%m")
            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM mess_subscriptions;")
            seq = cursor.fetchone()[0] or 1
            while True:
                candidate = f"SUB-{today_prefix}-{seq:04d}"
                cursor.execute("SELECT 1 FROM mess_subscriptions WHERE subscription_reference = ?;", (candidate,))
                if not cursor.fetchone():
                    sub_ref = candidate
                    break
                seq += 1

            status_val = "Active" if not payload.is_exempted else "Cancelled"

            # 5. Insert subscription
            cursor.execute("""
                INSERT INTO mess_subscriptions (
                    subscription_reference, student_id, hostel_id, plan_type, diet_type,
                    start_date, end_date, monthly_fee, total_fee, status, is_exempted,
                    exemption_reason, remarks, approved_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                sub_ref,
                payload.student_id,
                payload.hostel_id,
                payload.plan_type,
                payload.diet_type,
                payload.start_date,
                payload.end_date,
                payload.monthly_fee,
                total_fee,
                status_val,
                1 if payload.is_exempted else 0,
                payload.exemption_reason or "",
                payload.remarks or "",
                current_user.get("user_id")
            ))
            sub_id = cursor.lastrowid

            # 6. Notify student
            if student["user_id"]:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type)
                    VALUES (?, ?, ?, 'info');
                """, (
                    student["user_id"],
                    "Mess Subscription Activated",
                    f"Your {payload.diet_type} mess subscription ({sub_ref}) from {payload.start_date} to {payload.end_date} has been confirmed."
                ))

            # 7. Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'CREATE_MESS_SUBSCRIPTION', 'mess_subscriptions', ?, ?, 0.6);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "messmanager"),
                str(sub_id),
                f"Enrolled student #{payload.student_id} in {payload.plan_type} mess plan ({sub_ref})"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("mess")
            logger.info(f"Mess subscription {sub_ref} created for student #{payload.student_id}")
            return cls.get_subscription(sub_id, current_user)
        finally:
            conn.close()

    @classmethod
    def get_subscriptions(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch student mess subscriptions with role isolation and status filters."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            conditions = ["1=1"]
            params = []

            role = current_user.get("role")
            if role == "student":
                cursor.execute("SELECT id FROM students WHERE user_id = ?;", (current_user.get("user_id"),))
                st = cursor.fetchone()
                if not st:
                    return {"total": 0, "records": []}
                conditions.append("sub.student_id = ?")
                params.append(st["id"])
            elif filters.get("student_id"):
                conditions.append("sub.student_id = ?")
                params.append(filters["student_id"])

            if filters.get("status") and filters.get("status") != "all":
                conditions.append("sub.status = ?")
                params.append(filters["status"])

            if filters.get("plan_type"):
                conditions.append("sub.plan_type = ?")
                params.append(filters["plan_type"])

            if filters.get("hostel_id"):
                conditions.append("sub.hostel_id = ?")
                params.append(filters["hostel_id"])

            where_str = " AND ".join(conditions)

            cursor.execute(f"SELECT COUNT(*) FROM mess_subscriptions sub WHERE {where_str};", params)
            total = cursor.fetchone()[0]

            cursor.execute(f"""
                SELECT sub.*, s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       h.name as hostel_name, u.username as approved_by_username
                FROM mess_subscriptions sub
                JOIN students s ON s.id = sub.student_id
                LEFT JOIN hostels h ON h.id = sub.hostel_id
                LEFT JOIN users u ON u.id = sub.approved_by
                WHERE {where_str}
                ORDER BY sub.id DESC;
            """, params)

            records = [dict(r) for r in cursor.fetchall()]
            return {"total": total, "records": records}
        finally:
            conn.close()

    @classmethod
    def get_subscription(cls, sub_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch single mess subscription details with student isolation check."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sub.*, s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       s.user_id as student_user_id, h.name as hostel_name, u.username as approved_by_username
                FROM mess_subscriptions sub
                JOIN students s ON s.id = sub.student_id
                LEFT JOIN hostels h ON h.id = sub.hostel_id
                LEFT JOIN users u ON u.id = sub.approved_by
                WHERE sub.id = ?;
            """, (sub_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Mess subscription not found.")

            res = dict(row)
            role = current_user.get("role")
            if role == "student" and res.get("student_user_id") != current_user.get("user_id"):
                raise HTTPException(status_code=403, detail="Forbidden: You cannot access other students' subscriptions.")
            return res
        finally:
            conn.close()

    @classmethod
    def update_subscription_status(cls, sub_id: int, new_status: str, reason: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Lifecycle action: Suspend, Activate, Renew, or Cancel subscription."""
        cls._enforce_mess_manager_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mess_subscriptions WHERE id = ?;", (sub_id,))
            sub = cursor.fetchone()
            if not sub:
                raise HTTPException(status_code=404, detail="Mess subscription not found.")

            cursor.execute("""
                UPDATE mess_subscriptions
                SET status = ?, remarks = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (new_status, reason, sub_id))

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'UPDATE_SUBSCRIPTION_STATUS', 'mess_subscriptions', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "messmanager"),
                str(sub_id),
                f"Changed subscription #{sub_id} status to {new_status}. Reason: {reason}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("mess")
            return cls.get_subscription(sub_id, current_user)
        finally:
            conn.close()

    # ==========================================
    # 3. MEAL ATTENDANCE TRACKING
    # ==========================================

    @classmethod
    def record_meal_attendance(cls, payload: MealAttendanceCreate, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Record meal attendance with Poka-Yoke duplicate prevention and subscription validation."""
        cls._enforce_mess_manager_or_staff(current_user)

        att_date = payload.date or date.today().isoformat()
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # 1. Poka-Yoke Duplicate Prevention: UNIQUE(student_id, date, meal_type)
            cursor.execute("""
                SELECT id, marked_at FROM meal_attendance
                WHERE student_id = ? AND date = ? AND meal_type = ?;
            """, (payload.student_id, att_date, payload.meal_type))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Meal attendance for student #{payload.student_id} has already been recorded for {payload.meal_type} on {att_date}."
                )

            # 2. Check active subscription
            cursor.execute("""
                SELECT id, status FROM mess_subscriptions
                WHERE student_id = ? AND start_date <= ? AND end_date >= ? AND status = 'Active';
            """, (payload.student_id, att_date, att_date))
            sub = cursor.fetchone()
            sub_id = sub["id"] if sub else None

            # 3. Record attendance
            cursor.execute("""
                INSERT INTO meal_attendance (
                    student_id, subscription_id, hostel_id, date, meal_type,
                    verification_method, status, marked_by
                ) VALUES (?, ?, ?, ?, ?, ?, 'Present', ?);
            """, (
                payload.student_id,
                sub_id,
                payload.hostel_id,
                att_date,
                payload.meal_type,
                payload.verification_method,
                current_user.get("user_id")
            ))
            att_id = cursor.lastrowid
            conn.commit()
            cache_service.invalidate_by_tag("mess")

            return {
                "id": att_id,
                "student_id": payload.student_id,
                "date": att_date,
                "meal_type": payload.meal_type,
                "status": "Present",
                "is_subscribed": sub_id is not None,
                "verification_method": payload.verification_method
            }
        finally:
            conn.close()

    @classmethod
    def verify_qr_attendance(cls, payload: MealAttendanceQRVerify, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Verify QR data against student enrollment, check active subscription, and record attendance."""
        cls._enforce_mess_manager_or_staff(current_user)

        qr_text = payload.qr_data.strip()
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Lookup student by enrollment number or id
            cursor.execute("""
                SELECT id, student_id as roll_no, first_name || ' ' || last_name as name
                FROM students
                WHERE student_id = ? OR CAST(id AS TEXT) = ?;
            """, (qr_text, qr_text))
            student = cursor.fetchone()
            if not student:
                raise HTTPException(status_code=404, detail=f"No student found matching QR code '{qr_text}'.")

            record_payload = MealAttendanceCreate(
                student_id=student["id"],
                meal_type=payload.meal_type,
                verification_method="QR_Scan",
                hostel_id=payload.hostel_id
            )
            res = cls.record_meal_attendance(record_payload, current_user)
            res["student_name"] = student["name"]
            res["roll_no"] = student["roll_no"]
            return res
        finally:
            conn.close()

    @classmethod
    def correct_attendance(cls, attendance_id: int, payload: MealAttendanceCorrection, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Authorized correction of meal attendance status with mandatory justification."""
        cls._enforce_mess_manager_or_admin(current_user)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM meal_attendance WHERE id = ?;", (attendance_id,))
            att = cursor.fetchone()
            if not att:
                raise HTTPException(status_code=404, detail="Meal attendance record not found.")

            cursor.execute("""
                UPDATE meal_attendance
                SET status = ?, correction_reason = ?, corrected_by = ?
                WHERE id = ?;
            """, (payload.status, payload.correction_reason.strip(), current_user.get("user_id"), attendance_id))

            cursor.execute("""
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, ?, 'CORRECT_MEAL_ATTENDANCE', 'meal_attendance', ?, ?, 0.5);
            """, (
                current_user.get("user_id"),
                current_user.get("username", "messmanager"),
                str(attendance_id),
                f"Corrected meal attendance #{attendance_id} to '{payload.status}'. Reason: {payload.correction_reason}"
            ))

            conn.commit()
            cache_service.invalidate_by_tag("mess")
            return {"status": "success", "message": f"Meal attendance #{attendance_id} corrected to {payload.status}."}
        finally:
            conn.close()

    @classmethod
    def get_attendance(cls, filters: Dict[str, Any], current_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve meal attendance records with student data isolation and date filters."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            conditions = ["1=1"]
            params = []

            role = current_user.get("role")
            if role == "student":
                cursor.execute("SELECT id FROM students WHERE user_id = ?;", (current_user.get("user_id"),))
                st = cursor.fetchone()
                if not st:
                    return []
                conditions.append("ma.student_id = ?")
                params.append(st["id"])
            elif filters.get("student_id"):
                conditions.append("ma.student_id = ?")
                params.append(filters["student_id"])

            if filters.get("date"):
                conditions.append("ma.date = ?")
                params.append(filters["date"])

            if filters.get("meal_type"):
                conditions.append("ma.meal_type = ?")
                params.append(filters["meal_type"])

            if filters.get("hostel_id"):
                conditions.append("ma.hostel_id = ?")
                params.append(filters["hostel_id"])

            where_str = " AND ".join(conditions)
            cursor.execute(f"""
                SELECT ma.*, s.first_name || ' ' || s.last_name as student_name, s.student_id as student_roll_no,
                       u.username as marked_by_username
                FROM meal_attendance ma
                JOIN students s ON s.id = ma.student_id
                LEFT JOIN users u ON u.id = ma.marked_by
                WHERE {where_str}
                ORDER BY ma.marked_at DESC LIMIT 100;
            """, params)

            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ==========================================
    # 4. MESS DASHBOARD & ANALYTICS
    # ==========================================

    @classmethod
    def get_mess_dashboard(cls, hostel_id: Optional[int], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate real-time mess metrics with sub-10ms response time and caching."""
        role = current_user.get("role")
        user_id = current_user.get("user_id")

        cache_key = f"mess_dash:{role}:{user_id}:{hostel_id or 'all'}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            today_str = date.today().isoformat()

            # Student Personal Mess Dashboard
            if role == "student":
                cursor.execute("SELECT id FROM students WHERE user_id = ?;", (user_id,))
                st = cursor.fetchone()
                student_id = st["id"] if st else None

                if not student_id:
                    return {"active_subscription": None, "today_meals": [], "recent_attendance": []}

                # Current subscription
                cursor.execute("""
                    SELECT * FROM mess_subscriptions
                    WHERE student_id = ? AND status = 'Active' AND start_date <= ? AND end_date >= ?
                    ORDER BY id DESC LIMIT 1;
                """, (student_id, today_str, today_str))
                sub_row = cursor.fetchone()

                # Today's attendance
                cursor.execute("""
                    SELECT meal_type, marked_at, status FROM meal_attendance
                    WHERE student_id = ? AND date = ?;
                """, (student_id, today_str))
                today_meals = [dict(r) for r in cursor.fetchall()]

                # Recent attendance
                cursor.execute("""
                    SELECT date, meal_type, status, marked_at FROM meal_attendance
                    WHERE student_id = ? ORDER BY date DESC, marked_at DESC LIMIT 10;
                """, (student_id,))
                recent_att = [dict(r) for r in cursor.fetchall()]

                res = {
                    "role": "student",
                    "student_id": student_id,
                    "active_subscription": dict(sub_row) if sub_row else None,
                    "today_meals": today_meals,
                    "recent_attendance": recent_att
                }
                cache_service.set(cache_key, res, ttl=30.0, tags=["mess"])
                return res

            # Staff & Admin Aggregated Mess Dashboard
            cls._enforce_mess_view_access(current_user)

            hostel_clause_sub = ""
            hostel_clause_att = ""
            params_sub = []
            params_att = [today_str]

            if hostel_id:
                hostel_clause_sub = " AND hostel_id = ?"
                params_sub.append(hostel_id)
                hostel_clause_att = " AND hostel_id = ?"
                params_att.append(hostel_id)

            # 1. Active subscriptions
            cursor.execute(f"""
                SELECT COUNT(*) FROM mess_subscriptions
                WHERE status = 'Active' AND start_date <= ? AND end_date >= ? {hostel_clause_sub};
            """, [today_str, today_str] + params_sub)
            active_subs_count = cursor.fetchone()[0]

            # 2. Today's 4-Meal Attendance
            cursor.execute(f"""
                SELECT meal_type, COUNT(id) as count
                FROM meal_attendance
                WHERE date = ? AND status = 'Present' {hostel_clause_att}
                GROUP BY meal_type;
            """, params_att)
            meal_counts = {r["meal_type"]: r["count"] for r in cursor.fetchall()}

            breakfast_count = meal_counts.get("Breakfast", 0)
            lunch_count = meal_counts.get("Lunch", 0)
            snacks_count = meal_counts.get("Evening Snacks", 0) or meal_counts.get("Snacks", 0)
            dinner_count = meal_counts.get("Dinner", 0)
            total_today_consumption = breakfast_count + lunch_count + snacks_count + dinner_count

            # 3. Subscriptions expiring soon (within 7 days)
            expiry_threshold = (date.today() + timedelta(days=7)).isoformat()
            cursor.execute(f"""
                SELECT sub.subscription_reference, sub.end_date, s.first_name || ' ' || s.last_name as student_name
                FROM mess_subscriptions sub
                JOIN students s ON s.id = sub.student_id
                WHERE sub.status = 'Active' AND sub.end_date >= ? AND sub.end_date <= ? {hostel_clause_sub}
                ORDER BY sub.end_date ASC LIMIT 5;
            """, [today_str, expiry_threshold] + params_sub)
            expiring_soon = [dict(r) for r in cursor.fetchall()]

            # 4. Recent meal attendance activity
            cursor.execute(f"""
                SELECT ma.meal_type, ma.date, ma.marked_at, s.first_name || ' ' || s.last_name as student_name,
                       s.student_id as student_roll_no
                FROM meal_attendance ma
                JOIN students s ON s.id = ma.student_id
                WHERE 1=1 {hostel_clause_att}
                ORDER BY ma.marked_at DESC LIMIT 6;
            """, params_att[1:] if hostel_id else [])
            recent_activity = [dict(r) for r in cursor.fetchall()]

            dashboard_data = {
                "active_subscriptions": active_subs_count,
                "breakfast_attendance": breakfast_count,
                "lunch_attendance": lunch_count,
                "snacks_attendance": snacks_count,
                "dinner_attendance": dinner_count,
                "total_meal_consumption": total_today_consumption,
                "expiring_soon": expiring_soon,
                "recent_activity": recent_activity,
                "hostel_id": hostel_id
            }

            cache_service.set(cache_key, dashboard_data, ttl=45.0, tags=["mess"])
            return dashboard_data
        finally:
            conn.close()

    # ==========================================
    # HELPER PERMISSION CHECKS
    # ==========================================

    @staticmethod
    def _enforce_mess_manager_or_admin(current_user: Dict[str, Any]):
        role = current_user.get("role")
        if role not in ["super_admin", "hostel_admin", "mess_manager"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Access restricted to Mess Managers and Administrators."
            )

    @staticmethod
    def _enforce_mess_manager_or_staff(current_user: Dict[str, Any]):
        role = current_user.get("role")
        if role not in ["super_admin", "hostel_admin", "mess_manager", "warden", "assistant_warden"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Staff permissions required to mark meal attendance."
            )

    @staticmethod
    def _enforce_mess_view_access(current_user: Dict[str, Any]):
        role = current_user.get("role")
        if role not in ["super_admin", "hostel_admin", "mess_manager", "warden", "assistant_warden", "auditor", "accountant"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Access restricted to authorized personnel."
            )
