"""
Booking Model - Handles booking data validation and database operations.

MVC Role: MODEL
- Validates booking input (dates, guests, availability)
- Manages database queries for bookings table
- Contains business logic for booking lifecycle
- Returns data structures (dicts) to controllers
"""

from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
from backend.database.connection import execute_query, begin_immediate
from backend.models.property import Property


class Booking:
    """
    Booking model for managing stay reservations.

    Lifecycle: pending → approved / rejected
                        → completed (auto, after checkout)
                        → cancelled (by customer or admin, before completion)
    """

    VALID_STATUSES = ['pending', 'approved', 'rejected', 'cancelled', 'completed']

    ALLOWED_TRANSITIONS = {
        'pending': ['approved', 'rejected'],
        'approved': ['cancelled', 'completed'],
        'rejected': [],
        'cancelled': [],
        'completed': [],
    }

    @staticmethod
    def validate(start_date: str, end_date: str, guests: int, max_capacity: int = None) -> None:
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

        if max_capacity and guests_int > max_capacity:
            raise ValueError(f"Maximum {max_capacity} guests allowed for this property")

    @staticmethod
    def calculate_price(start_date: str, end_date: str, price_per_night: float) -> float:
        """Calculate total price for a stay."""
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        nights = (end - start).days
        return round(nights * price_per_night, 2)

    @staticmethod
    def check_availability(start_date: str, end_date: str, property_id: int,
                           exclude_booking_id: int = None) -> bool:
        """
        Check if a property is available for the requested dates.

        Returns True if available, False if dates overlap with an existing booking.
        """
        query = """
            SELECT id FROM bookings
            WHERE status IN ('pending', 'approved', 'completed')
            AND property_id = ?
            AND start_date < ?
            AND end_date > ?
        """
        params = [property_id, end_date, start_date]

        if exclude_booking_id:
            query += " AND id != ?"
            params.append(exclude_booking_id)

        result = execute_query(query, tuple(params), fetch_all=True)
        return len(result) == 0

    @staticmethod
    def get_booked_dates(property_id: int) -> List[Dict]:
        """Return all booked date ranges for a property (next 12 months).

        Returns list of dicts with start_date and end_date strings.
        Only includes bookings that block availability (pending, approved).
        """
        today = str(date.today())
        future = str(date.today() + timedelta(days=365))

        results = execute_query(
            """SELECT start_date, end_date FROM bookings
               WHERE property_id = ?
                 AND status IN ('pending', 'approved')
                 AND end_date > ?
                 AND start_date < ?
               ORDER BY start_date""",
            (property_id, today, future),
            fetch_all=True
        )
        return [{'start_date': r['start_date'], 'end_date': r['end_date']} for r in results] if results else []

    @staticmethod
    def create(user_id: int, start_date: str, end_date: str,
               guests: int, property_id: int, special_requests: str = None) -> Dict:
        """
        Create a new booking request.

        MVC Flow:
        1. Controller calls Booking.create() with form data
        2. Model validates dates, checks availability, calculates price
        3. Inserts booking with 'pending' status
        4. Returns complete booking dict
        """
        prop = Property.get_by_id(property_id)
        if not prop:
            raise ValueError("Property not found")
        if prop['status'] != 'active':
            raise ValueError("This property is not currently available for booking")

        Booking.validate(start_date, end_date, guests, max_capacity=prop['capacity'])
        total_price = Booking.calculate_price(start_date, end_date, prop['price_per_night'])

        with begin_immediate():
            if not Booking.check_availability(start_date, end_date, property_id):
                raise ValueError("The property is not available for the selected dates")

            query = """
                INSERT INTO bookings (user_id, property_id, start_date, end_date, status, total_price, guests, special_requests)
                VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
            """
            booking_id = execute_query(
                query,
                (user_id, property_id, start_date, end_date, total_price, int(guests), special_requests),
                commit=True
            )

        return Booking.get_by_id(booking_id, include_relations=True)

    @staticmethod
    def _build_booking_dict(row: Dict) -> Dict:
        """Build a booking dict with nested user and property from a joined row."""
        booking = {k: v for k, v in row.items()
                   if k == 'user_id' or (not k.startswith('user_') and not k.startswith('property_'))}
        try:
            start = date.fromisoformat(booking['start_date'])
            end = date.fromisoformat(booking['end_date'])
            booking['nights'] = (end - start).days
        except (KeyError, TypeError, ValueError):
            booking['nights'] = None
        if 'user_first_name' in row:
            booking['user'] = {
                'first_name': row['user_first_name'],
                'last_name': row['user_last_name'],
                'email': row['user_email'],
                'phone_number': row['user_phone'],
            }
        if 'property_name' in row:
            booking['property'] = {
                'name': row['property_name'],
                'location': row['property_location'],
                'check_in_instructions': row.get('property_check_in_instructions'),
            }
        return booking

    @staticmethod
    def get_by_id(booking_id: int, include_relations: bool = False) -> Optional[Dict]:
        """Fetch a booking by its ID, optionally with user and property details."""
        if not include_relations:
            result = execute_query(
                """SELECT bookings.*, properties.name as property_name,
                          properties.location as property_location,
                          properties.check_in_instructions as property_check_in_instructions
                   FROM bookings
                   LEFT JOIN properties ON bookings.property_id = properties.id
                   WHERE bookings.id = ?""",
                (booking_id,), fetch_one=True
            )
            if not result:
                return None
            return Booking._build_booking_dict(result)

        query = """
            SELECT
                bookings.*,
                users.first_name as user_first_name,
                users.last_name as user_last_name,
                users.email as user_email,
                users.phone_number as user_phone,
                properties.name as property_name,
                properties.location as property_location,
                properties.check_in_instructions as property_check_in_instructions
            FROM bookings
            INNER JOIN users ON bookings.user_id = users.id
            LEFT JOIN properties ON bookings.property_id = properties.id
            WHERE bookings.id = ?
        """
        result = execute_query(query, (booking_id,), fetch_one=True)
        if not result:
            return None

        return Booking._build_booking_dict(result)

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
                    users.phone_number as user_phone,
                    properties.name as property_name,
                    properties.location as property_location,
                    properties.check_in_instructions as property_check_in_instructions
                FROM bookings
                INNER JOIN users ON bookings.user_id = users.id
                LEFT JOIN properties ON bookings.property_id = properties.id
            """
        else:
            query = """
                SELECT bookings.*, properties.name as property_name,
                       properties.location as property_location,
                       properties.check_in_instructions as property_check_in_instructions
                FROM bookings
                LEFT JOIN properties ON bookings.property_id = properties.id
            """

        params = []
        if status:
            query += " WHERE bookings.status = ?"
            params.append(status)

        query += " ORDER BY bookings.created_at DESC"

        results = execute_query(query, tuple(params), fetch_all=True)
        if not results:
            return []

        return [Booking._build_booking_dict(r) for r in results]

    @staticmethod
    def get_by_user(user_id: int) -> List[Dict]:
        """Fetch all bookings for a specific user."""
        query = """
            SELECT bookings.*, properties.name as property_name,
                   properties.location as property_location,
                   properties.check_in_instructions as property_check_in_instructions
            FROM bookings
            LEFT JOIN properties ON bookings.property_id = properties.id
            WHERE bookings.user_id = ?
            ORDER BY bookings.created_at DESC
        """
        results = execute_query(query, (user_id,), fetch_all=True)
        if not results:
            return []
        return [Booking._build_booking_dict(r) for r in results]

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
    def transition_completed():
        """Auto-transition approved bookings past checkout to 'completed'."""
        execute_query(
            """UPDATE bookings SET status='completed', updated_at=CURRENT_TIMESTAMP
               WHERE status='approved' AND end_date <= date('now')""",
            commit=True
        )

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
