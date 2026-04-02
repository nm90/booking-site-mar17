"""Tests for booking calendar vs availability consistency."""

from datetime import date, timedelta

from backend.database.connection import execute_query
from backend.models.booking import Booking


def _seed_property_and_user():
    execute_query(
        "INSERT INTO users (id, email, password_hash, first_name, last_name, role) "
        "VALUES (1, 'c@example.com', 'h', 'A', 'B', 'customer')",
        commit=True,
    )
    execute_query(
        "INSERT INTO properties (id, name, location, capacity, price_per_night, status) "
        "VALUES (1, 'P', 'L', 4, 100.0, 'active')",
        commit=True,
    )


def test_get_booked_dates_includes_completed_stays(app):
    """Calendar must show the same blocking ranges as check_availability (incl. completed)."""
    with app.app_context():
        _seed_property_and_user()
        start = (date.today() + timedelta(days=40)).isoformat()
        end = (date.today() + timedelta(days=45)).isoformat()
        execute_query(
            """INSERT INTO bookings
               (user_id, property_id, start_date, end_date, status, total_price, guests)
               VALUES (1, 1, ?, ?, 'completed', 100.0, 2)""",
            (start, end),
            commit=True,
        )

        ranges = Booking.get_booked_dates(1)
        assert len(ranges) == 1
        assert ranges[0]["start_date"] == start
        assert ranges[0]["end_date"] == end

        assert Booking.check_availability(start, end, 1) is False
