"""Q05 Fast Search REST API Router.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from backend.app.database.connection import get_db_connection
from backend.app.models.search_dto import SearchResponse
from backend.app.services.auth_dependencies import get_current_user, require_roles
from backend.app.services.search_service import SearchService

router = APIRouter(prefix="/api/v1/search", tags=["Q05 Fast Search"])


@router.get("", response_model=SearchResponse)
def execute_fast_search(
    q: str = Query(..., min_length=1, max_length=100, description="Search keyword or token"),
    category: Optional[str] = Query("all", description="Entity filter: students, hostels, rooms, allocations, complaints, maintenance, payments, all"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> SearchResponse:
    """Execute sub-10ms parameterized full-text and indexed B-tree search across all operational entities."""
    conn = get_db_connection()
    try:
        return SearchService.search(
            conn=conn,
            q=q,
            category=category,
            user_roles=current_user.get("roles", []),
            linked_hostel_id=current_user.get("linked_hostel_id"),
            linked_student_id=current_user.get("linked_student_id"),
            limit=limit,
            offset=offset
        )
    finally:
        conn.close()


@router.post("/rebuild-index", status_code=status.HTTP_200_OK)
def rebuild_search_index(
    current_user: Dict[str, Any] = Depends(require_roles("super_admin", "hostel_admin", "auditor"))
) -> Dict[str, Any]:
    """Rebuild and synchronize the unified SQLite FTS5 full-text search index."""
    conn = get_db_connection()
    try:
        count = SearchService.rebuild_fts5_index(conn)
        return {
            "status": "success",
            "indexed_entities": count,
            "message": f"Successfully indexed {count} entities into SQLite FTS5 virtual table."
        }
    finally:
        conn.close()
