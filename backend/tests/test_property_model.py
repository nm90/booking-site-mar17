"""Tests for Property model (admin delete policy)."""

from datetime import date, timedelta

import pytest

from backend.database.connection import execute_query
from backend.models.property import Property


def _insert_user(user_id: int, email: str) -> None:
    execute_query(
        "INSERT INTO users (id, email, password_hash, first_name, last_name, role) "
        "VALUES (?, ?, 'h', 'F', 'L', 'customer')",
        (user_id, email),
        commit=True,
    )


def _insert_property(property_id: int = 1) -> None:
    execute_query(
        "INSERT INTO properties (id, name, location, capacity, price_per_night, status) "
        "VALUES (?, 'P', 'L', 4, 100.0, 'active')",
        (property_id,),
        commit=True,
    )


def _insert_booking(property_id: int, status: str) -> None:
    start = (date.today() + timedelta(days=60)).isoformat()
    end = (date.today() + timedelta(days=63)).isoformat()
    execute_query(
        """INSERT INTO bookings
           (user_id, property_id, start_date, end_date, status, total_price, guests)
           VALUES (1, ?, ?, ?, ?, 300.0, 2)""",
        (property_id, start, end, status),
        commit=True,
    )


def test_delete_property_with_completed_booking_raises(app):
    with app.app_context():
        _insert_user(1, "a@example.com")
        _insert_property(1)
        _insert_booking(1, "completed")

        with pytest.raises(ValueError, match="booking history"):
            Property.delete(1)


def test_delete_property_with_no_bookings_succeeds(app):
    with app.app_context():
        _insert_user(1, "b@example.com")
        _insert_property(1)

        assert Property.delete(1) is True
        assert Property.get_by_id(1) is None
