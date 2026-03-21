"""Integration tests for per-request connection reuse."""

import sqlite3
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import pytest
from flask import g
from backend.database.connection import get_connection, execute_query


class TestMultipleQueriesSingleConnection:
    def test_multiple_queries_single_connection(self, app):
        """Within one request, all execute_query calls share one sqlite3.connect call."""
        with app.app_context():
            with patch('backend.database.connection.sqlite3.connect', wraps=sqlite3.connect) as mock_connect:
                g.pop('db', None)
                execute_query("SELECT 1", fetch_one=True)
                execute_query("SELECT 2", fetch_one=True)
                execute_query("SELECT 3", fetch_one=True)
                assert mock_connect.call_count == 1


class TestConnectionClosedAfterRequest:
    def test_connection_closed_after_request(self, app):
        """After app context exits, the connection is closed via teardown."""
        with app.app_context():
            conn = get_connection()
        # After exiting app_context, teardown fires and closes conn
        with pytest.raises(Exception):
            conn.execute("SELECT 1")


class TestConcurrentRequestsIndependentConnections:
    def test_concurrent_requests_independent(self, app):
        """Two simultaneous requests each get their own connection."""
        conn_ids = []

        def make_request():
            with app.app_context():
                conn = get_connection()
                conn_ids.append(id(conn))

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(make_request)
            f2 = executor.submit(make_request)
            f1.result()
            f2.result()

        assert len(conn_ids) == 2
        assert conn_ids[0] != conn_ids[1]


class TestRollbackOnRequestError:
    def test_teardown_closes_on_exception(self, app):
        """If an exception occurs, the teardown still closes the connection cleanly."""
        conn_ref = None
        try:
            with app.app_context():
                conn_ref = get_connection()
                raise RuntimeError("boom")
        except RuntimeError:
            pass

        # Connection should be closed after app context teardown
        with pytest.raises(Exception):
            conn_ref.execute("SELECT 1")
