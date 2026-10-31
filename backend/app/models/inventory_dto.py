"""
Pydantic Models (DTOs) for Inventory, Stock, and Supplier Management
Course: BBAT104 Fundamentals of TQM
Quality Goal: Q05 - Response Time < 10ms SLA
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ==================== SUPPLIER DTOs ====================
class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: Optional[str] = Field(None, max_length=50)
    contact_person: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    is_active: bool = True


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    code: Optional[str] = Field(None, max_length=50)
    contact_person: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class SupplierResponse(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    category: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==================== INVENTORY CATEGORY DTOs ====================
class InventoryCategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    is_active: bool = True


class InventoryCategoryResponse(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None


# ==================== INVENTORY ITEM DTOs ====================
class InventoryItemCreate(BaseModel):
    item_code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=150)
    category_id: int
    unit: str = Field(..., max_length=30)
    quantity_in_stock: float = Field(0.0, ge=0.0)
    min_reorder_level: float = Field(10.0, ge=0.0)
    max_threshold: Optional[float] = Field(None, ge=0.0)
    unit_price: float = Field(0.0, ge=0.0)
    supplier_id: Optional[int] = None
    location: Optional[str] = Field(None, max_length=100)
    expiry_date: Optional[str] = None
    status: str = Field("Active", pattern="^(Active|Available|Inactive|Discontinued|Low_Stock|Out_of_Stock)$")


class InventoryItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    category_id: Optional[int] = None
    unit: Optional[str] = Field(None, max_length=30)
    min_reorder_level: Optional[float] = Field(None, ge=0.0)
    max_threshold: Optional[float] = Field(None, ge=0.0)
    unit_price: Optional[float] = Field(None, ge=0.0)
    supplier_id: Optional[int] = None
    location: Optional[str] = Field(None, max_length=100)
    expiry_date: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(Active|Available|Inactive|Discontinued|Low_Stock|Out_of_Stock)$")


class InventoryItemResponse(BaseModel):
    id: int
    item_code: str
    name: str
    category_id: int
    category_name: Optional[str] = None
    unit: str
    quantity_in_stock: float
    min_reorder_level: float
    max_threshold: Optional[float] = None
    unit_price: float
    total_valuation: float = 0.0
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    location: Optional[str] = None
    expiry_date: Optional[str] = None
    is_low_stock: bool = False
    is_expiring_soon: bool = False
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==================== STOCK TRANSACTIONS DTOs ====================
class StockInwardCreate(BaseModel):
    item_id: int
    quantity: float = Field(..., gt=0.0)
    unit_price: Optional[float] = Field(None, ge=0.0)
    supplier_id: Optional[int] = None
    invoice_ref: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=100)
    remarks: Optional[str] = Field(None, max_length=255)


class StockOutwardCreate(BaseModel):
    item_id: int
    quantity: float = Field(..., gt=0.0)
    department: str = Field(..., min_length=2, max_length=100)
    issued_to: Optional[str] = Field(None, max_length=100)
    remarks: Optional[str] = Field(None, max_length=255)


class StockAdjustmentCreate(BaseModel):
    item_id: int
    adjustment_type: str = Field(..., pattern="^(Damage|Expiry|Wastage|Audit_Discrepancy|Transfer)$")
    quantity_change: float  # can be positive or negative
    reason: str = Field(..., min_length=3, max_length=255)
    from_location: Optional[str] = None
    to_location: Optional[str] = None


class StockAdjustmentReview(BaseModel):
    action: str = Field(..., pattern="^(Approved|Rejected)$")
    remarks: Optional[str] = Field(None, max_length=255)


class StockTransactionResponse(BaseModel):
    id: int
    item_id: int
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    transaction_type: str
    quantity: float
    unit_price: Optional[float] = None
    total_amount: Optional[float] = None
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    invoice_ref: Optional[str] = None
    department: Optional[str] = None
    issued_to: Optional[str] = None
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    adjustment_reason: Optional[str] = None
    approval_status: str
    approved_by: Optional[int] = None
    approved_by_name: Optional[str] = None
    approved_at: Optional[str] = None
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: Optional[str] = None
    remarks: Optional[str] = None


class InventoryDashboardResponse(BaseModel):
    total_items: int
    total_valuation: float
    low_stock_count: int
    out_of_stock_count: int
    expiring_soon_count: int
    total_suppliers: int
    recent_transactions: List[StockTransactionResponse] = []
