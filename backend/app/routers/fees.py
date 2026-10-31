from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from backend.app.services.auth_dependencies import get_current_user
from backend.app.models.finance_dto import (
    FeeStructureCreate,
    FeeStructureUpdate,
    InvoiceCreate,
    BulkInvoiceCreate,
    InvoiceDiscountApply,
    InvoiceCancelRequest,
)
from backend.app.services.fee_service import FeeService

fees_router = APIRouter(prefix="/api/v1/fees", tags=["Fee & Financial Management"])


# ==========================================
# 1. FEE STRUCTURE ENDPOINTS
# ==========================================

@fees_router.get("/structures", summary="List fee structures with filters")
def list_fee_structures(
    hostel_id: Optional[int] = Query(None, description="Filter by hostel ID"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year"),
    fee_category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter active status"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    filters = {
        "hostel_id": hostel_id,
        "academic_year": academic_year,
        "fee_category": fee_category,
        "is_active": is_active
    }
    return FeeService.get_fee_structures(filters, current_user)


@fees_router.post("/structures", status_code=status.HTTP_201_CREATED, summary="Create a new fee structure")
def create_fee_structure(
    payload: FeeStructureCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return FeeService.create_fee_structure(payload, current_user)


@fees_router.get("/structures/{id}", summary="Get fee structure details by ID")
def get_fee_structure(
    id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return FeeService.get_fee_structure(id, current_user)


@fees_router.put("/structures/{id}", summary="Update a fee structure")
def update_fee_structure(
    id: int,
    payload: FeeStructureUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return FeeService.update_fee_structure(id, payload, current_user)


@fees_router.delete("/structures/{id}", summary="Delete or deactivate fee structure")
def delete_fee_structure(
    id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return FeeService.delete_fee_structure(id, current_user)


# ==========================================
# 2. INVOICE ENDPOINTS
# ==========================================

@fees_router.get("/invoices", summary="List invoices with RBAC filtering")
def list_invoices(
    student_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    hostel_id: Optional[int] = Query(None),
    invoice_number: Optional[str] = Query(None),
    due_before: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    filters = {
        "student_id": student_id,
        "status": status,
        "hostel_id": hostel_id,
        "invoice_number": invoice_number,
        "due_before": due_before,
        "limit": limit,
        "offset": offset
    }
    return FeeService.get_invoices(filters, current_user)


@fees_router.post("/invoices", status_code=status.HTTP_201_CREATED, summary="Generate an individual invoice")
def create_invoice(
    payload: InvoiceCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return FeeService.create_invoice(payload, current_user)


@fees_router.post("/invoices/bulk", status_code=status.HTTP_201_CREATED, summary="Generate bulk invoices")
def create_bulk_invoices(
    payload: BulkInvoiceCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return FeeService.create_bulk_invoices(payload, current_user)


@fees_router.get("/invoices/{id}", summary="Get single invoice details")
def get_invoice(
    id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return FeeService.get_invoice(id, current_user)


@fees_router.post("/invoices/{id}/discount", summary="Apply approved discount or concession")
def apply_discount(
    id: int,
    payload: InvoiceDiscountApply,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return FeeService.apply_discount(id, payload, current_user)


@fees_router.post("/invoices/{id}/cancel", summary="Cancel invoice with audit reason")
def cancel_invoice(
    id: int,
    payload: InvoiceCancelRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return FeeService.cancel_invoice(id, payload, current_user)


@fees_router.get("/invoices/student/{student_id}", summary="Get invoices for a specific student")
def get_student_invoices(
    student_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    filters = {"student_id": student_id, "limit": limit, "offset": offset}
    return FeeService.get_invoices(filters, current_user)


@fees_router.get("/invoices/{id}/receipt", summary="Get official invoice receipt slip")
def get_invoice_receipt(
    id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return FeeService.generate_invoice_receipt(id, current_user)
