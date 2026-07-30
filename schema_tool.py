"""
schema_tool.py

This module gives the agent a way to "see" the database structure
before writing any SQL. Run this file directly to test it standalone.
"""

import sqlite3
import os

DB_PATH = DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop.db")


def get_schema() -> str:
    """
    Returns a human-readable description of every table and its columns.
    This is what we'll hand to the LLM so it knows what it's working with.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get all table names
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]

    schema_parts = []
    for table in tables:
        cur.execute(f"PRAGMA table_info({table})")
        columns = cur.fetchall()
        # Each column row: (cid, name, type, notnull, default_value, pk)
        col_descriptions = [f"{col[1]} ({col[2]})" for col in columns]
        schema_parts.append(f"Table: {table}\n  Columns: {', '.join(col_descriptions)}")

    conn.close()
    return "\n\n".join(schema_parts)


if __name__ == "__main__":
    print("=== Schema the agent will see ===\n")
    print(get_schema())
