import sqlite3

conn = sqlite3.connect("instakill.db")
for table in ["user", "post", "follow", "like"]:
    count = conn.execute(f"SELECT COUNT(*) FROM \"{table}\"").fetchone()[0]
    print(f"Table {table}: {count} records")