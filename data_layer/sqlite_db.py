"""
data_layer/sqlite_db.py

Shared SQLite connection helper. Every SQLite-backed store in data_layer
keeps its own table in the same database file (config.DATABASE_FILE) and
passes its own CREATE TABLE schema here, so adding a table never means
editing another store.

No print()/input(), no AI calls, no business rules.
"""

import os
import sqlite3


def connect(db_path: str, schema: str) -> sqlite3.Connection:
    """Open `db_path` (creating its folder if needed) and make sure the
    tables in `schema` exist. The caller is responsible for closing it."""
    directory = os.path.dirname(db_path) or "."
    os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(schema)
    return conn
