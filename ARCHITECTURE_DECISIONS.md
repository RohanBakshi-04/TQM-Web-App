# ARCHITECTURE DECISIONS (ADR) — HOSTEL MANAGEMENT SYSTEM WEB APP

## ADR 01: Multi-Tier Modular Directory Structure
- **Date:** 2026-09-04
- **Status:** Accepted
- **Context:** Transitioning the baseline desktop system into an enterprise-grade web application requires clear separation of concerns to prevent coupling between routing, business logic, persistence, and presentation.
- **Decision:** Adopt a clean modular structure separating `backend/` (FastAPI app, database, models, routers, services, utils), `frontend/` (assets and client controllers), `data/` (isolated storage), and `docs/`.
- **Consequences:** Ensures code maintainability, simplifies isolated unit testing, and facilitates phased development.

## ADR 02: Selection of Python FastAPI + Uvicorn for Backend
- **Date:** 2026-09-08
- **Status:** Accepted
- **Context:** To satisfy Quality Goal Q05 (Reduce Response Time), the web server must handle high concurrent throughput with minimal CPU and latency overhead.
- **Decision:** Select FastAPI built on Starlette and Pydantic, served via the Uvicorn ASGI runner.
- **Consequences:** Asynchronous non-blocking I/O achieves sub-5ms API response times while providing automated OpenAPI/Swagger documentation.

## ADR 03: SQLite Persistence with WAL Mode and Foreign Keys
- **Date:** 2026-09-10
- **Status:** Accepted
- **Context:** The system requires a zero-configuration, robust local database engine suitable for academic evaluation and standalone deployment.
- **Decision:** Utilize SQLite3 configured with Write-Ahead Logging (`WAL`), `PRAGMA synchronous = NORMAL;`, `PRAGMA busy_timeout = 5000;`, and explicit `PRAGMA foreign_keys = ON;`.
- **Consequences:** Concurrent readers do not block writers, transaction latencies drop under 1ms, and relational data integrity is strictly maintained.

## ADR 04: Zero-Build Lightweight Frontend (Tailwind CDN + Alpine.js)
- **Date:** 2026-09-15
- **Status:** Accepted
- **Context:** The project requires a lightweight, modern web interface without heavy `node_modules` dependencies, complex build configurations, or bundle loading delays.
- **Decision:** Leverage HTML5, Tailwind CSS via CDN, and Alpine.js for lightweight client-side reactivity and modal management.
- **Consequences:** Instant page loading, minimal network overhead, zero build steps, and clean separation between API and UI.
