"""
Inventory, Stock, and Supplier Management Service
Course: BBAT104 Fundamentals of TQM
Quality Goal: Q05 - Response Time < 10ms SLA
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status

from backend.app.database.connection import get_db_connection
from backend.app.models.inventory_dto import (
    SupplierCreate, SupplierUpdate, SupplierResponse,
    InventoryCategoryCreate, InventoryCategoryResponse,
    InventoryItemCreate, InventoryItemUpdate, InventoryItemResponse,
    StockInwardCreate, StockOutwardCreate, StockAdjustmentCreate,
    StockAdjustmentReview, StockTransactionResponse,
    InventoryDashboardResponse
)

logger = logging.getLogger("hms_app")


class InventoryService:

    @staticmethod
    def _log_audit(cursor, user_id: int, action: str, entity_name: str, entity_id: int, details: str):
        try:
            cursor.execute(
                """
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details, latency_ms)
                VALUES (?, 'inventory_manager', ?, ?, ?, ?, 0.5)
                """,
                (user_id, action, entity_name, str(entity_id), details)
            )
        except Exception as e:
            logger.warning(f"Failed to record audit log: {e}")

    # ==================== CATEGORIES ====================
    @staticmethod
    def list_categories() -> List[InventoryCategoryResponse]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, code, description, is_active, created_at "
                "FROM inventory_categories ORDER BY name ASC"
            )
            rows = cursor.fetchall()
            return [InventoryCategoryResponse(**dict(r)) for r in rows]

    @staticmethod
    def create_category(payload: InventoryCategoryCreate) -> InventoryCategoryResponse:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO inventory_categories (name, code, description, is_active) "
                "VALUES (?, ?, ?, ?)",
                (payload.name, payload.code, payload.description, 1 if payload.is_active else 0)
            )
            cat_id = cursor.lastrowid
            conn.commit()
            return InventoryCategoryResponse(
                id=cat_id,
                name=payload.name,
                code=payload.code,
                description=payload.description,
                is_active=payload.is_active,
                created_at=datetime.now().isoformat()
            )

    # ==================== SUPPLIERS ====================
    @staticmethod
    def list_suppliers(active_only: bool = False) -> List[SupplierResponse]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM suppliers"
            params = []
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY name ASC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [SupplierResponse(**dict(r)) for r in rows]

    @staticmethod
    def get_supplier(supplier_id: int) -> SupplierResponse:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Supplier not found.")
            return SupplierResponse(**dict(row))

    @staticmethod
    def create_supplier(payload: SupplierCreate, user_id: int) -> SupplierResponse:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO suppliers (name, code, contact_person, phone, email, address, tax_id, category, is_active, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    payload.name, payload.code, payload.contact_person, payload.phone,
                    payload.email, payload.address, payload.tax_id, payload.category,
                    1 if payload.is_active else 0, now, now
                )
            )
            supplier_id = cursor.lastrowid
            InventoryService._log_audit(
                cursor=cursor,
                user_id=user_id,
                action="CREATE_SUPPLIER",
                entity_name="suppliers",
                entity_id=supplier_id,
                details=f"Created supplier {payload.name} (Code: {payload.code or 'N/A'})"
            )
            conn.commit()

            return SupplierResponse(
                id=supplier_id,
                name=payload.name,
                code=payload.code,
                contact_person=payload.contact_person,
                phone=payload.phone,
                email=payload.email,
                address=payload.address,
                tax_id=payload.tax_id,
                category=payload.category,
                is_active=payload.is_active,
                created_at=now,
                updated_at=now
            )

    @staticmethod
    def update_supplier(supplier_id: int, payload: SupplierUpdate, user_id: int) -> SupplierResponse:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
            current = cursor.fetchone()
            if not current:
                raise HTTPException(status_code=404, detail="Supplier not found.")

            update_data = payload.dict(exclude_unset=True)
            if not update_data:
                return SupplierResponse(**dict(current))

            now = datetime.now().isoformat()
            fields = []
            values = []
            for k, v in update_data.items():
                if k == "is_active":
                    fields.append(f"{k} = ?")
                    values.append(1 if v else 0)
                else:
                    fields.append(f"{k} = ?")
                    values.append(v)
            fields.append("updated_at = ?")
            values.append(now)
            values.append(supplier_id)

            cursor.execute(f"UPDATE suppliers SET {', '.join(fields)} WHERE id = ?", values)
            InventoryService._log_audit(
                cursor=cursor,
                user_id=user_id,
                action="UPDATE_SUPPLIER",
                entity_name="suppliers",
                entity_id=supplier_id,
                details=f"Updated supplier fields: {list(update_data.keys())}"
            )
            conn.commit()

            cursor.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
            return SupplierResponse(**dict(cursor.fetchone()))

    # ==================== INVENTORY ITEMS ====================
    @staticmethod
    def list_items(
        category_id: Optional[int] = None,
        supplier_id: Optional[int] = None,
        status: Optional[str] = None,
        low_stock_only: bool = False,
        expiring_soon_only: bool = False,
        search: Optional[str] = None
    ) -> List[InventoryItemResponse]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT i.*, 
                       c.name AS category_name,
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
            if supplier_id:
                query += " AND i.supplier_id = ?"
                params.append(supplier_id)
            if status:
                query += " AND i.status = ?"
                params.append(status)
            if search and search.strip():
                query += " AND (i.name LIKE ? OR i.item_code LIKE ?)"
                term = f"%{search.strip()}%"
                params.extend([term, term])

            query += " ORDER BY i.name ASC"
            cursor.execute(query, params)
            rows = cursor.fetchall()

            today = date.today()
            thirty_days = today + timedelta(days=30)
            items = []

            for r in rows:
                item_dict = dict(r)
                stock = float(item_dict.get("quantity_in_stock") or 0.0)
                min_reorder = float(item_dict.get("min_reorder_level") or 0.0)
                price = float(item_dict.get("unit_price") or 0.0)
                exp_str = item_dict.get("expiry_date")

                is_low = stock <= min_reorder
                is_exp = False
                if exp_str:
                    try:
                        exp_date = datetime.strptime(exp_str[:10], "%Y-%m-%d").date()
                        is_exp = exp_date <= thirty_days
                    except Exception:
                        pass

                if low_stock_only and not is_low:
                    continue
                if expiring_soon_only and not is_exp:
                    continue

                item_dict["total_valuation"] = round(stock * price, 2)
                item_dict["is_low_stock"] = is_low
                item_dict["is_expiring_soon"] = is_exp
                items.append(InventoryItemResponse(**item_dict))

            return items

    @staticmethod
    def get_item(item_id: int) -> InventoryItemResponse:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT i.*, 
                       c.name AS category_name,
                       s.name AS supplier_name
                FROM inventory_items i
                LEFT JOIN inventory_categories c ON i.category_id = c.id
                LEFT JOIN suppliers s ON i.supplier_id = s.id
                WHERE i.id = ?
                """,
                (item_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Inventory item not found.")

            item_dict = dict(row)
            stock = float(item_dict.get("quantity_in_stock") or 0.0)
            min_reorder = float(item_dict.get("min_reorder_level") or 0.0)
            price = float(item_dict.get("unit_price") or 0.0)
            exp_str = item_dict.get("expiry_date")

            is_low = stock <= min_reorder
            is_exp = False
            if exp_str:
                try:
                    exp_date = datetime.strptime(exp_str[:10], "%Y-%m-%d").date()
                    is_exp = exp_date <= (date.today() + timedelta(days=30))
                except Exception:
                    pass

            item_dict["total_valuation"] = round(stock * price, 2)
            item_dict["is_low_stock"] = is_low
            item_dict["is_expiring_soon"] = is_exp
            return InventoryItemResponse(**item_dict)

    @staticmethod
    def create_item(payload: InventoryItemCreate, user_id: int) -> InventoryItemResponse:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check item code uniqueness
            cursor.execute("SELECT id FROM inventory_items WHERE item_code = ?", (payload.item_code,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail=f"Item code '{payload.item_code}' already exists.")

            # Validate category
            cursor.execute("SELECT id FROM inventory_categories WHERE id = ?", (payload.category_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=400, detail=f"Category ID {payload.category_id} does not exist.")

            now = datetime.now().isoformat()
            cursor.execute(
                """
                INSERT INTO inventory_items (
                    item_code, name, category_id, unit, quantity_in_stock,
                    min_reorder_level, max_threshold, unit_price, supplier_id,
                    location, expiry_date, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.item_code, payload.name, payload.category_id, payload.unit,
                    payload.quantity_in_stock, payload.min_reorder_level, payload.max_threshold,
                    payload.unit_price, payload.supplier_id, payload.location,
                    payload.expiry_date, payload.status, now, now
                )
            )
            item_id = cursor.lastrowid
            InventoryService._log_audit(
                cursor=cursor,
                user_id=user_id,
                action="CREATE_INVENTORY_ITEM",
                entity_name="inventory_items",
                entity_id=item_id,
                details=f"Created item {payload.name} [{payload.item_code}] with initial stock {payload.quantity_in_stock} {payload.unit}"
            )
            conn.commit()

            return InventoryService.get_item(item_id)

    @staticmethod
    def update_item(item_id: int, payload: InventoryItemUpdate, user_id: int) -> InventoryItemResponse:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM inventory_items WHERE id = ?", (item_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Inventory item not found.")

            update_data = payload.dict(exclude_unset=True)
            if not update_data:
                return InventoryService.get_item(item_id)

            now = datetime.now().isoformat()
            fields = []
            values = []
            for k, v in update_data.items():
                fields.append(f"{k} = ?")
                values.append(v)
            fields.append("updated_at = ?")
            values.append(now)
            values.append(item_id)

            cursor.execute(f"UPDATE inventory_items SET {', '.join(fields)} WHERE id = ?", values)
            InventoryService._log_audit(
                cursor=cursor,
                user_id=user_id,
                action="UPDATE_INVENTORY_ITEM",
                entity_name="inventory_items",
                entity_id=item_id,
                details=f"Updated item fields: {list(update_data.keys())}"
            )
            conn.commit()

            return InventoryService.get_item(item_id)

    # ==================== STOCK TRANSACTIONS (POKA-YOKE) ====================
    @staticmethod
    def record_stock_inward(payload: StockInwardCreate, user_id: int) -> StockTransactionResponse:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inventory_items WHERE id = ?", (payload.item_id,))
            item = cursor.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="Inventory item not found.")

            current_qty = float(item["quantity_in_stock"] or 0.0)
            new_qty = current_qty + payload.quantity
            now = datetime.now().isoformat()

            # Determine unit price
            effective_unit_price = payload.unit_price if payload.unit_price is not None else float(item["unit_price"] or 0.0)
            total_amt = round(payload.quantity * effective_unit_price, 2)

            # Determine new status
            min_reorder = float(item["min_reorder_level"] or 0.0)
            new_status = "Active"
            if new_qty <= 0:
                new_status = "Out_of_Stock"
            elif new_qty <= min_reorder:
                new_status = "Low_Stock"

            # 1. Update item quantity and price
            cursor.execute(
                """
                UPDATE inventory_items 
                SET quantity_in_stock = ?,
                    unit_price = ?,
                    status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (new_qty, effective_unit_price, new_status, now, payload.item_id)
            )

            # 2. Record transaction
            cursor.execute(
                """
                INSERT INTO inventory_transactions (
                    item_id, transaction_type, quantity, unit_price, total_amount,
                    supplier_id, invoice_ref, to_location, approval_status,
                    approved_by, approved_at, created_by, created_at, remarks
                ) VALUES (?, 'Inward', ?, ?, ?, ?, ?, ?, 'Approved', ?, ?, ?, ?, ?)
                """,
                (
                    payload.item_id, payload.quantity, effective_unit_price, total_amt,
                    payload.supplier_id or item["supplier_id"], payload.invoice_ref,
                    payload.location or item["location"], user_id, now, user_id, now,
                    payload.remarks or "Routine stock procurement receipt"
                )
            )
            tx_id = cursor.lastrowid
            InventoryService._log_audit(
                cursor=cursor,
                user_id=user_id,
                action="STOCK_INWARD",
                entity_name="inventory_transactions",
                entity_id=tx_id,
                details=f"Received {payload.quantity} {item['unit']} of {item['name']} [Total: INR {total_amt}]"
            )
            conn.commit()

            return InventoryService.get_transaction(tx_id)

    @staticmethod
    def record_stock_outward(payload: StockOutwardCreate, user_id: int) -> StockTransactionResponse:
        """
        Stock Outward with Poka-Yoke Zero-Negative-Inventory Enforcement:
        Rejects immediately if requested quantity exceeds quantity currently in stock.
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inventory_items WHERE id = ?", (payload.item_id,))
            item = cursor.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="Inventory item not found.")

            current_qty = float(item["quantity_in_stock"] or 0.0)

            # POKA-YOKE ENFORCEMENT: Never permit issuing more stock than available
            if current_qty < payload.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Poka-Yoke Violation: Cannot issue {payload.quantity} {item['unit']} of "
                        f"'{item['name']}'. Only {current_qty} {item['unit']} available in stock."
                    )
                )

            new_qty = current_qty - payload.quantity
            now = datetime.now().isoformat()
            unit_price = float(item["unit_price"] or 0.0)
            total_amt = round(payload.quantity * unit_price, 2)

            min_reorder = float(item["min_reorder_level"] or 0.0)
            new_status = "Active"
            if new_qty <= 0:
                new_status = "Out_of_Stock"
            elif new_qty <= min_reorder:
                new_status = "Low_Stock"

            # 1. Update item quantity atomically
            cursor.execute(
                """
                UPDATE inventory_items 
                SET quantity_in_stock = ?,
                    status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (new_qty, new_status, now, payload.item_id)
            )

            # 2. Record transaction
            cursor.execute(
                """
                INSERT INTO inventory_transactions (
                    item_id, transaction_type, quantity, unit_price, total_amount,
                    department, issued_to, approval_status, approved_by, approved_at,
                    created_by, created_at, remarks
                ) VALUES (?, 'Outward', ?, ?, ?, ?, ?, 'Approved', ?, ?, ?, ?, ?)
                """,
                (
                    payload.item_id, payload.quantity, unit_price, total_amt,
                    payload.department, payload.issued_to, user_id, now, user_id, now,
                    payload.remarks or f"Issued to {payload.department}"
                )
            )
            tx_id = cursor.lastrowid
            InventoryService._log_audit(
                cursor=cursor,
                user_id=user_id,
                action="STOCK_OUTWARD",
                entity_name="inventory_transactions",
                entity_id=tx_id,
                details=f"Issued {payload.quantity} {item['unit']} of {item['name']} to {payload.department}"
            )
            conn.commit()

            return InventoryService.get_transaction(tx_id)

    @staticmethod
    def record_stock_adjustment(payload: StockAdjustmentCreate, user_id: int) -> StockTransactionResponse:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inventory_items WHERE id = ?", (payload.item_id,))
            item = cursor.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="Inventory item not found.")

            current_qty = float(item["quantity_in_stock"] or 0.0)
            new_qty = current_qty + payload.quantity_change

            # Prevent negative inventory from adjustment
            if new_qty < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Adjustment would result in negative stock ({new_qty} {item['unit']}). Current: {current_qty}"
                )

            now = datetime.now().isoformat()
            unit_price = float(item["unit_price"] or 0.0)
            total_amt = round(abs(payload.quantity_change) * unit_price, 2)

            min_reorder = float(item["min_reorder_level"] or 0.0)
            new_status = "Active"
            if new_qty <= 0:
                new_status = "Out_of_Stock"
            elif new_qty <= min_reorder:
                new_status = "Low_Stock"

            cursor.execute(
                """
                UPDATE inventory_items 
                SET quantity_in_stock = ?,
                    status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (new_qty, new_status, now, payload.item_id)
            )

            cursor.execute(
                """
                INSERT INTO inventory_transactions (
                    item_id, transaction_type, quantity, unit_price, total_amount,
                    from_location, to_location, adjustment_reason, approval_status,
                    approved_by, approved_at, created_by, created_at, remarks
                ) VALUES (?, 'Adjustment', ?, ?, ?, ?, ?, ?, 'Approved', ?, ?, ?, ?, ?)
                """,
                (
                    payload.item_id, payload.quantity_change, unit_price, total_amt,
                    payload.from_location or item["location"], payload.to_location,
                    f"[{payload.adjustment_type}] {payload.reason}", user_id, now, user_id, now,
                    payload.reason
                )
            )
            tx_id = cursor.lastrowid
            InventoryService._log_audit(
                cursor=cursor,
                user_id=user_id,
                action="STOCK_ADJUSTMENT",
                entity_name="inventory_transactions",
                entity_id=tx_id,
                details=f"Stock adjustment {payload.quantity_change:+} {item['unit']} for {item['name']} ({payload.adjustment_type})"
            )
            conn.commit()

            return InventoryService.get_transaction(tx_id)

    @staticmethod
    def get_transaction(tx_id: int) -> StockTransactionResponse:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT t.*,
                       i.item_code,
                       i.name AS item_name,
                       s.name AS supplier_name,
                       u1.full_name AS approved_by_name,
                       u2.full_name AS created_by_name
                FROM inventory_transactions t
                JOIN inventory_items i ON t.item_id = i.id
                LEFT JOIN suppliers s ON t.supplier_id = s.id
                LEFT JOIN users u1 ON t.approved_by = u1.id
                LEFT JOIN users u2 ON t.created_by = u2.id
                WHERE t.id = ?
                """,
                (tx_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Transaction not found.")
            return StockTransactionResponse(**dict(row))

    @staticmethod
    def list_transactions(
        item_id: Optional[int] = None,
        transaction_type: Optional[str] = None,
        limit: int = 50
    ) -> List[StockTransactionResponse]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT t.*,
                       i.item_code,
                       i.name AS item_name,
                       s.name AS supplier_name,
                       u1.full_name AS approved_by_name,
                       u2.full_name AS created_by_name
                FROM inventory_transactions t
                JOIN inventory_items i ON t.item_id = i.id
                LEFT JOIN suppliers s ON t.supplier_id = s.id
                LEFT JOIN users u1 ON t.approved_by = u1.id
                LEFT JOIN users u2 ON t.created_by = u2.id
                WHERE 1=1
            """
            params: List[Any] = []
            if item_id:
                query += " AND t.item_id = ?"
                params.append(item_id)
            if transaction_type:
                query += " AND t.transaction_type = ?"
                params.append(transaction_type)

            query += " ORDER BY t.created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [StockTransactionResponse(**dict(r)) for r in rows]

    # ==================== INVENTORY DASHBOARD & ALERTS ====================
    @staticmethod
    def get_dashboard() -> InventoryDashboardResponse:
        items = InventoryService.list_items()
        suppliers = InventoryService.list_suppliers(active_only=True)
        transactions = InventoryService.list_transactions(limit=10)

        total_valuation = sum(item.total_valuation for item in items)
        low_stock_count = sum(1 for item in items if item.is_low_stock and item.quantity_in_stock > 0)
        out_of_stock_count = sum(1 for item in items if item.quantity_in_stock <= 0)
        expiring_soon_count = sum(1 for item in items if item.is_expiring_soon)

        return InventoryDashboardResponse(
            total_items=len(items),
            total_valuation=round(total_valuation, 2),
            low_stock_count=low_stock_count,
            out_of_stock_count=out_of_stock_count,
            expiring_soon_count=expiring_soon_count,
            total_suppliers=len(suppliers),
            recent_transactions=transactions
        )
