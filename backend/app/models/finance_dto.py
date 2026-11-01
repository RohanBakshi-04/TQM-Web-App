from datetime import date, datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator


# ==================== 1. FEE STRUCTURE DTOs ====================

class FeeStructureCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    fee_category: str = Field(default="Hostel Accommodation Fee")
    hostel_id: Optional[int] = None
    room_type: str = Field(default="All")  # Single, Double, Triple, Dormitory, All
    academic_year: str = Field(..., min_length=4, max_length=20)
    semester: str = Field(default="All")
    amount: float = Field(..., gt=0)
    payment_frequency: str = Field(default="Semester")  # Monthly, Quarterly, Semester, Annual, One_Time
    is_mandatory: bool = True
    late_fine_amount: float = Field(default=0.0, ge=0)
    description: Optional[str] = ""

    @validator("amount")
    def validate_amount(cls, v):
        if round(v, 2) <= 0:
            raise ValueError("Fee amount must be greater than zero.")
        return round(v, 2)

    @validator("late_fine_amount")
    def validate_fine(cls, v):
        return round(v, 2) if v else 0.0


class FeeStructureUpdate(BaseModel):
    name: Optional[str] = None
    fee_category: Optional[str] = None
    hostel_id: Optional[int] = None
    room_type: Optional[str] = None
    academic_year: Optional[str] = None
    semester: Optional[str] = None
    amount: Optional[float] = None
    payment_frequency: Optional[str] = None
    is_mandatory: Optional[bool] = None
    late_fine_amount: Optional[float] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

    @validator("amount")
    def validate_amount(cls, v):
        if v is not None:
            if round(v, 2) <= 0:
                raise ValueError("Fee amount must be greater than zero.")
            return round(v, 2)
        return v


# ==================== 2. INVOICE DTOs ====================

class InvoiceItemCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=100)
    amount: float = Field(..., gt=0)

    @validator("amount")
    def validate_amount(cls, v):
        return round(v, 2)


class InvoiceCreate(BaseModel):
    student_id: Union[int, str]
    fee_structure_id: Optional[int] = None
    issue_date: str = Field(default_factory=lambda: date.today().isoformat())
    due_date: str
    items: Optional[List[InvoiceItemCreate]] = None
    total_amount: Optional[float] = None
    discount_amount: float = Field(default=0.0, ge=0)
    discount_reason: Optional[str] = ""
    remarks: Optional[str] = ""
    status: str = Field(default="Issued")  # Draft or Issued

    @validator("due_date")
    def validate_due_date(cls, v, values):
        issue_date = values.get("issue_date")
        if issue_date and v < issue_date:
            raise ValueError("Invoice due_date cannot be earlier than issue_date.")
        return v


class BulkInvoiceCreate(BaseModel):
    hostel_id: Optional[int] = None
    room_type: Optional[str] = None
    academic_year: str = Field(..., min_length=4)
    fee_structure_id: int
    issue_date: str = Field(default_factory=lambda: date.today().isoformat())
    due_date: str
    remarks: Optional[str] = ""

    @validator("due_date")
    def validate_due_date(cls, v, values):
        issue_date = values.get("issue_date")
        if issue_date and v < issue_date:
            raise ValueError("Due date cannot precede issue date.")
        return v


class InvoiceDiscountApply(BaseModel):
    discount_amount: float = Field(..., gt=0)
    discount_reason: str = Field(..., min_length=3, max_length=255)

    @validator("discount_amount")
    def validate_discount(cls, v):
        return round(v, 2)


class InvoiceCancelRequest(BaseModel):
    cancellation_reason: str = Field(..., min_length=3, max_length=255)


# ==================== 3. PAYMENT DTOs ====================

class PaymentRecordCreate(BaseModel):
    invoice_id: int
    amount: float = Field(..., gt=0)
    payment_method: str = Field(..., pattern=r"^(Cash|UPI|Bank Transfer|Bank_Transfer|Card|Credit_Card|Debit_Card|Cheque|Demand Draft|Demand_Draft|Other)$")
    payment_date: str = Field(default_factory=lambda: date.today().isoformat())
    transaction_id: Optional[str] = ""
    notes: Optional[str] = ""

    @validator("amount")
    def validate_amount(cls, v):
        if round(v, 2) <= 0:
            raise ValueError("Payment amount must be greater than zero.")
        return round(v, 2)


class PaymentReverseRequest(BaseModel):
    reversal_reason: str = Field(..., min_length=5, max_length=255)


# ==================== 4. REFUND DTOs ====================

class RefundRequestCreate(BaseModel):
    payment_id: int
    amount: float = Field(..., gt=0)
    reason: str = Field(..., min_length=5, max_length=255)
    refund_method: str = Field(default="Bank_Transfer")

    @validator("amount")
    def validate_amount(cls, v):
        if round(v, 2) <= 0:
            raise ValueError("Refund amount must be greater than zero.")
        return round(v, 2)


class RefundReviewAction(BaseModel):
    action: str = Field(..., pattern=r"^(Approve|Reject|Process)$")
    reason: Optional[str] = ""
    transaction_reference: Optional[str] = ""
