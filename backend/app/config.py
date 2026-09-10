"""Environment-based application configuration.

Course: BBAT104 - Fundamentals of TQM
Quality Goal: Q05 - Reduce Response Time
"""

import os
from typing import List
from pydantic import BaseModel


class Settings(BaseModel):
    """Centralized configuration loaded from environment with safe defaults."""
    app_name: str = os.getenv("APP_NAME", "Hostel Management System Web App")
    app_env: str = os.getenv("APP_ENV", "development")
    debug: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    secret_key: str = os.getenv("SECRET_KEY", "tqm-q05-hms-secret-key-2026")
    database_path: str = os.getenv("DATABASE_PATH", "data/hostel_web.db")
    enable_sqlite_wal: bool = os.getenv("ENABLE_SQLITE_WAL", "True").lower() in ("true", "1", "yes")
    cors_origins: List[str] = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]


settings = Settings()
