"""
Booking Model - Handles booking data validation and database operations.

MVC Role: MODEL
- Validates booking input (dates, guests, availability)
- Manages database queries for bookings table
- Contains business logic for booking lifecycle
- Returns data structures (dicts) to controllers
"""

from typing import Dict, List, Optional
from datetime import date, datetime
from backend.database.connection import execute_query


class Booking:
    """
    Booking model for managing stay reservations.

    Lifecycle: pending → approved / rejected
                        → cancelled (by customer or admin)
    """

    VALID_STATUSES = ['pending', 'approved', 'rejected', 'cancelled']

    ALLOWED_TRANSITIONS = {
        'pending': ['approved', 'rejected'],
        'approved': ['cancelled'],
        'rejected': [],
        'cancelled': [],
    }

    @staticmethod
    def validate(start_date: str, end_date: str, guests: int) -> None:
        """
        Validate booking data.

        Raises ValueError with descriptive message if validation fails.
        """
        if not start_date:
            raise ValueError("Start date is required")

        if not end_date:
            raise ValueError("End date is required")

        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError:
            raise ValueError("Dates must be in YYYY-MM-DD format")

        if start >= end:
            raise ValueError("Check-out date must be after check-in date")

        if start < date.today():
            raise ValueError("Check-in date cannot be in the past")

        try:
            guests_int = int(guests)
        except (TypeError, ValueError):
            raise ValueError("Number of guests must be a whole number")

        if guests_int < 1:
            raise ValueError("At least 1 guest is required")

        if guests_int > 20:
            raise ValueError("Maximum 20 guests allowed per booking")

    @staticmethod
    def calculate_price(start_date: str, end_date: str, price_per_night: float = 450.00) -> float:
        """Calculate total price for a stay."""
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        nights = (end - start).days
        return round(nights * price_per_night, 2)

    @staticmethod
    def check_availability(start_date: str, end_date: str, exclude_booking_id: int = None) -> bool:
        """
        Check if the property is available for the requested dates.

        Returns True if available, False if dates overlap with an existing booking.
        """
        query = """
            SELECT id FROM bookings
            WHERE status IN ('pending', 'approved')
            AND start_date < ?
            AND end_date > ?
        """
        params = [end_date, start_date]

        if exclude_booking_id:
            query += " AND id != ?"
            params.append(exclude_booking_id)

        result = execute_query(query, tuple(params), fetch_all=True)
        return len(result) == 0

    @staticmethod
    def create(user_id: int, start_date: str, end_date: str,
               guests: int, special_requests: str = None) -> Dict:
        """
        Create a new booking request.

        MVC Flow:
        1. Controller calls Booking.create() with form data
        2. Model validates dates, checks availability, calculates price
        3. Inserts booking with 'pending' status
        4. Returns complete booking dict
        """
        Booking.validate(start_date, end_date, guests)

        if not Booking.check_availability(start_date, end_date):
            raise ValueError("The property is not available for the selected dates")

        total_price = Booking.calculate_price(start_date, end_date)

        query = """
            INSERT INTO bookings (user_id, property_id, start_date, end_date, status, total_price, guests, special_requests)
            VALUES (?, 1, ?, ?, 'pending', ?, ?, ?)
        """
        booking_id = execute_query(
            query,
            (user_id, start_date, end_date, total_price, int(guests), special_requests),
            commit=True
        )
        return Booking.get_by_id(booking_id, include_relations=True)

    @staticmethod
    def get_by_id(booking_id: int, include_relations: bool = False) -> Optional[Dict]:
        """Fetch a booking by its ID, optionally with user details."""
        if not include_relations:
            return execute_query(
                "SELECT * FROM bookings WHERE id=?",
                (booking_id,), fetch_one=True
            )

        query = """
            SELECT
                bookings.*,
                users.first_name as user_first_name,
                users.last_name as user_last_name,
                users.email as user_email,
                users.phone_number as user_phone
            FROM bookings
            INNER JOIN users ON bookings.user_id = users.id
            WHERE bookings.id = ?
        """
        result = execute_query(query, (booking_id,), fetch_one=True)
        if not result:
            return None

        return {
            **{k: v for k, v in result.items() if not k.startswith('user_')},
            'user': {
                'first_name': result['user_first_name'],
                'last_name': result['user_last_name'],
                'email': result['user_email'],
                'phone_number': result['user_phone'],
            }
        }

    @staticmethod
    def get_all(status: str = None, include_relations: bool = True) -> List[Dict]:
        """Fetch all bookings, optionally filtered by status."""
        if include_relations:
            query = """
                SELECT
                    bookings.*,
                    users.first_name as user_first_name,
                    users.last_name as user_last_name,
                    users.email as user_email,
                    users.phone_number as user_phone
                FROM bookings
                INNER JOIN users ON bookings.user_id = users.id
            """
        else:
            query = "SELECT * FROM bookings"

        params = []
        if status:
            query += " WHERE bookings.status = ?" if include_relations else " WHERE status = ?"
            params.append(status)

        query += " ORDER BY bookings.created_at DESC" if include_relations else " ORDER BY created_at DESC"

        results = execute_query(query, tuple(params), fetch_all=True)
        if not results:
            return []

        if not include_relations:
            return results

        bookings = []
        for r in results:
            bookings.append({
                **{k: v for k, v in r.items() if not k.startswith('user_')},
                'user': {
                    'first_name': r['user_first_name'],
                    'last_name': r['user_last_name'],
                    'email': r['user_email'],
                    'phone_number': r['user_phone'],
                }
            })
        return bookings

    @staticmethod
    def get_by_user(user_id: int) -> List[Dict]:
        """Fetch all bookings for a specific user."""
        query = """
            SELECT bookings.* FROM bookings
            WHERE user_id = ?
            ORDER BY created_at DESC
        """
        result = execute_query(query, (user_id,), fetch_all=True)
        return result if result else []

    @staticmethod
    def update_status(booking_id: int, status: str, admin_notes: str = None) -> Optional[Dict]:
        """
        Update booking status (admin action: approve/reject).

        Returns updated booking dict or None if not found.
        """
        if status not in Booking.VALID_STATUSES:
            raise ValueError(f"Status must be one of {Booking.VALID_STATUSES}")

        existing = Booking.get_by_id(booking_id)
        if not existing:
            return None

        current_status = existing['status']
        allowed = Booking.ALLOWED_TRANSITIONS.get(current_status, [])
        if status not in allowed:
            raise ValueError(
                f"Cannot transition from '{current_status}' to '{status}'"
            )

        execute_query(
            "UPDATE bookings SET status=?, admin_notes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, admin_notes, booking_id), commit=True
        )
        return Booking.get_by_id(booking_id, include_relations=True)

    @staticmethod
    def cancel(booking_id: int, user_id: int) -> Optional[Dict]:
        """
        Cancel a booking (customer action).

        Only the booking owner can cancel, and only pending/approved bookings.
        """
        booking = Booking.get_by_id(booking_id)
        if not booking:
            return None

        if booking['user_id'] != user_id:
            raise ValueError("You can only cancel your own bookings")

        if booking['status'] not in ['pending', 'approved']:
            raise ValueError(f"Cannot cancel a booking with status '{booking['status']}'")

        execute_query(
            "UPDATE bookings SET status='cancelled', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (booking_id,), commit=True
        )
        return Booking.get_by_id(booking_id)
