"""Announcement Data Transfer Objects (DTOs).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    content: str = Field(..., min_length=5, max_length=5000)
    category: str = Field("General Notice", pattern="^(General Notice|Hostel Notice|Academic Notice|Fee Notice|Mess Notice|Maintenance Notice|Emergency Notice|Event Notice|Other)$")
    priority: str = Field("Normal", pattern="^(Low|Normal|High|Critical|Emergency|low|normal|high|urgent)$")
    target_audience: str = Field("All Users", pattern="^(All Users|All Students|Hostel Residents|Roles|Selected Users|Guardians|all|students|staff|wardens)$")
    target_hostel_id: Optional[int] = None
    target_roles: Optional[List[str]] = Field(default_factory=list)
    publish_at: Optional[str] = None
    expires_at: Optional[str] = None
    attachment_url: Optional[str] = Field("", max_length=255)
    attachment_name: Optional[str] = Field("", max_length=150)
    status: str = Field("Published", pattern="^(Draft|Scheduled|Published)$")


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    content: Optional[str] = Field(None, min_length=5, max_length=5000)
    category: Optional[str] = Field(None, pattern="^(General Notice|Hostel Notice|Academic Notice|Fee Notice|Mess Notice|Maintenance Notice|Emergency Notice|Event Notice|Other)$")
    priority: Optional[str] = Field(None, pattern="^(Low|Normal|High|Critical|Emergency|low|normal|high|urgent)$")
    target_audience: Optional[str] = Field(None, pattern="^(All Users|All Students|Hostel Residents|Roles|Selected Users|Guardians|all|students|staff|wardens)$")
    target_hostel_id: Optional[int] = None
    target_roles: Optional[List[str]] = None
    publish_at: Optional[str] = None
    expires_at: Optional[str] = None
    attachment_url: Optional[str] = None
    attachment_name: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(Draft|Scheduled|Published|Archived)$")


class AnnouncementResponse(BaseModel):
    id: int
    title: str
    content: str
    category: str
    priority: str
    target_audience: str
    target_hostel_id: Optional[int] = None
    target_hostel_name: Optional[str] = None
    target_roles: List[str] = Field(default_factory=list)
    status: str
    publish_at: Optional[str] = None
    expires_at: Optional[str] = None
    attachment_url: Optional[str] = ""
    attachment_name: Optional[str] = ""
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    published_by: Optional[int] = None
    published_at: Optional[str] = None
    archived_at: Optional[str] = None
    is_active: bool = True
    view_count: int = 0
    acknowledged_count: int = 0
    is_viewed_by_me: bool = False
    is_acknowledged_by_me: bool = False
    created_at: str


class AnnouncementViewResponse(BaseModel):
    id: int
    user_id: int
    username: str
    first_name: str
    last_name: str
    role: str
    viewed_at: str
    acknowledged_at: Optional[str] = None
