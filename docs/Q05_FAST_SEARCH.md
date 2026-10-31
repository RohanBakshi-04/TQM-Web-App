# Q05 Fast Search Architecture & Implementation

**Course:** BBAT104 - Fundamentals of Total Quality Management (TQM)  
**Quality Goal:** Q05 - Reduce Response Time (<10ms SLA)  
**Component:** Unified Multi-Domain Search Engine & FTS5 Acceleration  
**Backend Endpoint:** `GET /api/v1/search`

---

## 1. Overview & TQM Quality Rationale

Under the Total Quality Management (TQM) framework, **Quality Goal Q05** mandates that the Hostel Management System deliver immediate operational responsiveness. Administrative staff, wardens, security personnel, and students require instant search capabilities across disparate operational entities—ranging from enrollment identifiers and room numbers to disciplinary complaints and fee payments.

Standard database query patterns utilizing leading wildcards (`LIKE '%term%'`) force full table scans across multiple tables, scaling poorly and causing severe UI latency. To achieve true sub-10ms execution, the system implements a **hybrid search architecture**:

1. **SQLite FTS5 Full-Text Virtual Engine:** Compiles an inverted index with tokenization, prefix matching (`token*`), and BM25 relevance ranking.
2. **Targeted B-Tree Index Acceleration:** Supports structured equality and prefix lookups for numerical, enrollment, and status attributes.
3. **Role-Based Authorization Barrier:** Prevents unauthorized information disclosure at the database query layer.

```
+-------------------------------------------------------------+
|               Client Request (Ctrl + K / Search)            |
|       (250ms Debounce, Category Filter, Query Token)        |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|             FastAPI Server-Side Search Router               |
|      (Auth Dependency, Role Extraction, Token Sanitation)   |
+------------------------------+------------------------------+
                               |
              +----------------+----------------+
              |                                 |
              v                                 v
+-------------------------------+ +-----------------------------+
|    FTS5 Virtual Index Search  | | B-Tree Fallback / Prefix    |
| (Inverted Token Index, BM25)  | | (Indexed Equality/Prefix)   |
+---------------+---------------+ +--------------+--------------+
                |                                |
                +----------------+---------------+
                                 |
                                 v
+---------------------------------------------------------------+
|     Role-Based Security Filter & Parameterized Data Guard     |
|   - Students: Payments & confidential records omitted         |
|   - Wardens: Constrained to designated hostel boundaries      |
+--------------------------------+------------------------------+
                                 |
                                 v
+---------------------------------------------------------------+
|     JSON Response with Telemetry: X-Response-Time-Ms (<10ms)  |
+---------------------------------------------------------------+
```

---

## 2. SQLite FTS5 Virtual Table Configuration

The FTS5 virtual table aggregates searchable text and metadata from operational tables into a unified inverted index.

### 2.1 Table Schema Definition
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS search_index_fts USING fts5(
    entity_type UNINDEXED,     -- e.g. 'students', 'hostels', 'rooms', 'complaints'
    entity_id UNINDEXED,       -- Primary key reference to source record
    title,                     -- Primary heading (e.g. 'Priya Sharma', 'Room 201')
    subtitle,                  -- Secondary descriptive text (e.g. 'Enrollment: 2410301012')
    content,                   -- Searchable keywords, contact details, tags
    tags,                      -- Categorical tokens (e.g. 'active', 'CSE', 'Double')
    hostel_id UNINDEXED,       -- Facility boundary for role isolation
    tokenize = 'porter unicode61'
);
```

### 2.2 Tokenizer & Ranking Strategy
- **Tokenizer:** `tokenize = 'porter unicode61'` combines Unicode case folding with the **Porter Stemming algorithm**, enabling linguistic stem matching (e.g., searching for `"allocating"` matches `"allocate"` and `"allocation"`).
- **Prefix Expansion:** User search tokens are automatically expanded with the wildcard operator (e.g., query `"Priy"` expands to `"Priy*"`) for seamless typeahead without leading-wildcard penalties.
- **Relevance Scoring:** SQLite calculates BM25 ranking scores (`rank`), placing high-frequency and exact matches at the top of the result list.

---

## 3. Parameterized Query Patterns & SQL Injection Protection

In accordance with strict security rules, all search queries are strictly parameterized:

```python
sql = """
    SELECT entity_type, entity_id, title, subtitle, content, tags, hostel_id, rank
    FROM search_index_fts
    WHERE search_index_fts MATCH ?
"""
params = [fts_query]

if category and category != "all":
    sql += " AND entity_type = ?"
    params.append(category)

if linked_hostel_id and not roles.intersection({"super_admin", "auditor", "accountant"}):
    sql += " AND (hostel_id = ? OR hostel_id IS NULL)"
    params.append(linked_hostel_id)

sql += " ORDER BY rank LIMIT ? OFFSET ?;"
params.extend([limit, offset])

rows = cursor.execute(sql, params).fetchall()
```

- **Query Sanitization:** Input tokens are filtered using regex `[a-zA-Z0-9_-]+` prior to FTS5 compilation, preventing syntax errors from raw symbols like quotes or brackets.
- **No String Formatting:** No user input is ever interpolated into raw SQL statements.

---

## 4. Role-Based Authorization & Data Isolation

Search results are filtered dynamically based on authenticated JWT claims:

| User Role | Search Capabilities & Data Boundaries |
|:---|:---|
| **Super Admin / Auditor** | Full system visibility across all 7 categories with global scope |
| **Hostel Admin / Warden** | Full visibility scoped strictly to their assigned hostel facility |
| **Accountant** | Full visibility into students, rooms, invoices, and payments |
| **Student** | Access restricted to public directory, hostels, room types, and own records; **payments and other students' grievances are strictly excluded** |
| **Security Guard** | Access restricted to student gate verifications and visitor records |

---

## 5. Frontend Integration & User Experience

The search interface is integrated into the application shell:
- **Shortcut:** Accessible from anywhere using `Ctrl + K` (or `Cmd + K` on macOS).
- **Debounced Input:** 250ms debouncing eliminates redundant network requests while preserving a fluid typeahead experience.
- **Category Filter Pills:** Users can toggle between *All Entities*, *Students*, *Hostels*, *Rooms*, *Allocations*, *Complaints*, and *Payments*.
- **Sub-10ms Telemetry Pill:** Live query latency is displayed in the modal header (e.g., `⚡ 1.25 ms (<10ms SLA)`).
- **Result Highlighting:** Matching query tokens are automatically highlighted within titles and subtitles using styled `<mark>` elements.
- **Seamless Navigation:** Selecting a search result navigates directly to the target record within the application.
