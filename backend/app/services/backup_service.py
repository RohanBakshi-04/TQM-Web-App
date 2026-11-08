"""Database Backup and Restore Service.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Reduce Response Time (< 10ms SLA)
"""

import hashlib
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
from backend.app.database.connection import get_db_path, get_db_connection
from backend.app.utils.logger import logger

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BACKUP_DIR = os.getenv("BACKUP_DIR") or os.path.join(PROJECT_ROOT, "data", "backups")


class BackupService:
    """Safe SQLite WAL online backup, integrity verification, and recovery engine."""

    @classmethod
    def _ensure_backup_dir(cls, custom_dir: Optional[str] = None) -> str:
        bdir = custom_dir or BACKUP_DIR
        os.makedirs(bdir, exist_ok=True)
        return bdir

    @classmethod
    def create_backup(
        cls,
        note: Optional[str] = None,
        custom_db_path: Optional[str] = None,
        custom_backup_dir: Optional[str] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a timestamped SQLite-safe online backup utilizing SQLite backup API."""
        backup_dir = cls._ensure_backup_dir(custom_backup_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_filename = f"hms_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)

        src_conn = get_db_connection(custom_db_path) if custom_db_path else get_db_connection()
        try:
            # Checkpoint WAL passively to ensure consistent frame sync without blocking
            try:
                src_conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
            except sqlite3.OperationalError:
                pass

            # Destination backup connection
            dest_conn = sqlite3.connect(backup_path)
            try:
                # Online SQLite safe backup (atomic copy even with WAL mode)
                src_conn.backup(dest_conn)
            finally:
                dest_conn.close()

            # Verify integrity of the created backup
            integrity = cls.verify_backup_integrity(backup_path)
            if not integrity["is_valid"]:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                raise RuntimeError(f"Backup integrity verification failed: {integrity['error']}")

            file_size = os.path.getsize(backup_path)
            h = hashlib.sha256()
            with open(backup_path, "rb") as bf:
                while chunk := bf.read(65536):
                    h.update(chunk)
            checksum = h.hexdigest()
            logger.info(f"Database backup created successfully: {backup_filename} ({file_size} bytes, sha256: {checksum[:8]}...)")

            # Record backup telemetry and audit trail
            try:
                cursor = src_conn.cursor()
                try:
                    cursor.execute(
                        """
                        INSERT INTO backup_metadata (filename, file_path, size_bytes, checksum_sha256, status, initiated_by, notes)
                        VALUES (?, ?, ?, ?, 'Completed', ?, ?);
                        """,
                        (backup_filename, backup_path, file_size, checksum, username or "system", note or "Automated backup")
                    )
                except sqlite3.OperationalError:
                    pass

                cursor.execute(
                    """
                    INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details)
                    VALUES (?, ?, 'CREATE_BACKUP', 'database', ?, ?);
                    """,
                    (user_id or 1, username or "system", backup_filename, f"Size: {file_size} bytes. Note: {note or 'Automated backup'}")
                )
                src_conn.commit()
            except Exception as audit_err:
                logger.debug(f"Audit log skipped during backup creation: {audit_err}")

            return {
                "status": "success",
                "filename": backup_filename,
                "path": backup_path,
                "size_bytes": file_size,
                "checksum_sha256": checksum,
                "timestamp": timestamp,
                "table_count": integrity["table_count"],
                "note": note or "Automated backup"
            }
        finally:
            src_conn.close()

    @classmethod
    def verify_backup_integrity(cls, backup_path: str) -> Dict[str, Any]:
        """Verify the integrity and foreign-key consistency of a backup SQLite file."""
        if not os.path.exists(backup_path):
            return {"is_valid": False, "error": "File does not exist", "table_count": 0}

        try:
            conn = sqlite3.connect(backup_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            res = cursor.fetchone()
            if not res or res[0] != "ok":
                conn.close()
                return {"is_valid": False, "error": f"Integrity check failed: {res[0] if res else 'None'}", "table_count": 0}

            cursor.execute("PRAGMA foreign_key_check;")
            fk_violations = cursor.fetchall()
            if fk_violations:
                conn.close()
                return {"is_valid": False, "error": f"Foreign key check failed: {len(fk_violations)} violations", "table_count": 0}

            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%';")
            table_count = cursor.fetchone()[0]
            conn.close()

            h = hashlib.sha256()
            with open(backup_path, "rb") as bf:
                while chunk := bf.read(65536):
                    h.update(chunk)
            checksum = h.hexdigest()

            return {"is_valid": True, "error": None, "table_count": table_count, "checksum_sha256": checksum}
        except Exception as e:
            return {"is_valid": False, "error": str(e), "table_count": 0, "checksum_sha256": None}

    @classmethod
    def list_backups(cls, custom_backup_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all available backup files with size and verification status."""
        backup_dir = cls._ensure_backup_dir(custom_backup_dir)
        backups = []

        if not os.path.exists(backup_dir):
            return backups

        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith(".db"):
                p = os.path.join(backup_dir, f)
                stat = os.stat(p)
                backups.append({
                    "filename": f,
                    "path": p,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        return backups

    @classmethod
    def restore_backup(
        cls,
        backup_filename: str,
        custom_db_path: Optional[str] = None,
        custom_backup_dir: Optional[str] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Safely restore database from a verified backup with pre-restore safety snapshot."""
        backup_dir = cls._ensure_backup_dir(custom_backup_dir)

        # Security: Prevent path traversal and invalid file extensions
        clean_filename = os.path.basename(backup_filename)
        if clean_filename != backup_filename or not clean_filename.endswith(".db"):
            raise ValueError("Invalid backup filename. Directory traversal characters and non-.db extensions are prohibited.")

        backup_path = os.path.join(backup_dir, clean_filename)
        real_backup_path = os.path.realpath(backup_path)
        real_backup_dir = os.path.realpath(backup_dir)
        if not real_backup_path.startswith(real_backup_dir):
            raise ValueError("Access denied: Backup path escapes authorized backup directory.")

        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file '{backup_filename}' does not exist.")

        # 1. Verify integrity of backup to restore
        integrity = cls.verify_backup_integrity(backup_path)
        if not integrity["is_valid"]:
            raise ValueError(f"Cannot restore: Backup file is corrupt ({integrity['error']}).")

        # 2. Create pre-restore safety snapshot of current database
        safety_snapshot = cls.create_backup(
            note="Pre-restore safety snapshot",
            custom_db_path=custom_db_path,
            custom_backup_dir=custom_backup_dir,
            user_id=user_id,
            username=username
        )

        # 3. Restore backup into target database safely using SQLite backup API
        live_db_path = get_db_path(custom_db_path) if custom_db_path else get_db_path()
        backup_conn = sqlite3.connect(backup_path)
        live_conn = sqlite3.connect(live_db_path)
        try:
            backup_conn.backup(live_conn)
        finally:
            backup_conn.close()
            live_conn.close()

        # 4. Verify live database integrity post-restore
        live_integrity = cls.verify_backup_integrity(live_db_path)
        if not live_integrity["is_valid"]:
            logger.critical("Restore produced invalid database state! Restoring from pre-restore safety snapshot...")
            cls.restore_backup(
                safety_snapshot["filename"],
                custom_db_path=custom_db_path,
                custom_backup_dir=custom_backup_dir,
                user_id=user_id,
                username=username
            )
            raise RuntimeError("Database restore failed integrity check. Reverted to pre-restore snapshot.")

        # Record audit trail and backup metadata tracking
        try:
            audit_conn = get_db_connection(custom_db_path) if custom_db_path else get_db_connection()
            cursor = audit_conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO backup_metadata (filename, file_path, size_bytes, checksum_sha256, status, initiated_by, notes)
                    VALUES (?, ?, ?, ?, 'Restored', ?, ?)
                    ON CONFLICT(filename) DO UPDATE SET status = 'Restored', notes = excluded.notes;
                    """,
                    (
                        clean_filename,
                        backup_path,
                        os.path.getsize(backup_path),
                        integrity.get("checksum_sha256", "restored"),
                        username or "system",
                        f"Restored into database. Safety snapshot: {safety_snapshot['filename']}"
                    )
                )
            except sqlite3.OperationalError:
                pass

            cursor.execute(
                """
                INSERT INTO audit_logs (user_id, username, action, entity_name, entity_id, details)
                VALUES (?, ?, 'RESTORE_BACKUP', 'database', ?, ?);
                """,
                (user_id or 1, username or "system", backup_filename, f"Restored from {backup_filename}. Safety snapshot: {safety_snapshot['filename']}")
            )
            audit_conn.commit()
            audit_conn.close()
        except Exception as audit_err:
            logger.debug(f"Audit log skipped during restore: {audit_err}")

        logger.info(f"Database successfully restored from {backup_filename}")
        return {
            "status": "success",
            "message": f"Database successfully restored from {backup_filename}.",
            "safety_snapshot": safety_snapshot["filename"],
            "table_count": live_integrity["table_count"]
        }
