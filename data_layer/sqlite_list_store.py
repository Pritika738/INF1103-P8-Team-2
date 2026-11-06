"""
data_layer/sqlite_list_store.py

A list-of-dicts store backed by one SQLite table - a drop-in replacement
for JsonListStore. It has the same two methods, load() -> list and
save(list) -> bool, so a class that owns a list store (e.g. the PDF and
report archives) works with either backend unchanged.

Each named field is a real column (so it can be indexed/queried); any
other key an entry carries is kept in an "extra" JSON column, so nothing
is lost. Rows come back in the order they were saved. A field whose
value is None is left out of the returned dict - callers use .get(), so
"missing" and "None" behave the same.

No print()/input(), no AI calls, no business rules.
"""

import json
import sqlite3
from contextlib import closing
from typing import List, Sequence

from .sqlite_db import connect


class SqliteListStore:
    """One SQLite table holding a list of flat dicts."""

    def __init__(self, db_path: str, table: str, fields: Sequence[str],
                 unique: Sequence[str] = (), indexes: Sequence[Sequence[str]] = ()):
        self.__db_path = db_path
        self.__table = table
        self.__fields = tuple(fields)
        self.__columns = self.__fields + ("extra",)

        # Identifiers come from our own code, never from user input, so
        # building the SQL with format() here is safe; every VALUE is still
        # passed as a "?" parameter.
        column_defs = ",\n    ".join(
            f"{f} TEXT" + (" UNIQUE" if f in unique else "") for f in self.__fields
        )
        index_defs = "".join(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_{'_'.join(cols)} "
            f"ON {table} ({', '.join(cols)});\n"
            for cols in indexes
        )
        self.__schema = (
            f"CREATE TABLE IF NOT EXISTS {table} (\n"
            f"    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            f"    {column_defs},\n"
            f"    extra TEXT\n"
            f");\n{index_defs}"
        )
        self.__insert_sql = "INSERT INTO {} ({}) VALUES ({})".format(
            table, ", ".join(self.__columns), ", ".join("?" for _ in self.__columns)
        )
        self.__select_sql = "SELECT {} FROM {} ORDER BY id".format(
            ", ".join(self.__columns), table
        )

    @property
    def db_path(self) -> str:
        return self.__db_path

    def _to_row(self, entry: dict) -> tuple:
        extra = {k: v for k, v in entry.items() if k not in self.__fields}
        return tuple(entry.get(f) for f in self.__fields) + (
            json.dumps(extra) if extra else None,
        )

    def _from_row(self, row: tuple) -> dict:
        data = dict(zip(self.__columns, row))
        entry = {f: data[f] for f in self.__fields if data[f] is not None}
        if data["extra"]:
            entry.update(json.loads(data["extra"]))
        return entry

    def load(self) -> List[dict]:
        """Every entry in saved order; [] if the table is empty or unreadable."""
        try:
            with closing(connect(self.__db_path, self.__schema)) as conn:
                return [self._from_row(row) for row in conn.execute(self.__select_sql)]
        except (sqlite3.Error, OSError, ValueError):
            return []

    def save(self, entries: List[dict]) -> bool:
        """Replace every entry in ONE transaction: either all are written or,
        on any failure, the previous contents are kept."""
        try:
            rows = [self._to_row(e) for e in entries]
            with closing(connect(self.__db_path, self.__schema)) as conn:
                with conn:  # commits on success, rolls back on error
                    conn.execute(f"DELETE FROM {self.__table}")
                    conn.executemany(self.__insert_sql, rows)
            return True
        except (sqlite3.Error, OSError, TypeError, ValueError, AttributeError):
            return False
