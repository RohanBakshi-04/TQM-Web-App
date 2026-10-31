from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class MessMenuCreate(BaseModel):
    hostel_id: Optional[int] = Field(None, description="Hostel ID, or null for institutional master menu")
    menu_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Specific calendar date (YYYY-MM-DD)")
    day_of_week: str = Field(..., pattern=r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$")
    meal_type: str = Field(..., pattern=r"^(Breakfast|Lunch|Evening Snacks|Snacks|Dinner)$")
    title: Optional[str] = Field("", max_length=120)
    items_description: str = Field(..., min_length=3, max_length=1000)
    items: Optional[List[str]] = Field(default_factory=list)
    start_time: Optional[str] = Field("", max_length=10)
    end_time: Optional[str] = Field("", max_length=10)
    is_special: bool = False
    status: str = Field("Published", pattern=r"^(Draft|Published|Cancelled)$")


class MessMenuUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=120)
    items_description: Optional[str] = Field(None, min_length=3, max_length=1000)
    items: Optional[List[str]] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_special: Optional[bool] = None
    status: Optional[str] = Field(None, pattern=r"^(Draft|Published|Cancelled)$")
    cancelled_reason: Optional[str] = Field("", max_length=500)


class MessSubscriptionCreate(BaseModel):
    student_id: int = Field(..., gt=0)
    hostel_id: Optional[int] = Field(None, gt=0)
    plan_type: str = Field(..., pattern=r"^(Monthly|Semester|Custom|Annual)$")
    diet_type: str = Field("Regular", pattern=r"^(Regular|Vegetarian|Non-Vegetarian|Jain|Special)$")
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    monthly_fee: float = Field(..., ge=0.0)
    is_exempted: bool = False
    exemption_reason: Optional[str] = Field("", max_length=500)
    remarks: Optional[str] = Field("", max_length=500)

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: str, info) -> str:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("Subscription end_date cannot be earlier than start_date")
        return v


class MessSubscriptionUpdate(BaseModel):
    diet_type: Optional[str] = Field(None, pattern=r"^(Regular|Vegetarian|Non-Vegetarian|Jain|Special)$")
    end_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    status: Optional[str] = Field(None, pattern=r"^(Pending|Active|Suspended|Expired|Cancelled)$")
    remarks: Optional[str] = Field("", max_length=500)
    exemption_reason: Optional[str] = Field("", max_length=500)


class MealAttendanceCreate(BaseModel):
    student_id: int = Field(..., gt=0)
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    meal_type: str = Field(..., pattern=r"^(Breakfast|Lunch|Evening Snacks|Snacks|Dinner)$")
    verification_method: str = Field("Manual", pattern=r"^(Manual|QR_Scan|Biometric|RFID)$")
    hostel_id: Optional[int] = None


class MealAttendanceCorrection(BaseModel):
    status: str = Field(..., pattern=r"^(Present|Absent|Corrected|Cancelled)$")
    correction_reason: str = Field(..., min_length=5, max_length=500)


class MealAttendanceQRVerify(BaseModel):
    qr_data: str = Field(..., min_length=1, description="Student enrollment number or ID")
    meal_type: str = Field(..., pattern=r"^(Breakfast|Lunch|Evening Snacks|Snacks|Dinner)$")
    hostel_id: Optional[int] = None
