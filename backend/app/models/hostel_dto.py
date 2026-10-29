"""Pydantic Data Transfer Objects for Hostels and Buildings.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time
"""

from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class HostelBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Hostel Name")
    code: str = Field(..., min_length=2, max_length=20, description="Unique Hostel Code")
    hostel_type: str = Field("Co-Ed", description="Hostel Type: Boys, Girls, Co-Ed")
    address: Optional[str] = Field("", max_length=255)
    warden_id: Optional[int] = None
    contact_phone: Optional[str] = Field("", max_length=30)
    contact_email: Optional[str] = Field("", max_length=100)
    is_active: int = Field(1, ge=0, le=1)


class HostelCreate(HostelBase):
    pass


class HostelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    code: Optional[str] = Field(None, min_length=2, max_length=20)
    hostel_type: Optional[str] = None
    address: Optional[str] = None
    warden_id: Optional[int] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: Optional[int] = Field(None, ge=0, le=1)


class HostelStatusUpdate(BaseModel):
    is_active: int = Field(..., ge=0, le=1)


class BuildingBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    total_floors: int = Field(..., ge=1, le=50)
    is_active: int = Field(1, ge=0, le=1)


class BuildingCreate(BuildingBase):
    hostel_id: Optional[int] = None


class BuildingUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    total_floors: Optional[int] = Field(None, ge=1, le=50)
    is_active: Optional[int] = Field(None, ge=0, le=1)


class BuildingStatusUpdate(BaseModel):
    is_active: int = Field(..., ge=0, le=1)
