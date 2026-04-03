"""Bookings table constraints (W6: no default property_id, CHECKs)."""

import sqlite3

import pytest

from backend.database.connection import execute_query


class TestBookingSchemaConstraints:
    def test_property_id_required_at_db_level(self, app):
        with app.app_context():
            execute_query(
                """
                INSERT INTO users (email, password_hash, first_name, last_name, role, status)
                VALUES (?, ?, ?, ?, 'customer', 'active')
                """,
                ("schema-u1@example.com", "h", "A", "B"),
                commit=True,
            )
            with pytest.raises(sqlite3.IntegrityError):
                execute_query(
                    """
                    INSERT INTO bookings (user_id, start_date, end_date, status, total_price, guests)
                    VALUES (1, '2026-08-01', '2026-08-05', 'pending', 100.0, 2)
                    """,
                    commit=True,
                )

    def test_end_date_must_be_after_start_date(self, app):
        with app.app_context():
            execute_query(
                """
                INSERT INTO users (email, password_hash, first_name, last_name, role, status)
                VALUES (?, ?, ?, ?, 'customer', 'active')
                """,
                ("schema-u2@example.com", "h", "C", "D"),
                commit=True,
            )
            execute_query(
                """
                INSERT INTO properties (name, description, location, capacity, price_per_night, status)
                VALUES (?, ?, ?, ?, ?, 'active')
                """,
                ("P1", "d", "L", 4, 50.0),
                commit=True,
            )
            with pytest.raises(sqlite3.IntegrityError):
                execute_query(
                    """
                    INSERT INTO bookings (user_id, property_id, start_date, end_date, status, total_price, guests)
                    VALUES (1, 1, '2026-09-10', '2026-09-05', 'pending', 100.0, 2)
                    """,
                    commit=True,
                )
