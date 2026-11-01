"""Notification REST API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, status

from backend.app.models.notification_dto import (
    NotificationResponse,
    NotificationListResponse,
    NotificationPreferenceDTO,
    NotificationPreferenceResponse
)
from backend.app.services.auth_dependencies import get_current_user
from backend.app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    category: Optional[str] = Query(None, description="Filter by notification category"),
    priority: Optional[str] = Query(None, description="Filter by notification priority"),
    is_read: Optional[bool] = Query(None, description="Filter read or unread notifications"),
    search: Optional[str] = Query(None, description="Search in title or message text"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> NotificationListResponse:
    """Retrieve paginated notifications for the authenticated user with Q05 < 10ms SLA."""
    user_id = current_user.get("user_id") or current_user.get("id")
    return NotificationService.get_user_notifications(
        user_id=user_id,
        category=category,
        priority=priority,
        is_read=is_read,
        search=search,
        page=page,
        page_size=page_size
    )


@router.get("/unread-count")
def get_unread_notification_count(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Retrieve ultra-fast unread notification badge count."""
    user_id = current_user.get("user_id") or current_user.get("id")
    count = NotificationService.get_unread_count(user_id=user_id)
    return {"unread_count": count}


@router.post("/{notification_id}/read")
def mark_notification_as_read(
    notification_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Mark a specific notification as read, enforcing user isolation."""
    user_id = current_user.get("user_id") or current_user.get("id")
    NotificationService.mark_as_read(notification_id=notification_id, user_id=user_id)
    return {"status": "success", "message": f"Notification #{notification_id} marked as read."}


@router.post("/read-all")
def mark_all_notifications_as_read(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Mark all unread notifications as read for current user."""
    user_id = current_user.get("user_id") or current_user.get("id")
    count = NotificationService.mark_all_read(user_id=user_id)
    return {"status": "success", "message": f"Marked {count} notifications as read.", "affected_count": count}


@router.get("/preferences", response_model=NotificationPreferenceResponse)
def get_notification_preferences(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> NotificationPreferenceResponse:
    """Fetch current user's notification delivery preferences."""
    user_id = current_user.get("user_id") or current_user.get("id")
    return NotificationService.get_preferences(user_id=user_id)


@router.put("/preferences", response_model=NotificationPreferenceResponse)
def update_notification_preferences(
    payload: NotificationPreferenceDTO,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> NotificationPreferenceResponse:
    """Update current user's notification preferences."""
    user_id = current_user.get("user_id") or current_user.get("id")
    return NotificationService.update_preferences(user_id=user_id, payload=payload)
