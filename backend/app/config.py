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
    secret_key: str = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET_KEY") or "tqm-q05-hms-secret-key-2026-dev-32bytes-min"
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY") or "tqm-q05-hms-secret-key-2026-dev-32bytes-min"
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    refresh_token_expire_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    database_path: str = os.getenv("DATABASE_PATH", "data/hostel_web.db")
    enable_sqlite_wal: bool = os.getenv("ENABLE_SQLITE_WAL", "True").lower() in ("true", "1", "yes")
    enable_demo_seeding: bool = os.getenv("ENABLE_DEMO_SEEDING", "auto").lower() in ("true", "1", "yes") or (
        os.getenv("ENABLE_DEMO_SEEDING", "auto").lower() == "auto" and os.getenv("APP_ENV", "development") != "production"
    )
    cors_origins: List[str] = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]

    def validate_production_secrets(self) -> None:
        """Enforce strong, non-default cryptographic secret keys when running in production."""
        known_defaults = {
            "tqm-q05-hms-secret-key-2026",
            "tqm-q05-hms-secret-key-2026-dev-32bytes-min",
            "tqm-q05-hms-super-secret-jwt-key-2026-rohan-bakshi",
            "replace-this-in-production-with-a-secure-random-key",
            "prod_super_secret_jwt_signing_key_replace_me_randomly_12345",
            "secret",
            "changeme"
        }
        if self.app_env.lower() == "production":
            key = self.secret_key or self.jwt_secret_key
            if not key or key in known_defaults or len(key) < 32:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: In production mode (APP_ENV=production), "
                    "a cryptographically strong SECRET_KEY / JWT_SECRET_KEY of at least 32 characters "
                    "must be provided via environment variable, and cannot use default placeholders."
                )


settings = Settings()
settings.validate_production_secrets()
