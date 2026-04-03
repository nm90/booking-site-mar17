"""Review model: one review per booking (W3)."""

from datetime import date, timedelta

import pytest

from backend.database.connection import execute_query
from backend.models.review import Review


def _create_customer(email: str) -> int:
    return execute_query(
        """
        INSERT INTO users (email, password_hash, first_name, last_name, role, status)
        VALUES (?, ?, ?, ?, 'customer', 'active')
        """,
        (email, "hash", "Guest", "User"),
        commit=True,
    )


def _create_property() -> int:
    return execute_query(
        """
        INSERT INTO properties (name, description, location, capacity, price_per_night, status)
        VALUES (?, ?, ?, ?, ?, 'active')
        """,
        ("Review Test Villa", "x", "Here", 4, 100.0),
        commit=True,
    )


def _create_stay_booking(
    user_id: int, property_id: int, status: str = "completed"
) -> int:
    start = date.today() - timedelta(days=14)
    end = start + timedelta(days=3)
    return execute_query(
        """
        INSERT INTO bookings (user_id, property_id, start_date, end_date, status, total_price, guests)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            property_id,
            start.isoformat(),
            end.isoformat(),
            status,
            300.0,
            2,
        ),
        commit=True,
    )


class TestReviewOnePerBooking:
    def test_second_create_raises_cleanly(self, app):
        with app.app_context():
            uid = _create_customer("reviewer@example.com")
            pid = _create_property()
            bid = _create_stay_booking(uid, pid, status="completed")
            Review.create(
                user_id=uid,
                booking_id=bid,
                rating=5,
                content="Great stay, would book again for sure.",
                title="Loved it",
            )
            with pytest.raises(ValueError, match="already submitted a review"):
                Review.create(
                    user_id=uid,
                    booking_id=bid,
                    rating=4,
                    content="Another review text here minimum ten chars.",
                    title=None,
                )
