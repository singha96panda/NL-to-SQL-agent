"""
sql_tool.py

This module gives the agent a way to actually run SQL against the database.
Safety guardrails are baked in:
  1. Only SELECT statements are allowed (string-level check)
  2. The connection itself is opened read-only (OS-level enforcement)
  3. Results are capped at MAX_ROWS

Run this file directly to test it standalone.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop.db")
MAX_ROWS = 50

# Keywords that should never appear in a query we execute
BLOCKED_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "CREATE", "TRUNCATE", "REPLACE", "ATTACH", "PRAGMA"
]


def _is_safe(query: str) -> tuple[bool, str]:
    """Checks a query string for obviously unsafe operations."""
    stripped = query.strip().rstrip(";")

    if not stripped.upper().startswith("SELECT"):
        return False, "Only SELECT statements are allowed."

    upper_query = stripped.upper()
    for keyword in BLOCKED_KEYWORDS:
        if keyword in upper_query:
            return False, f"Query contains a blocked keyword: {keyword}"

    # Block stacked queries like "SELECT ...; DROP TABLE ..."
    if ";" in stripped:
        return False, "Multiple statements in a single query are not allowed."

    return True, ""


def run_sql(query: str) -> dict:
    """
    Executes a read-only SQL query and returns the results.

    Returns a dict shaped like:
      {"success": True, "columns": [...], "rows": [...], "row_count": n}
    or
      {"success": False, "error": "..."}

    This dict shape matters: it's what we hand back to the agent so
    it can decide what to do next (show the answer, or retry on error).
    """
    safe, reason = _is_safe(query)
    if not safe:
        return {"success": False, "error": f"Query rejected: {reason}"}

    try:
        # Open connection in read-only mode (URI mode) — a second safety layer
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchmany(MAX_ROWS)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        conn.close()

        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }
    except sqlite3.Error as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    print("=== Test 1: A safe, valid query ===")
    result = run_sql("SELECT name, city FROM customers WHERE city = 'Bengaluru'")
    print(result)

    print("\n=== Test 2: A blocked query (DELETE) ===")
    result = run_sql("DELETE FROM customers WHERE customer_id = 1")
    print(result)

    print("\n=== Test 3: An invalid query (typo in column name) ===")
    result = run_sql("SELECT nam FROM customers")
    print(result)

    print("\n=== Test 4: A stacked/injected query ===")
    result = run_sql("SELECT * FROM customers; DROP TABLE customers;")
    print(result)
