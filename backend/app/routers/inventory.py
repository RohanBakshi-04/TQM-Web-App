"""
FastAPI Router for Inventory, Stock, and Supplier Management
Course: BBAT104 Fundamentals of TQM
Quality Goal: Q05 - Response Time < 10ms SLA
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from backend.app.services.auth_dependencies import get_current_user
from backend.app.models.inventory_dto import (
    SupplierCreate, SupplierUpdate, SupplierResponse,
    InventoryCategoryCreate, InventoryCategoryResponse,
    InventoryItemCreate, InventoryItemUpdate, InventoryItemResponse,
    StockInwardCreate, StockOutwardCreate, StockAdjustmentCreate,
    StockTransactionResponse, InventoryDashboardResponse
)
from backend.app.services.inventory_service import InventoryService

inventory_router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory Management"])


# ==========================================
# 1. CATEGORIES
# ==========================================

@inventory_router.get("/categories", response_model=List[InventoryCategoryResponse], summary="List inventory categories")
def list_categories(current_user: Dict[str, Any] = Depends(get_current_user)):
    return InventoryService.list_categories()


@inventory_router.post("/categories", response_model=InventoryCategoryResponse, status_code=status.HTTP_201_CREATED, summary="Create an inventory category")
def create_category(
    payload: InventoryCategoryCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return InventoryService.create_category(payload)


# ==========================================
# 2. SUPPLIERS
# ==========================================

@inventory_router.get("/suppliers", response_model=List[SupplierResponse], summary="List suppliers")
def list_suppliers(
    active_only: bool = Query(False, description="Filter active suppliers only"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return InventoryService.list_suppliers(active_only=active_only)


@inventory_router.get("/suppliers/{supplier_id}", response_model=SupplierResponse, summary="Get supplier details")
def get_supplier(
    supplier_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return InventoryService.get_supplier(supplier_id)


@inventory_router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED, summary="Create a supplier")
def create_supplier(
    payload: SupplierCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return InventoryService.create_supplier(payload, user_id=current_user["id"])


@inventory_router.put("/suppliers/{supplier_id}", response_model=SupplierResponse, summary="Update supplier details")
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return InventoryService.update_supplier(supplier_id, payload, user_id=current_user["id"])


# ==========================================
# 3. INVENTORY ITEMS
# ==========================================

@inventory_router.get("/items", response_model=List[InventoryItemResponse], summary="List inventory items with filters")
def list_items(
    category_id: Optional[int] = Query(None, description="Filter by category"),
    supplier_id: Optional[int] = Query(None, description="Filter by supplier"),
    status: Optional[str] = Query(None, description="Filter by status"),
    low_stock: bool = Query(False, description="Filter low stock items"),
    expiring_soon: bool = Query(False, description="Filter items expiring in 30 days"),
    search: Optional[str] = Query(None, description="Search by name or item code"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return InventoryService.list_items(
        category_id=category_id,
        supplier_id=supplier_id,
        status=status,
        low_stock_only=low_stock,
        expiring_soon_only=expiring_soon,
        search=search
    )


@inventory_router.get("/items/{item_id}", response_model=InventoryItemResponse, summary="Get inventory item details")
def get_item(
    item_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return InventoryService.get_item(item_id)


@inventory_router.post("/items", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED, summary="Create new inventory item")
def create_item(
    payload: InventoryItemCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return InventoryService.create_item(payload, user_id=current_user["id"])


@inventory_router.put("/items/{item_id}", response_model=InventoryItemResponse, summary="Update inventory item")
def update_item(
    item_id: int,
    payload: InventoryItemUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return InventoryService.update_item(item_id, payload, user_id=current_user["id"])


# ==========================================
# 4. STOCK TRANSACTIONS (POKA-YOKE)
# ==========================================

@inventory_router.post("/stock/inward", response_model=StockTransactionResponse, status_code=status.HTTP_201_CREATED, summary="Record stock procurement inward")
def stock_inward(
    payload: StockInwardCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return InventoryService.record_stock_inward(payload, user_id=current_user["id"])


@inventory_router.post("/stock/outward", response_model=StockTransactionResponse, status_code=status.HTTP_201_CREATED, summary="Record stock outward with Poka-Yoke check")
def stock_outward(
    payload: StockOutwardCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return InventoryService.record_stock_outward(payload, user_id=current_user["id"])


@inventory_router.post("/stock/adjustment", response_model=StockTransactionResponse, status_code=status.HTTP_201_CREATED, summary="Record stock adjustment / wastage")
def stock_adjustment(
    payload: StockAdjustmentCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return InventoryService.record_stock_adjustment(payload, user_id=current_user["id"])


@inventory_router.get("/transactions", response_model=List[StockTransactionResponse], summary="List stock transactions")
def list_transactions(
    item_id: Optional[int] = Query(None, description="Filter by item ID"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return InventoryService.list_transactions(item_id=item_id, transaction_type=transaction_type, limit=limit)


# ==========================================
# 5. DASHBOARD & ALERTS
# ==========================================

@inventory_router.get("/dashboard", response_model=InventoryDashboardResponse, summary="Inventory telemetry and dashboard metrics")
def get_inventory_dashboard(current_user: Dict[str, Any] = Depends(get_current_user)):
    return InventoryService.get_dashboard()
