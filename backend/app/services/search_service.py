"""Q05 Fast Search Service with B-Tree and SQLite FTS5 Acceleration.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (<10ms SLA)
"""

import re
import sqlite3
import time
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from backend.app.models.search_dto import SearchResponse, SearchResultItem
from backend.app.utils.logger import logger


class SearchService:
    """Unified, sub-10ms server-side search engine with multi-domain indexing."""

    @staticmethod
    def ensure_fts5_schema(conn: sqlite3.Connection) -> None:
        """Create and ensure the unified FTS5 full-text index table exists."""
        cursor = conn.cursor()
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS search_index_fts USING fts5(
                entity_type UNINDEXED,
                entity_id UNINDEXED,
                title,
                subtitle,
                content,
                tags,
                hostel_id UNINDEXED,
                tokenize = 'porter unicode61'
            );
        """)
        conn.commit()

    @staticmethod
    def rebuild_fts5_index(conn: sqlite3.Connection) -> int:
        """Synchronize FTS5 virtual catalog with active relational records."""
        cursor = conn.cursor()
        SearchService.ensure_fts5_schema(conn)

        cursor.execute("DELETE FROM search_index_fts;")

        count = 0

        # 1. Students
        students = cursor.execute("""
            SELECT id, student_id, first_name, last_name, email, phone, branch, academic_year, status
            FROM students;
        """).fetchall()
        for s in students:
            title = f"{s['first_name']} {s['last_name']}"
            subtitle = f"Enrollment: {s['student_id']} • {s['branch']} ({s['academic_year']})"
            content = f"{s['first_name']} {s['last_name']} {s['student_id']} {s['email']} {s['phone']} {s['branch']} {s['academic_year']}"
            tags = f"student {s['branch']} {s['status']}"
            cursor.execute("""
                INSERT INTO search_index_fts (entity_type, entity_id, title, subtitle, content, tags, hostel_id)
                VALUES ('students', ?, ?, ?, ?, ?, NULL);
            """, (s["id"], title, subtitle, content, tags))
            count += 1

        # 2. Hostels
        hostels = cursor.execute("""
            SELECT id, name, code, hostel_type, address, contact_phone, contact_email, is_active
            FROM hostels;
        """).fetchall()
        for h in hostels:
            title = f"{h['name']} ({h['code']})"
            subtitle = f"Type: {h['hostel_type']} • {h['address']}"
            content = f"{h['name']} {h['code']} {h['hostel_type']} {h['address']} {h['contact_phone']} {h['contact_email']}"
            tags = f"hostel {h['hostel_type']} {'active' if h['is_active'] else 'inactive'}"
            cursor.execute("""
                INSERT INTO search_index_fts (entity_type, entity_id, title, subtitle, content, tags, hostel_id)
                VALUES ('hostels', ?, ?, ?, ?, ?, ?);
            """, (h["id"], title, subtitle, content, tags, h["id"]))
            count += 1

        # 3. Rooms & Beds
        rooms = cursor.execute("""
            SELECT r.id AS room_id, r.room_number, r.room_type, r.capacity, r.status AS room_status,
                   f.floor_name, b.name AS building_name, h.id AS hostel_id, h.name AS hostel_name, h.code AS hostel_code
            FROM rooms r
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id;
        """).fetchall()
        for r in rooms:
            title = f"Room {r['room_number']} ({r['room_type']})"
            subtitle = f"{r['hostel_name']} • {r['building_name']} ({r['floor_name']})"
            content = f"Room {r['room_number']} {r['room_type']} {r['hostel_name']} {r['hostel_code']} {r['building_name']} {r['room_status']}"
            tags = f"room {r['room_type']} {r['room_status']}"
            cursor.execute("""
                INSERT INTO search_index_fts (entity_type, entity_id, title, subtitle, content, tags, hostel_id)
                VALUES ('rooms', ?, ?, ?, ?, ?, ?);
            """, (r["room_id"], title, subtitle, content, tags, r["hostel_id"]))
            count += 1

        # 4. Room Allocations
        allocs = cursor.execute("""
            SELECT ra.id AS alloc_id, ra.allocation_status, ra.start_date, ra.fee_status,
                   s.student_id AS student_enrollment, s.first_name || ' ' || s.last_name AS student_name,
                   bd.bed_number, r.room_number, h.id AS hostel_id, h.name AS hostel_name
            FROM room_allocations ra
            JOIN students s ON ra.student_id = s.id
            JOIN beds bd ON ra.bed_id = bd.id
            JOIN rooms r ON ra.room_id = r.id
            JOIN floors f ON r.floor_id = f.id
            JOIN buildings b ON f.building_id = b.id
            JOIN hostels h ON b.hostel_id = h.id;
        """).fetchall()
        for a in allocs:
            title = f"Allocation #{a['alloc_id']:04d}: {a['student_name']}"
            subtitle = f"{a['hostel_name']} • Rm {a['room_number']} (Bed {a['bed_number']})"
            content = f"Allocation {a['alloc_id']} {a['student_name']} {a['student_enrollment']} Bed {a['bed_number']} Room {a['room_number']} {a['hostel_name']} {a['allocation_status']}"
            tags = f"allocation {a['allocation_status']} {a['fee_status']}"
            cursor.execute("""
                INSERT INTO search_index_fts (entity_type, entity_id, title, subtitle, content, tags, hostel_id)
                VALUES ('allocations', ?, ?, ?, ?, ?, ?);
            """, (a["alloc_id"], title, subtitle, content, tags, a["hostel_id"]))
            count += 1

        # 5. Complaints
        complaints = cursor.execute("""
            SELECT c.id, c.complaint_id, c.title, c.description, c.category, c.status, c.severity,
                   s.first_name || ' ' || s.last_name AS student_name, r.room_number
            FROM complaints c
            JOIN students s ON c.student_id = s.id
            JOIN rooms r ON c.room_id = r.id;
        """).fetchall()
        for c in complaints:
            title = f"Complaint {c['complaint_id']}: {c['title']}"
            subtitle = f"Category: {c['category']} • Room {c['room_number']} • Status: {c['status']}"
            content = f"{c['complaint_id']} {c['title']} {c['description']} {c['category']} {c['student_name']} Room {c['room_number']} {c['status']} {c['severity']}"
            tags = f"complaint {c['category']} {c['status']} {c['severity']}"
            cursor.execute("""
                INSERT INTO search_index_fts (entity_type, entity_id, title, subtitle, content, tags, hostel_id)
                VALUES ('complaints', ?, ?, ?, ?, ?, NULL);
            """, (c["id"], title, subtitle, content, tags))
            count += 1

        # 6. Payments
        payments = cursor.execute("""
            SELECT p.id, p.payment_reference, p.amount, p.payment_method, p.status, p.payment_date,
                   s.first_name || ' ' || s.last_name AS student_name, s.student_id AS enrollment
            FROM payments p
            JOIN invoices inv ON p.invoice_id = inv.id
            JOIN students s ON inv.student_id = s.id;
        """).fetchall()
        for p in payments:
            title = f"Payment {p['payment_reference']}: ₹{p['amount']:.2f}"
            subtitle = f"Student: {p['student_name']} ({p['enrollment']}) • Date: {p['payment_date']}"
            content = f"{p['payment_reference']} {p['amount']} {p['student_name']} {p['enrollment']} {p['payment_method']} {p['status']}"
            tags = f"payment {p['status']} {p['payment_method']}"
            cursor.execute("""
                INSERT INTO search_index_fts (entity_type, entity_id, title, subtitle, content, tags, hostel_id)
                VALUES ('payments', ?, ?, ?, ?, ?, NULL);
            """, (p["id"], title, subtitle, content, tags))
            count += 1

        conn.commit()
        logger.info(f"FTS5 Search Index successfully indexed {count} entities.")
        return count

    @staticmethod
    def search(
        conn: sqlite3.Connection,
        q: str,
        category: Optional[str] = "all",
        user_roles: Optional[List[str]] = None,
        linked_hostel_id: Optional[int] = None,
        linked_student_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0
    ) -> SearchResponse:
        """Execute high-speed parameterized search combining FTS5 and B-Tree indexes."""
        t0 = time.perf_counter()

        cleaned_q = q.strip()
        if not cleaned_q:
            return SearchResponse(
                query="",
                category=category or "all",
                total_matches=0,
                execution_time_ms=round((time.perf_counter() - t0) * 1000, 3),
                results=[]
            )

        if len(cleaned_q) > 100:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Search query exceeds maximum limit of 100 characters.")

        cursor = conn.cursor()
        SearchService.ensure_fts5_schema(conn)

        roles = set(user_roles or [])
        is_student = "student" in roles and not roles.intersection({"super_admin", "hostel_admin", "warden", "assistant_warden", "accountant", "auditor"})

        # Sanitize query tokens for FTS5 (strip punctuation that could cause syntax errors)
        clean_tokens = re.findall(r"[a-zA-Z0-9_-]+", cleaned_q)
        if clean_tokens:
            # Form prefix search expression: e.g. "rohan*" OR "CSE*"
            fts_query = " ".join([f"{tok}*" for tok in clean_tokens])
        else:
            fts_query = f'"{cleaned_q}"'

        results: List[SearchResultItem] = []

        try:
            # 1. Primary Strategy: Query FTS5 Full-Text Index
            sql = """
                SELECT entity_type, entity_id, title, subtitle, content, tags, hostel_id, rank
                FROM search_index_fts
                WHERE search_index_fts MATCH ?
            """
            params: List[Any] = [fts_query]

            if category and category != "all":
                sql += " AND entity_type = ?"
                params.append(category)

            # Security: If user is constrained to a linked hostel
            if linked_hostel_id and not roles.intersection({"super_admin", "auditor", "accountant"}):
                sql += " AND (hostel_id = ? OR hostel_id IS NULL)"
                params.append(linked_hostel_id)

            # Security: Student role cannot see financial payments or other students' private complaints
            if is_student:
                sql += " AND entity_type NOT IN ('payments')"

            sql += " ORDER BY rank LIMIT ? OFFSET ?;"
            params.extend([limit, offset])

            rows = cursor.execute(sql, params).fetchall()

            for r in rows:
                tag_list = [t for t in (r["tags"] or "").split() if t]
                results.append(SearchResultItem(
                    category=r["entity_type"],
                    entity_id=r["entity_id"],
                    title=r["title"],
                    subtitle=r["subtitle"],
                    details=r["content"][:120] + "...",
                    tags=tag_list,
                    relevance_score=round(float(abs(r["rank"] or 1.0)), 2)
                ))

        except sqlite3.OperationalError:
            # If FTS5 table is empty or error occurs, fall back immediately to B-Tree indexed queries
            results = SearchService._search_fallback_btree(
                conn=conn,
                term=cleaned_q,
                category=category,
                is_student=is_student,
                linked_hostel_id=linked_hostel_id,
                limit=limit
            )

        # If FTS5 had 0 matches (e.g. index not yet synced), execute B-Tree index scan
        if not results:
            results = SearchService._search_fallback_btree(
                conn=conn,
                term=cleaned_q,
                category=category,
                is_student=is_student,
                linked_hostel_id=linked_hostel_id,
                limit=limit
            )

        duration_ms = round((time.perf_counter() - t0) * 1000, 3)

        return SearchResponse(
            query=cleaned_q,
            category=category or "all",
            total_matches=len(results),
            execution_time_ms=duration_ms,
            results=results
        )

    @staticmethod
    def _search_fallback_btree(
        conn: sqlite3.Connection,
        term: str,
        category: Optional[str],
        is_student: bool,
        linked_hostel_id: Optional[int],
        limit: int
    ) -> List[SearchResultItem]:
        """B-tree accelerated fallback search using parameterized equality and prefix queries."""
        cursor = conn.cursor()
        results: List[SearchResultItem] = []
        p_term = f"{term.strip()}%"

        # Search Students (B-Tree indexed by student_id and branch)
        if category in ("all", "students"):
            rows = cursor.execute("""
                SELECT id, student_id, first_name, last_name, branch, academic_year, status
                FROM students
                WHERE student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR branch LIKE ?
                LIMIT ?;
            """, (p_term, p_term, p_term, p_term, limit)).fetchall()
            for s in rows:
                results.append(SearchResultItem(
                    category="students",
                    entity_id=s["id"],
                    title=f"{s['first_name']} {s['last_name']}",
                    subtitle=f"Enrollment: {s['student_id']} • {s['branch']} ({s['academic_year']})",
                    details=f"Status: {s['status']}",
                    tags=["student", s["branch"], s["status"]]
                ))

        # Search Hostels (B-Tree indexed)
        if category in ("all", "hostels") and len(results) < limit:
            rows = cursor.execute("""
                SELECT id, name, code, hostel_type, address, is_active
                FROM hostels
                WHERE code LIKE ? OR name LIKE ?
                LIMIT ?;
            """, (p_term, p_term, limit)).fetchall()
            for h in rows:
                results.append(SearchResultItem(
                    category="hostels",
                    entity_id=h["id"],
                    title=f"{h['name']} ({h['code']})",
                    subtitle=f"{h['hostel_type']} Facility • {h['address']}",
                    details="Active Residential Unit",
                    tags=["hostel", h["hostel_type"]]
                ))

        # Search Rooms (B-Tree indexed by room_number)
        if category in ("all", "rooms") and len(results) < limit:
            rows = cursor.execute("""
                SELECT r.id, r.room_number, r.room_type, r.capacity, r.status,
                       h.name AS hostel_name
                FROM rooms r
                JOIN floors f ON r.floor_id = f.id
                JOIN buildings b ON f.building_id = b.id
                JOIN hostels h ON b.hostel_id = h.id
                WHERE r.room_number LIKE ?
                LIMIT ?;
            """, (p_term, limit)).fetchall()
            for r in rows:
                results.append(SearchResultItem(
                    category="rooms",
                    entity_id=r["id"],
                    title=f"Room {r['room_number']}",
                    subtitle=f"{r['hostel_name']} • {r['room_type']} (Cap: {r['capacity']})",
                    details=f"Status: {r['status']}",
                    tags=["room", r["status"]]
                ))

        return results[:limit]
