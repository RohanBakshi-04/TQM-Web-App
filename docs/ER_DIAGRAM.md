# Entity Relationship (ER) Diagram — Hostel Management System Web App

**Course:** BBAT104 – Fundamentals of Total Quality Management (TQM)  
**Assigned Quality Goal:** Q05 – Reduce Response Time  

```mermaid
erDiagram
    %% User and Access Domain
    USERS ||--o{ USER_ROLES : "assigned"
    ROLES ||--o{ USER_ROLES : "granted"
    ROLES ||--o{ ROLE_PERMISSIONS : "contains"
    PERMISSIONS ||--o{ ROLE_PERMISSIONS : "mapped"
    USERS ||--o{ AUDIT_LOGS : "logs"
    USERS ||--o{ NOTIFICATIONS : "receives"

    %% Student Domain
    USERS ||--o| STUDENTS : "authenticates"
    STUDENTS ||--o{ STUDENT_GUARDIANS : "linked"
    GUARDIANS ||--o{ STUDENT_GUARDIANS : "cares_for"
    STUDENTS ||--o{ STUDENT_DOCUMENTS : "submits"
    STUDENTS ||--o{ ROOM_ALLOCATIONS : "holds"

    %% Hostel Inventory Domain
    HOSTELS ||--o{ BUILDINGS : "comprises"
    BUILDINGS ||--o{ FLOORS : "contains"
    FLOORS ||--o{ ROOMS : "divides_into"
    ROOMS ||--o{ BEDS : "furnishes"
    BEDS ||--o{ ROOM_ALLOCATIONS : "allocated_to"
    ROOMS ||--o{ ROOM_ALLOCATIONS : "contains_allocation"

    %% Operations & Attendance
    STUDENTS ||--o{ ATTENDANCE : "marked"
    STUDENTS ||--o{ LEAVE_REQUESTS : "applies"
    VISITORS ||--o{ VISITOR_LOGS : "visits"
    STUDENTS ||--o{ VISITOR_LOGS : "visited_by"

    %% Complaints & Maintenance
    STUDENTS ||--o{ COMPLAINTS : "files"
    ROOMS ||--o{ COMPLAINTS : "located_at"
    COMPLAINTS ||--o{ COMPLAINT_UPDATES : "tracked_by"
    ROOMS ||--o{ MAINTENANCE_TASKS : "requires"
    MAINTENANCE_TASKS ||--o{ MAINTENANCE_HISTORY : "records"

    %% Financial Domain
    FEE_STRUCTURES ||--o{ INVOICES : "calculates"
    STUDENTS ||--o{ INVOICES : "billed_to"
    INVOICES ||--o{ INVOICE_ITEMS : "details"
    INVOICES ||--o{ PAYMENTS : "settled_by"
    PAYMENTS ||--o{ REFUNDS : "adjusts"

    %% Mess & Inventory Domain
    STUDENTS ||--o{ MESS_SUBSCRIPTIONS : "subscribes"
    STUDENTS ||--o{ MEAL_ATTENDANCE : "eats"
    INVENTORY_CATEGORIES ||--o{ INVENTORY_ITEMS : "classifies"
    INVENTORY_ITEMS ||--o{ INVENTORY_TRANSACTIONS : "tracks"
    MAINTENANCE_TASKS ||--o{ INVENTORY_TRANSACTIONS : "consumes"

    %% Entity Attribute Definitions
    USERS {
        int id PK
        string username UK
        string email UK
        string password_hash
        string first_name
        string last_name
        int is_active
    }

    STUDENTS {
        int id PK
        string student_id UK
        string email UK
        string phone
        string branch
        string academic_year
        string status
    }

    HOSTELS {
        int id PK
        string name UK
        string code UK
        string hostel_type
    }

    ROOMS {
        int id PK
        int floor_id FK
        string room_number
        int capacity
        float base_fee
        string status
    }

    BEDS {
        int id PK
        int room_id FK
        string bed_number
        string status
    }

    ROOM_ALLOCATIONS {
        int id PK
        int student_id FK
        int bed_id FK
        int room_id FK
        string start_date
        string end_date
        string allocation_status
    }

    INVOICES {
        int id PK
        string invoice_number UK
        int student_id FK
        float total_amount
        float paid_amount
        string status
    }

    PAYMENTS {
        int id PK
        string payment_reference UK
        int invoice_id FK
        float amount
        string payment_method
    }

    COMPLAINTS {
        int id PK
        string complaint_id UK
        int student_id FK
        string category
        string severity
        string status
    }
```
