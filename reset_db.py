"""Database Reset Script with Production Safety Guards.

This script drops and re-initializes the application database.
It is strictly guarded against accidental invocation and completely prohibited in production.
"""

import argparse
import gc
import os
import sys

from backend.app.config import settings
from backend.app.database.connection import get_db_connection, get_db_path
from backend.app.database.init_db import initialize_database


def main():
    parser = argparse.ArgumentParser(
        description="Safely reset and re-initialize the development database."
    )
    parser.add_argument(
        "--confirm-destructive-reset",
        action="store_true",
        help="Explicit flag required to confirm that all data will be permanently wiped."
    )
    args = parser.parse_args()

    # Guard 1: Environment check
    if getattr(settings, "app_env", "development").lower() in ("production", "prod"):
        sys.stderr.write("CRITICAL ERROR: Destructive database reset is strictly prohibited in production!\n")
        sys.exit(1)

    # Guard 2: Required flag
    if not args.confirm_destructive_reset:
        sys.stderr.write(
            "CRITICAL ERROR: Safety guard triggered. You must supply '--confirm-destructive-reset' to wipe the database.\n"
        )
        sys.exit(1)

    # Guard 3: Interactive confirmation if running in an interactive terminal
    if sys.stdin and sys.stdin.isatty():
        confirmation = input("Type 'CONFIRM_DISPOSABLE_RESET' to permanently wipe all data: ")
        if confirmation.strip() != "CONFIRM_DISPOSABLE_RESET":
            sys.stderr.write("Aborted: Confirmation string did not match.\n")
            sys.exit(1)

    gc.collect()
    db_file = get_db_path()
    print("Target DB File:", db_file)

    for ext in ["", "-wal", "-shm"]:
        f = db_file + ext
        if os.path.exists(f):
            try:
                os.remove(f)
                print("Removed:", f)
            except Exception as e:
                print("Could not remove:", f, e)

    print("Initializing fresh database...")
    initialize_database()

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM hostels;")
    print("Hostels count:", c.fetchone()[0])
    c.execute("SELECT COUNT(*) FROM rooms;")
    print("Rooms count:", c.fetchone()[0])
    c.execute("SELECT COUNT(*) FROM beds;")
    print("Beds count:", c.fetchone()[0])
    c.execute("SELECT COUNT(*) FROM users;")
    print("Users count:", c.fetchone()[0])
    conn.close()
    print("Database freshly cleared and initialized successfully!")


if __name__ == "__main__":
    main()
