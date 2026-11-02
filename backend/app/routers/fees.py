from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status, Response

from backend.app.services.auth_dependencies import get_current_user, verify_student_isolation
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
    verify_student_isolation(student_id, current_user)
    filters = {"student_id": student_id, "limit": limit, "offset": offset}
    return FeeService.get_invoices(filters, current_user)


@fees_router.get("/invoices/{id}/receipt", summary="Get official invoice receipt slip")
def get_invoice_receipt(
    id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return FeeService.generate_invoice_receipt(id, current_user)


# ==========================================
# 3. PAYMENT ENDPOINTS
# ==========================================

@fees_router.get("/payments", summary="List payment transactions with filters")
def list_payments(
    student_id: Optional[int] = Query(None),
    invoice_id: Optional[int] = Query(None),
    payment_method: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    payment_reference: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    filters = {
        "student_id": student_id,
        "invoice_id": invoice_id,
        "payment_method": payment_method,
        "status": status,
        "payment_reference": payment_reference,
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
        "offset": offset
    }
    return PaymentService.get_payments(filters, current_user)


@fees_router.post("/payments", status_code=status.HTTP_201_CREATED, summary="Record student payment against invoice")
def record_payment(
    payload: PaymentRecordCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return PaymentService.record_payment(payload, current_user)


@fees_router.get("/payments/{id}", summary="Get payment transaction details")
def get_payment(
    id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return PaymentService.get_payment(id, current_user)


@fees_router.get("/payments/student/{student_id}", summary="Get payments by student ID")
def get_student_payments(
    student_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    verify_student_isolation(student_id, current_user)
    filters = {"student_id": student_id, "limit": limit, "offset": offset}
    return PaymentService.get_payments(filters, current_user)


@fees_router.post("/payments/{id}/verify", summary="Verify and confirm payment record")
def verify_payment(
    id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    # Fetch details confirming verification
    return PaymentService.get_payment(id, current_user)


@fees_router.post("/payments/{id}/reverse", summary="Audited payment reversal")
def reverse_payment(
    id: int,
    payload: PaymentReverseRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return PaymentService.reverse_payment(id, payload, current_user)


@fees_router.get("/payments/{id}/receipt", summary="Get official payment confirmation receipt")
def get_payment_receipt(
    id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return PaymentService.generate_payment_receipt(id, current_user)


# ==========================================
# 4. REFUND ENDPOINTS
# ==========================================

@fees_router.get("/refunds", summary="List refund requests")
def list_refunds(
    status: Optional[str] = Query(None),
    payment_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    filters = {"status": status, "payment_id": payment_id, "limit": limit, "offset": offset}
    return PaymentService.get_refunds(filters, current_user)


@fees_router.post("/refunds", status_code=status.HTTP_201_CREATED, summary="Create a refund request")
def request_refund(
    payload: RefundRequestCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return PaymentService.request_refund(payload, current_user)


@fees_router.get("/refunds/{id}", summary="Get refund details by ID")
def get_refund(
    id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return PaymentService.get_refund(id, current_user)


@fees_router.post("/refunds/{id}/approve", summary="Approve refund request")
def approve_refund(
    id: int,
    payload: Optional[RefundReviewAction] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    review = payload or RefundReviewAction(action="Approve")
    review.action = "Approve"
    return PaymentService.review_refund(id, review, current_user)


@fees_router.post("/refunds/{id}/reject", summary="Reject refund request with reason")
def reject_refund(
    id: int,
    payload: RefundReviewAction,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    payload.action = "Reject"
    return PaymentService.review_refund(id, payload, current_user)


@fees_router.post("/refunds/{id}/process", summary="Process approved refund and adjust ledger")
def process_refund(
    id: int,
    payload: Optional[RefundReviewAction] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    review = payload or RefundReviewAction(action="Process")
    review.action = "Process"
    return PaymentService.review_refund(id, review, current_user)


# ==========================================
# 5. FINANCIAL DASHBOARD & REPORTS ENDPOINTS
# ==========================================

@fees_router.get("/dashboard", summary="Financial dashboard analytics and metrics")
def get_financial_dashboard(
    hostel_id: Optional[int] = Query(None, description="Optional hostel ID filter"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return FinancialReportService.get_financial_dashboard(hostel_id, current_user)


@fees_router.get("/reports/collections", summary="Collections report with filters")
def get_collections_report(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    payment_method: Optional[str] = Query(None, description="Payment method"),
    hostel_id: Optional[int] = Query(None, description="Hostel filter"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "payment_method": payment_method,
        "hostel_id": hostel_id
    }
    return FinancialReportService.get_collections_report(filters, current_user)


@fees_router.get("/reports/dues", summary="Outstanding dues report")
def get_dues_report(
    status: Optional[str] = Query(None, description="Invoice status filter"),
    hostel_id: Optional[int] = Query(None, description="Hostel filter"),
    min_amount: Optional[float] = Query(None, description="Minimum due amount"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    filters = {
        "status": status,
        "hostel_id": hostel_id,
        "min_amount": min_amount
    }
    return FinancialReportService.get_dues_report(filters, current_user)


@fees_router.get("/reports/overdue", summary="Overdue invoices report with aging buckets")
def get_overdue_report(
    hostel_id: Optional[int] = Query(None, description="Hostel filter"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    filters = {"hostel_id": hostel_id}
    return FinancialReportService.get_overdue_report(filters, current_user)


@fees_router.get("/reports/refunds", summary="Refunds audit report")
def get_refunds_report(
    status: Optional[str] = Query(None, description="Refund status"),
    start_date: Optional[str] = Query(None, description="Start date"),
    end_date: Optional[str] = Query(None, description="End date"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    filters = {
        "status": status,
        "start_date": start_date,
        "end_date": end_date
    }
    return FinancialReportService.get_refunds_report(filters, current_user)


@fees_router.get("/reports/export", summary="Export financial report to CSV")
def export_financial_report_csv(
    report_type: str = Query(..., description="Report type: collections, dues, overdue, refunds"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    payment_method: Optional[str] = Query(None),
    hostel_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "payment_method": payment_method,
        "hostel_id": hostel_id,
        "status": status
    }
    csv_data = FinancialReportService.export_csv(report_type, filters, current_user)
    filename = f"finance_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
