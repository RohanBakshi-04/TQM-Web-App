"""Maintenance Task and Work-Order Data Transfer Objects (DTOs).

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

from typing import List, Optional
from pydantic import BaseModel, Field

VALID_MAINTENANCE_STATUSES = [
    "Open",
    "Assigned",
    "Accepted",
    "In Progress",
    "On Hold",
    "Completed",
    "Verified",
    "Cancelled",
]

VALID_PRIORITIES = ["Low", "Medium", "High", "Critical"]


class MaintenanceTaskCreate(BaseModel):
    """Schema for creating a maintenance task work-order."""
    complaint_id: Optional[int] = Field(None, description="Optional linked student complaint ID")
    room_id: Optional[int] = Field(None, description="Optional target room ID")
    title: str = Field(..., min_length=3, max_length=200, description="Task summary")
    description: str = Field(..., min_length=5, description="Work order scope and repair details")
    priority: str = Field("Medium", description="Priority level: Low, Medium, High, Critical")
    assigned_to: Optional[int] = Field(None, description="User ID of assigned maintenance staff")
    deadline: Optional[str] = Field(None, description="Target completion deadline (YYYY-MM-DD)")
    estimated_cost: float = Field(0.0, ge=0.0, description="Estimated repair cost in INR")
    scheduled_date: Optional[str] = Field(None, description="Scheduled service date (YYYY-MM-DD)")
    affects_occupancy: bool = Field(False, description="Whether repairs require marking room/bed under Maintenance")


class MaintenanceTaskAssign(BaseModel):
    """Schema for assigning or reassigning a maintenance task to a technician."""
    assigned_to: int = Field(..., description="User ID of maintenance worker")
    priority: Optional[str] = Field(None, description="Updated priority if changed")
    deadline: Optional[str] = Field(None, description="Target completion deadline")
    estimated_cost: Optional[float] = Field(0.0, ge=0.0, description="Estimated budget")
    scheduled_date: Optional[str] = Field(None, description="Scheduled date for work")
    remarks: Optional[str] = Field(None, description="Warden internal assignment instructions")
    affects_occupancy: bool = Field(False, description="Set room/bed status to Maintenance")


class MaintenanceTaskProgress(BaseModel):
    """Schema for general progress notes and intermediate updates."""
    notes: str = Field(..., min_length=2, description="Progress notes or part replacement update")


class MaintenanceTaskHold(BaseModel):
    """Schema for putting a work-order on hold (e.g., waiting for spare parts)."""
    hold_reason: str = Field(..., min_length=3, description="Reason for pausing work")
    notes: Optional[str] = Field("", description="Additional details")


class MaintenanceTaskComplete(BaseModel):
    """Schema for maintenance worker submitting task completion."""
    resolution_notes: str = Field(..., min_length=5, description="Summary of work completed and parts used")
    actual_cost: float = Field(0.0, ge=0.0, description="Actual materials and labor cost incurred")
    completion_photo_url: Optional[str] = Field(None, description="Photo proof URL of completed repair")


class MaintenanceTaskVerify(BaseModel):
    """Schema for Warden or Admin verification and closure of work-order."""
    approved: bool = Field(True, description="Whether work meets quality standards")
    verification_notes: Optional[str] = Field("", description="Inspection feedback and sign-off comments")
