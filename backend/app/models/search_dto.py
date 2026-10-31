"""Pydantic Data Transfer Objects for Q05 Fast Search.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SearchResultItem(BaseModel):
    category: str = Field(..., description="Entity category: students, hostels, rooms, allocations, complaints, maintenance, payments")
    entity_id: int = Field(..., description="Primary key ID of the entity")
    title: str = Field(..., description="Primary title or identifier")
    subtitle: str = Field(..., description="Secondary descriptive line")
    details: Optional[str] = Field("", description="Supplementary context or status details")
    tags: List[str] = Field(default_factory=list, description="Categorical or status tags")
    relevance_score: float = Field(1.0, description="Search relevance ranking score")


class SearchResponse(BaseModel):
    query: str
    category: str
    total_matches: int
    execution_time_ms: float
    results: List[SearchResultItem]
