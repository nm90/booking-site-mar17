"""
Test for US-203: Make availability check + insert atomic.

Demonstrates the race condition where two concurrent booking requests for
the same dates can both pass the availability check before either inserts,
resulting in overlapping bookings.
"""

import os
import sqlite3
import threading
from datetime import date, timedelta

from backend.models.booking import Booking


def test_concurrent_bookings_same_dates_only_one_succeeds(app, seed_user):
    """
    Two threads simultaneously attempt to book the same dates.

    Without atomic check+insert, both threads see the dates as available
    and both inserts succeed — creating overlapping bookings.

    With the fix, only one should succeed; the other should raise ValueError.
    """
    start = (date.today() + timedelta(days=30)).isoformat()
    end = (date.today() + timedelta(days=35)).isoformat()

    results = {"successes": [], "errors": []}
    barrier = threading.Barrier(2, timeout=5)

    def attempt_booking(user_id):
        with app.app_context():
            # Synchronise so both threads hit create() at the same moment
            barrier.wait()
            try:
                booking = Booking.create(
                    user_id=user_id,
                    start_date=start,
                    end_date=end,
                    guests=2,
                )
                results["successes"].append(booking)
            except ValueError as e:
                results["errors"].append(str(e))

    t1 = threading.Thread(target=attempt_booking, args=(1,))
    t2 = threading.Thread(target=attempt_booking, args=(2,))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    # The atomicity requirement: exactly one booking should succeed
    assert len(results["successes"]) == 1, (
        f"Expected exactly 1 successful booking but got {len(results['successes'])}. "
        f"Race condition allowed overlapping bookings! "
        f"Errors: {results['errors']}"
    )
    assert len(results["errors"]) == 1, (
        f"Expected exactly 1 rejected booking but got {len(results['errors'])}. "
        f"Errors: {results['errors']}"
    )
    assert "not available" in results["errors"][0].lower()
