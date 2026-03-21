"""Unit tests for backend/database/connection.py — per-request connection reuse."""

import sqlite3
from unittest.mock import patch, MagicMock
import pytest
from flask import g
from backend.database.connection import get_connection, close_connection, execute_query


class TestGetConnection:
    def test_returns_same_object_within_request(self, app):
        """Two calls to get_connection() in the same app context return the same object."""
        with app.app_context():
            conn1 = get_connection()
            conn2 = get_connection()
            assert conn1 is conn2

    def test_returns_new_object_across_requests(self, app):
        """Connections from two separate app contexts are different objects."""
        with app.app_context():
            conn1 = get_connection()
            conn1_id = id(conn1)
        with app.app_context():
            conn2 = get_connection()
            assert id(conn2) != conn1_id

    def test_foreign_keys_enabled(self, app):
        """PRAGMA foreign_keys is ON for the connection."""
        with app.app_context():
            conn = get_connection()
            result = conn.execute("PRAGMA foreign_keys;").fetchone()
            assert result[0] == 1

    def test_row_factory_set(self, app):
        """Connection's row_factory is sqlite3.Row."""
        with app.app_context():
            conn = get_connection()
            assert conn.row_factory is sqlite3.Row


class TestCloseConnection:
    def test_teardown_closes_and_removes(self, app):
        """After close_connection, g no longer has 'db'."""
        with app.app_context():
            conn = get_connection()
            assert 'db' in g
            close_connection()
            assert 'db' not in g

    def test_close_connection_twice_no_error(self, app):
        """Calling close_connection when no connection exists does not raise."""
        with app.app_context():
            get_connection()
            close_connection()
            close_connection()  # should not raise


class TestExecuteQuery:
    def test_reuses_connection(self, app):
        """sqlite3.connect is called exactly once for two execute_query() calls in one request."""
        with app.app_context():
            with patch('backend.database.connection.sqlite3.connect', wraps=sqlite3.connect) as mock_connect:
                # Reset g so our mock captures the connect call
                g.pop('db', None)
                execute_query("SELECT 1", fetch_one=True)
                execute_query("SELECT 2", fetch_one=True)
                assert mock_connect.call_count == 1

    def test_commit_returns_lastrowid(self, app):
        """Insert returns lastrowid."""
        with app.app_context():
            execute_query(
                "CREATE TABLE IF NOT EXISTS _test (id INTEGER PRIMARY KEY, val TEXT)",
                commit=True,
            )
            row_id = execute_query(
                "INSERT INTO _test (val) VALUES (?)", ("hello",), commit=True
            )
            assert isinstance(row_id, int)
            assert row_id >= 1

    def test_fetch_one_returns_dict(self, app):
        """fetch_one returns a dict or None."""
        with app.app_context():
            execute_query("CREATE TABLE IF NOT EXISTS _test2 (id INTEGER PRIMARY KEY, val TEXT)", commit=True)
            execute_query("INSERT INTO _test2 (val) VALUES (?)", ("x",), commit=True)
            result = execute_query("SELECT * FROM _test2 LIMIT 1", fetch_one=True)
            assert isinstance(result, dict)
            assert result['val'] == 'x'

    def test_fetch_one_returns_none(self, app):
        """fetch_one returns None when no rows match."""
        with app.app_context():
            execute_query("CREATE TABLE IF NOT EXISTS _test3 (id INTEGER PRIMARY KEY)", commit=True)
            result = execute_query("SELECT * FROM _test3 WHERE id = 9999", fetch_one=True)
            assert result is None

    def test_fetch_all_returns_list_of_dicts(self, app):
        """fetch_all returns a list of dicts."""
        with app.app_context():
            execute_query("CREATE TABLE IF NOT EXISTS _test4 (id INTEGER PRIMARY KEY, val TEXT)", commit=True)
            execute_query("INSERT INTO _test4 (val) VALUES (?)", ("a",), commit=True)
            execute_query("INSERT INTO _test4 (val) VALUES (?)", ("b",), commit=True)
            results = execute_query("SELECT * FROM _test4", fetch_all=True)
            assert isinstance(results, list)
            assert len(results) == 2
            assert all(isinstance(r, dict) for r in results)

    def test_integrity_error_has_user_message(self, app):
        """Duplicate unique value raises IntegrityError with .user_message."""
        with app.app_context():
            execute_query(
                "CREATE TABLE IF NOT EXISTS _test5 (id INTEGER PRIMARY KEY, email TEXT UNIQUE)",
                commit=True,
            )
            execute_query("INSERT INTO _test5 (email) VALUES (?)", ("a@b.com",), commit=True)
            with pytest.raises(sqlite3.IntegrityError) as exc_info:
                execute_query("INSERT INTO _test5 (email) VALUES (?)", ("a@b.com",), commit=True)
            assert hasattr(exc_info.value, 'user_message')
            assert exc_info.value.user_message  # non-empty string
