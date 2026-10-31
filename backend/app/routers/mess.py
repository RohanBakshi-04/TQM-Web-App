from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from backend.app.services.auth_dependencies import get_current_user
from backend.app.models.mess_dto import (
    MessMenuCreate,
    MessMenuUpdate,
    MessSubscriptionCreate,
    MessSubscriptionUpdate,
    MealAttendanceCreate,
    MealAttendanceCorrection,
    MealAttendanceQRVerify,
)
from backend.app.services.mess_service import MessService

mess_router = APIRouter(prefix="/api/v1/mess", tags=["Mess Management"])


# ==========================================
# 1. MESS MENU ENDPOINTS
# ==========================================

@mess_router.get("/menus", summary="List mess menus with date, day, meal, and hostel filters")
def list_menus(
    menu_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD"),
    day_of_week: Optional[str] = Query(None, description="Day of week"),
    meal_type: Optional[str] = Query(None, description="Meal type"),
    hostel_id: Optional[int] = Query(None, description="Hostel filter"),
    status: Optional[str] = Query(None, description="Status filter"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    filters = {
        "menu_date": menu_date,
        "day_of_week": day_of_week,
        "meal_type": meal_type,
        "hostel_id": hostel_id,
        "status": status
    }
    return MessService.get_menus(filters, current_user)


@mess_router.post("/menus", status_code=status.HTTP_201_CREATED, summary="Create a new daily/weekly mess menu")
def create_menu(
    payload: MessMenuCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return MessService.create_menu(payload, current_user)


@mess_router.get("/menus/{id}", summary="Get mess menu details by ID")
def get_menu(
    id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return MessService.get_menu(id, current_user)


@mess_router.put("/menus/{id}", summary="Update a mess menu")
def update_menu(
    id: int,
    payload: MessMenuUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return MessService.update_menu(id, payload, current_user)


@mess_router.delete("/menus/{id}", summary="Cancel or remove a mess menu")
def delete_menu(
    id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return MessService.delete_menu(id, current_user)


# ==========================================
# 2. MESS SUBSCRIPTION ENDPOINTS
# ==========================================

@mess_router.get("/subscriptions", summary="List mess subscriptions with filters")
def list_subscriptions(
    student_id: Optional[int] = Query(None, description="Filter by student ID"),
    hostel_id: Optional[int] = Query(None, description="Filter by hostel ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    plan_type: Optional[str] = Query(None, description="Filter by plan type"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    filters = {
        "student_id": student_id,
        "hostel_id": hostel_id,
        "status": status,
        "plan_type": plan_type
    }
    return MessService.get_subscriptions(filters, current_user)


@mess_router.post("/subscriptions", status_code=status.HTTP_201_CREATED, summary="Enroll student in mess subscription")
def create_subscription(
    payload: MessSubscriptionCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return MessService.create_subscription(payload, current_user)


@mess_router.get("/subscriptions/{id}", summary="Get mess subscription by ID")
def get_subscription(
    id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return MessService.get_subscription(id, current_user)


@mess_router.post("/subscriptions/{id}/suspend", summary="Suspend student mess subscription")
def suspend_subscription(
    id: int,
    reason: str = Query("Suspended on student request", description="Reason for suspension"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return MessService.update_subscription_status(id, "Suspended", reason, current_user)


@mess_router.post("/subscriptions/{id}/renew", summary="Renew student mess subscription")
def renew_subscription(
    id: int,
    reason: str = Query("Renewed subscription", description="Renewal notes"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return MessService.update_subscription_status(id, "Active", reason, current_user)


@mess_router.post("/subscriptions/{id}/cancel", summary="Cancel student mess subscription")
def cancel_subscription(
    id: int,
    reason: str = Query("Subscription cancelled", description="Cancellation reason"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return MessService.update_subscription_status(id, "Cancelled", reason, current_user)


# ==========================================
# 3. MEAL ATTENDANCE ENDPOINTS
# ==========================================

@mess_router.get("/attendance", summary="List meal attendance records")
def list_attendance(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD"),
    student_id: Optional[int] = Query(None, description="Filter by student ID"),
    meal_type: Optional[str] = Query(None, description="Filter by meal type"),
    hostel_id: Optional[int] = Query(None, description="Filter by hostel ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    filters = {
        "date": date,
        "student_id": student_id,
        "meal_type": meal_type,
        "hostel_id": hostel_id
    }
    return MessService.get_attendance(filters, current_user)


@mess_router.post("/attendance", status_code=status.HTTP_201_CREATED, summary="Record student meal attendance")
def record_attendance(
    payload: MealAttendanceCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return MessService.record_meal_attendance(payload, current_user)


@mess_router.post("/attendance/qr-verify", summary="Verify QR code and mark meal attendance")
def verify_qr_attendance(
    payload: MealAttendanceQRVerify,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return MessService.verify_qr_attendance(payload, current_user)


@mess_router.put("/attendance/{id}", summary="Correct a meal attendance entry with audit reason")
def correct_attendance(
    id: int,
    payload: MealAttendanceCorrection,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return MessService.correct_attendance(id, payload, current_user)


# ==========================================
# 4. MESS DASHBOARD
# ==========================================

@mess_router.get("/dashboard", summary="Mess real-time dashboard analytics")
def get_mess_dashboard(
    hostel_id: Optional[int] = Query(None, description="Optional hostel ID filter"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    return MessService.get_mess_dashboard(hostel_id, current_user)


# ==========================================
# 5. MESS REPORTS & CSV EXPORT
# ==========================================

@mess_router.get("/reports/consumption", summary="Meal consumption report")
def get_meal_consumption_report(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    hostel_id: Optional[int] = Query(None, description="Hostel filter"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    from backend.app.services.mess_inventory_report_service import MessInventoryReportService
    return MessInventoryReportService.get_meal_consumption_report(start_date, end_date, hostel_id)


@mess_router.get("/reports/consumption/export", summary="Export meal consumption report as RFC 4180 CSV")
def export_meal_consumption_csv(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    hostel_id: Optional[int] = Query(None, description="Hostel filter"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    from fastapi.responses import StreamingResponse
    from backend.app.services.mess_inventory_report_service import MessInventoryReportService

    generator = MessInventoryReportService.stream_meal_consumption_csv(start_date, end_date, hostel_id)
    return StreamingResponse(
        generator,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=meal_consumption_report.csv"}
    )
