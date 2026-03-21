"""Benchmark test: per-request connection reuse vs per-query open/close."""

import sqlite3
import time
import pytest
from flask import g
from backend.database.connection import get_connection, execute_query, DB_PATH


NUM_REQUESTS = 100
QUERIES_PER_REQUEST = 5


class TestConnectionBenchmark:
    def test_reuse_faster_than_per_query(self, app):
        """Per-request reuse is at least 2x faster than per-query open/close."""

        # --- Baseline: simulate old per-query open/close behavior ---
        start = time.perf_counter()
        for _ in range(NUM_REQUESTS):
            with app.app_context():
                for _ in range(QUERIES_PER_REQUEST):
                    conn = sqlite3.connect(DB_PATH)
                    conn.row_factory = sqlite3.Row
                    conn.execute("PRAGMA foreign_keys = ON;")
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    conn.close()
        baseline_time = time.perf_counter() - start

        # --- New: per-request reuse via get_connection / g ---
        start = time.perf_counter()
        for _ in range(NUM_REQUESTS):
            with app.app_context():
                for _ in range(QUERIES_PER_REQUEST):
                    execute_query("SELECT 1", fetch_one=True)
        new_time = time.perf_counter() - start

        speedup = baseline_time / new_time
        print(f"\nBaseline: {baseline_time:.3f}s | New: {new_time:.3f}s | Speedup: {speedup:.1f}x")
        assert new_time <= 0.5 * baseline_time, (
            f"Expected >=2x speedup but got {speedup:.2f}x "
            f"(baseline={baseline_time:.3f}s, new={new_time:.3f}s)"
        )
