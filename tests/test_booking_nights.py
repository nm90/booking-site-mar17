"""Regression tests for computed booking nights."""

import os
import sqlite3

from backend.models.booking import Booking


def _insert_booking_row():
    db_path = os.environ["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        """
        INSERT INTO bookings (
            id, user_id, property_id, start_date, end_date, status, total_price, guests
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (101, 1, 1, "2026-04-01", "2026-04-05", "pending", 400.00, 2),
    )
    conn.commit()
    conn.close()


def test_booking_get_by_user_includes_calculated_nights(app, seed_user):
    _insert_booking_row()

    with app.app_context():
        bookings = Booking.get_by_user(1)

    assert len(bookings) == 1
    assert bookings[0]["start_date"] == "2026-04-01"
    assert bookings[0]["end_date"] == "2026-04-05"
    assert bookings[0]["nights"] == 4


def test_booking_get_all_includes_calculated_nights(app, seed_user):
    _insert_booking_row()

    with app.app_context():
        bookings = Booking.get_all()

    assert len(bookings) == 1
    assert bookings[0]["nights"] == 4


def test_booking_get_by_id_includes_calculated_nights(app, seed_user):
    _insert_booking_row()

    with app.app_context():
        booking = Booking.get_by_id(101)

    assert booking is not None
    assert booking["nights"] == 4
