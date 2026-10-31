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
    contact_person: Optional[str] = Field("", max_length=100)
    phone: Optional[str] = Field("", max_length=30)
    email: Optional[str] = Field("", max_length=100)
    address: Optional[str] = Field("", max_length=255)
    category: Optional[str] = Field("General", max_length=100)
    is_active: bool = True


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    contact_person: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class SupplierResponse(BaseModel):
    id: int
    name: str
    contact_person: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    address: Optional[str] = ""
    category: Optional[str] = "General"
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==================== INVENTORY CATEGORY DTOs ====================
class InventoryCategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field("", max_length=255)
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
    max_stock_threshold: Optional[float] = Field(None, ge=0.0)
    unit_price: float = Field(0.0, ge=0.0)
    supplier_id: Optional[int] = None
    storage_location: Optional[str] = Field("Main Store", max_length=100)
    expiry_date: Optional[str] = None
    description: Optional[str] = Field("", max_length=255)
    status: str = Field("Active", pattern="^(Active|Available|Inactive|Discontinued|Low_Stock|Out_of_Stock)$")


class InventoryItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    category_id: Optional[int] = None
    unit: Optional[str] = Field(None, max_length=30)
    min_reorder_level: Optional[float] = Field(None, ge=0.0)
    max_stock_threshold: Optional[float] = Field(None, ge=0.0)
    unit_price: Optional[float] = Field(None, ge=0.0)
    supplier_id: Optional[int] = None
    storage_location: Optional[str] = Field(None, max_length=100)
    expiry_date: Optional[str] = None
    description: Optional[str] = None
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
    max_stock_threshold: Optional[float] = None
    unit_price: float
    total_valuation: float = 0.0
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    storage_location: Optional[str] = "Main Store"
    expiry_date: Optional[str] = None
    is_low_stock: bool = False
    is_expiring_soon: bool = False
    status: str
    description: Optional[str] = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==================== STOCK TRANSACTIONS DTOs ====================
class StockInwardCreate(BaseModel):
    item_id: int
    quantity: float = Field(..., gt=0.0)
    unit_price: Optional[float] = Field(None, ge=0.0)
    supplier_id: Optional[int] = None
    invoice_reference: Optional[str] = Field("", max_length=100)
    storage_location: Optional[str] = Field(None, max_length=100)
    remarks: Optional[str] = Field("", max_length=255)


class StockOutwardCreate(BaseModel):
    item_id: int
    quantity: float = Field(..., gt=0.0)
    department: Optional[str] = Field("Mess Kitchen", max_length=100)
    department_destination: Optional[str] = Field("Mess Kitchen", max_length=100)
    issued_to: Optional[str] = Field("", max_length=100)
    purpose: Optional[str] = Field("Departmental consumption", max_length=255)
    remarks: Optional[str] = Field("", max_length=255)


class StockAdjustmentCreate(BaseModel):
    item_id: int
    adjustment_type: str = Field("Adjustment", pattern="^(Adjustment|Damaged|Damage|Wastage|Expired|Transfer)$")
    quantity_change: Optional[float] = None
    quantity: Optional[float] = None
    reason: Optional[str] = Field(None, max_length=255)
    adjustment_reason: Optional[str] = Field(None, max_length=255)
    from_location: Optional[str] = None
    to_location: Optional[str] = None


class StockTransactionResponse(BaseModel):
    id: int
    transaction_reference: Optional[str] = None
    item_id: int
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    transaction_type: str
    quantity: float
    unit_price: Optional[float] = None
    total_amount: Optional[float] = None
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    invoice_reference: Optional[str] = None
    department_destination: Optional[str] = None
    purpose: Optional[str] = None
    approval_status: str
    approved_by: Optional[int] = None
    approved_by_name: Optional[str] = None
    created_at: Optional[str] = None
    notes: Optional[str] = None


class InventoryDashboardResponse(BaseModel):
    total_items: int
    total_valuation: float
    low_stock_count: int
    out_of_stock_count: int
    expiring_soon_count: int
    total_suppliers: int
    recent_transactions: List[StockTransactionResponse] = []
