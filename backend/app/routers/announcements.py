"""Announcement REST API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from backend.app.models.announcement_dto import (
    AnnouncementCreate,
    AnnouncementUpdate,
    AnnouncementResponse,
    AnnouncementViewResponse
)
from backend.app.services.auth_dependencies import get_current_user
from backend.app.services.announcement_service import AnnouncementService

router = APIRouter(prefix="/api/v1/announcements", tags=["Announcements"])


@router.get("", response_model=List[AnnouncementResponse])
def list_announcements(
    category: Optional[str] = Query(None, description="Filter by category"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    status: Optional[str] = Query(None, description="Filter by status (Draft, Scheduled, Published, Archived)"),
    hostel_id: Optional[int] = Query(None, description="Filter by hostel target"),
    search: Optional[str] = Query(None, description="Search announcement title or content"),
    limit: int = Query(50, ge=1, le=200, description="Max items to retrieve"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[AnnouncementResponse]:
    """List targeted announcements for the user with sub-10ms Q05 SLA."""
    return AnnouncementService.get_announcements(
        current_user=current_user,
        category=category,
        priority=priority,
        status_filter=status,
        hostel_id=hostel_id,
        search=search,
        limit=limit
    )


@router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
def create_announcement(
    payload: AnnouncementCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AnnouncementResponse:
    """Create a new institution or hostel announcement."""
    return AnnouncementService.create_announcement(payload=payload, current_user=current_user)


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
def get_announcement_detail(
    announcement_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AnnouncementResponse:
    """Fetch announcement details and log reader view."""
    return AnnouncementService.get_announcement_by_id(announcement_id=announcement_id, current_user=current_user)


@router.put("/{announcement_id}", response_model=AnnouncementResponse)
def update_announcement(
    announcement_id: int,
    payload: AnnouncementUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AnnouncementResponse:
    """Update announcement fields."""
    return AnnouncementService.update_announcement(
        announcement_id=announcement_id,
        payload=payload,
        current_user=current_user
    )


@router.post("/{announcement_id}/publish", response_model=AnnouncementResponse)
def publish_announcement(
    announcement_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AnnouncementResponse:
    """Publish a draft or scheduled announcement immediately."""
    return AnnouncementService.publish_announcement(announcement_id=announcement_id, current_user=current_user)


@router.post("/{announcement_id}/archive", response_model=AnnouncementResponse)
def archive_announcement(
    announcement_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AnnouncementResponse:
    """Archive an announcement to remove it from active views."""
    return AnnouncementService.archive_announcement(announcement_id=announcement_id, current_user=current_user)


@router.post("/{announcement_id}/acknowledge")
def acknowledge_announcement(
    announcement_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Record student/resident formal acknowledgement for a mandatory notice."""
    AnnouncementService.acknowledge_announcement(announcement_id=announcement_id, current_user=current_user)
    return {"status": "success", "message": f"Announcement #{announcement_id} acknowledged."}


@router.get("/{announcement_id}/views", response_model=List[AnnouncementViewResponse])
def get_announcement_views(
    announcement_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[AnnouncementViewResponse]:
    """Inspect reader view and acknowledgement logs (Administrators only)."""
    return AnnouncementService.get_announcement_views(announcement_id=announcement_id, current_user=current_user)
