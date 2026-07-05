"""
Database connection utilities. Handles SQLite/Postgres connections and query execution.

MVC Role: Infrastructure Layer
- Provides low-level database access
- Models use these functions to persist data
- Reuses one connection per Flask request via g (teardown registered in app.py)

Dialect selection: if DATABASE_URL is set the app talks to Postgres via psycopg
(e.g. a Supabase connection string); otherwise it uses the local SQLite file.
All dialect differences (placeholders, insert ids, error mapping, transactions)
are handled here so models keep writing ?-style SQL.
"""

import sqlite3
import os
from contextlib import contextmanager
from typing import Any, List, Optional
from flask import g


DB_PATH = os.environ.get(
    'DATABASE_PATH',
    os.path.join(os.path.dirname(__file__), 'booking_site.db')
)

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.string import TextLoader

    INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.errors.IntegrityError)
else:
    INTEGRITY_ERRORS = (sqlite3.IntegrityError,)


def _is_postgres() -> bool:
    return bool(DATABASE_URL)


def translate_placeholders(query: str) -> str:
    """Convert ?-style placeholders to %s for psycopg. No-op on SQLite."""
    if not _is_postgres():
        return query
    return query.replace('?', '%s')


def get_connection():
    """Return the per-request connection, creating it if needed."""
    if 'db' not in g:
        if _is_postgres():
            # autocommit keeps each execute_query() call standalone (matching
            # SQLite behavior); begin_immediate() opens explicit transactions.
            g.db = psycopg.connect(
                DATABASE_URL, row_factory=dict_row, autocommit=True
            )
            # Templates and models treat dates/timestamps as strings (SQLite
            # behavior, e.g. created_at[:10], date.fromisoformat(...)) — load
            # them as text instead of datetime objects.
            for pg_type in ('date', 'timestamp', 'timestamptz'):
                g.db.adapters.register_loader(pg_type, TextLoader)
        else:
            g.db = sqlite3.connect(DB_PATH, timeout=10)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db


def close_connection(exception=None) -> None:
    """Close the per-request connection. Registered with app.teardown_appcontext."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


@contextmanager
def begin_immediate():
    """Wrap multiple execute_query() calls in a single transaction."""
    conn = get_connection()
    if _is_postgres():
        g.in_transaction = True
        try:
            with conn.transaction():
                yield conn
        finally:
            g.in_transaction = False
    else:
        conn.execute("BEGIN IMMEDIATE")
        g.in_transaction = True
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
        finally:
            g.in_transaction = False


def _is_insert(query: str) -> bool:
    return query.lstrip().upper().startswith('INSERT')


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
        - commit: inserted row id for INSERTs (None for UPDATE/DELETE on Postgres)
        - Otherwise: None
    """
    conn = get_connection()
    try:
        if _is_postgres():
            pg_query = translate_placeholders(query)
            returning_id = (
                commit and _is_insert(pg_query)
                and 'RETURNING' not in pg_query.upper()
            )
            if returning_id:
                pg_query += ' RETURNING id'
            cursor = conn.execute(pg_query, params)

            if commit:
                # autocommit (or begin_immediate's transaction) handles the commit
                if returning_id:
                    row = cursor.fetchone()
                    return row['id'] if row else None
                return None
            elif fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            return None

        cursor = conn.cursor()
        cursor.execute(query, params)

        if commit:
            if not getattr(g, 'in_transaction', False):
                conn.commit()
            return cursor.lastrowid
        elif fetch_one:
            result = cursor.fetchone()
            return dict(result) if result else None
        elif fetch_all:
            results = cursor.fetchall()
            return [dict(row) for row in results]

        return None

    except INTEGRITY_ERRORS as e:
        e.user_message = _parse_integrity_error(e)
        raise


def _parse_integrity_error(error) -> str:
    """Parse an IntegrityError (SQLite or Postgres) into a user-friendly message."""
    if _is_postgres() and not isinstance(error, sqlite3.IntegrityError):
        return _parse_pg_integrity_error(error)
    return _parse_sqlite_integrity_error(str(error))


def _parse_pg_integrity_error(error) -> str:
    """Map psycopg IntegrityError SQLSTATE codes to user-friendly messages."""
    sqlstate = error.sqlstate or ''
    diag = error.diag
    constraint = (diag.constraint_name or '').lower()
    column = diag.column_name or ''

    if sqlstate == '23505':  # unique_violation
        if constraint == 'users_email_unique':
            return "An account with this email already exists"
        if constraint:
            # e.g. uq_reviews_booking -> "Booking already exists"
            field = constraint.split('_')[-1]
            return f"{field.replace('_', ' ').capitalize()} already exists"
        return "This value already exists"

    if sqlstate == '23503':  # foreign_key_violation
        return "Referenced record does not exist"

    if sqlstate == '23502':  # not_null_violation
        if column:
            return f"{column.replace('_', ' ').capitalize()} is required"
        return "Required field is missing"

    if sqlstate == '23514':  # check_violation
        return "Value is not valid for this field"

    return str(error)


def _parse_sqlite_integrity_error(error_message: str) -> str:
    """Parse SQLite IntegrityError text into a user-friendly message."""
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
