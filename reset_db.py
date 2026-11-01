import os
import gc
from backend.app.database.connection import get_db_path
from backend.app.database.init_db import initialize_database
from backend.app.database.connection import get_db_connection

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
