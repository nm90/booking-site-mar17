"""
Database connection utilities. Handles SQLite connection and query execution.

MVC Role: Infrastructure Layer
- Provides low-level database access
- Models use these functions to persist data
- Reuses one connection per Flask request via g (teardown registered in app.py)
"""

import sqlite3
import os
from typing import Any, List, Optional
from flask import g


DB_PATH = os.environ.get(
    'DATABASE_PATH',
    os.path.join(os.path.dirname(__file__), 'booking_site.db')
)


def get_connection() -> sqlite3.Connection:
    """Return the per-request connection, creating it if needed."""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db


def close_connection(exception=None) -> None:
    """Close the per-request connection. Registered with app.teardown_appcontext."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def execute_query(query: str, params: tuple = (), fetch_one: bool = False,
                  fetch_all: bool = False, commit: bool = False) -> Optional[Any]:
    """
    Execute a SQL query with error handling.

    Args:
        query: SQL query string (use ? for parameters)
        params: Tuple of parameters to safely substitute
        fetch_one: If True, return single row
        fetch_all: If True, return all rows
        commit: If True, commit changes (INSERT/UPDATE/DELETE)

    Returns:
        - fetch_one: dict or None
        - fetch_all: list of dicts
        - commit: lastrowid
        - Otherwise: None
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)

        if commit:
            conn.commit()
            return cursor.lastrowid
        elif fetch_one:
            result = cursor.fetchone()
            return dict(result) if result else None
        elif fetch_all:
            results = cursor.fetchall()
            return [dict(row) for row in results]

        return None

    except sqlite3.IntegrityError as e:
        error_message = str(e)
        e.user_message = _parse_integrity_error(error_message)
        raise

    except sqlite3.Error as e:
        raise


def _parse_integrity_error(error_message: str) -> str:
    """Parse SQLite IntegrityError into a user-friendly message."""
    error_lower = error_message.lower()

    if 'unique constraint failed' in error_lower:
        if 'users.email' in error_lower:
            return "An account with this email already exists"
        parts = error_message.split(':')
        if len(parts) > 1:
            field = parts[1].strip().split('.')[-1]
            return f"{field.replace('_', ' ').capitalize()} already exists"
        return "This value already exists"

    if 'foreign key constraint failed' in error_lower:
        return "Referenced record does not exist"

    if 'not null constraint failed' in error_lower:
        parts = error_message.split(':')
        if len(parts) > 1:
            field = parts[1].strip().split('.')[-1]
            return f"{field.replace('_', ' ').capitalize()} is required"
        return "Required field is missing"

    if 'check constraint failed' in error_lower:
        return "Value is not valid for this field"

    return error_message
