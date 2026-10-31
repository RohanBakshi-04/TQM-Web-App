"""Pydantic DTOs for Student Complaint and Lifecycle Management.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

VALID_CATEGORIES = (
    "Electrical",
    "Plumbing",
    "Carpentry",
    "Wi-Fi and Internet",
    "Cleanliness",
    "Water Supply",
    "Furniture",
    "Security",
    "Mess",
    "Other"
)

VALID_SEVERITIES = ("Low", "Medium", "High", "Critical")

VALID_STATUSES = (
    "Submitted",
    "Pending",
    "Assigned",
    "In Progress",
    "On Hold",
    "Resolved",
    "Closed",
    "Rejected",
    "Reopened"
)


class ComplaintCreate(BaseModel):
    category: str = Field(..., description="Complaint category: Electrical, Plumbing, Carpentry, Wi-Fi and Internet, Cleanliness, Water Supply, Furniture, Security, Mess, Other")
    title: str = Field(..., min_length=3, max_length=150, description="Brief summary of the issue")
    description: str = Field(..., min_length=5, max_length=1500, description="Detailed description of the issue")
    severity: str = Field("Medium", description="Low, Medium, High, Critical")
    room_id: Optional[int] = Field(None, description="Affected room ID if applicable")
    bed_id: Optional[int] = Field(None, description="Affected bed ID if applicable")
    attachment_url: Optional[str] = Field(None, description="Optional image/document attachment URL or base64")


class ComplaintCommentAdd(BaseModel):
    comment: str = Field(..., min_length=2, max_length=1000, description="Additional comment or progress update")


class ComplaintFeedback(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Satisfaction score between 1 and 5 stars")
    comment: Optional[str] = Field("", max_length=1000, description="Optional feedback narrative")


class ComplaintReopen(BaseModel):
    reason: str = Field(..., min_length=5, max_length=1000, description="Justification for reopening resolved complaint")


class ComplaintAssign(BaseModel):
    assigned_to: int = Field(..., description="User ID of the maintenance technician")
    priority: Optional[str] = Field(None, description="Optional overridden priority: Low, Medium, High, Critical")
    deadline: Optional[str] = Field(None, description="Target resolution deadline (YYYY-MM-DD)")
    internal_remarks: Optional[str] = Field("", description="Private internal notes for maintenance staff")
    affects_occupancy: bool = Field(False, description="Flag if maintenance prevents room/bed occupancy")


class ComplaintReject(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000, description="Reason for complaint rejection")


class ComplaintEscalate(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000, description="Reason for urgent escalation to administration")


class ComplaintClose(BaseModel):
    notes: Optional[str] = Field("", max_length=1000, description="Closure and inspection notes")
