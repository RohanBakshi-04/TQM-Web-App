"""Notification Data Transfer Objects (DTOs).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    user_id: int
    title: str = Field(..., min_length=2, max_length=150)
    message: str = Field(..., min_length=2, max_length=1000)
    category: str = Field("general", max_length=50)
    priority: str = Field("Normal", pattern="^(Low|Normal|High|Critical)$")
    notification_type: str = Field("info", pattern="^(info|warning|alert|success)$")
    related_entity_type: Optional[str] = Field("", max_length=50)
    related_entity_id: Optional[str] = Field("", max_length=50)
    event_key: Optional[str] = Field("", max_length=150)
    delivery_channel: str = Field("in_app", pattern="^(in_app|email|browser)$")


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    category: str
    priority: str
    notification_type: str
    is_read: bool
    read_at: Optional[str] = None
    related_entity_type: Optional[str] = ""
    related_entity_id: Optional[str] = ""
    event_key: Optional[str] = ""
    delivery_channel: str = "in_app"
    created_at: str


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int
    unread_count: int


class NotificationPreferenceDTO(BaseModel):
    in_app_enabled: bool = True
    email_enabled: bool = False
    browser_enabled: bool = False
    disabled_categories: List[str] = Field(default_factory=list)


class NotificationPreferenceResponse(NotificationPreferenceDTO):
    user_id: int
    updated_at: Optional[str] = None
