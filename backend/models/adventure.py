"""
Adventure Model - Handles adventure activity catalog and booking operations.

MVC Role: MODEL
- Validates adventure and booking input
- Manages adventure catalog and bookings
- Contains business logic for adventure reservations
"""

from typing import Dict, List, Optional
from datetime import date
from backend.database.connection import execute_query


class Adventure:
    """
    Adventure model for managing activity catalog and booking requests.
    """

    VALID_DIFFICULTIES = ['easy', 'moderate', 'hard', 'extreme']

    @staticmethod
    def get_all(active_only: bool = True) -> List[Dict]:
        """Fetch all adventures, optionally only active ones."""
        if active_only:
            result = execute_query(
                "SELECT * FROM adventures WHERE status='active' ORDER BY category, name",
                fetch_all=True
            )
        else:
            result = execute_query(
                "SELECT * FROM adventures ORDER BY category, name",
                fetch_all=True
            )
        return result if result else []

    @staticmethod
    def get_by_id(adventure_id: int) -> Optional[Dict]:
        """Fetch an adventure by ID."""
        return execute_query(
            "SELECT * FROM adventures WHERE id=?",
            (adventure_id,), fetch_one=True
        )

    @staticmethod
    def create(name: str, description: str, category: str, difficulty: str,
               duration_hours: int, price: float, max_participants: int = 10) -> Dict:
        """Create a new adventure activity (admin action)."""
        if not name or not name.strip():
            raise ValueError("Adventure name is required")

        if difficulty not in Adventure.VALID_DIFFICULTIES:
            raise ValueError(f"Difficulty must be one of {Adventure.VALID_DIFFICULTIES}")

        try:
            price_float = float(price)
        except (TypeError, ValueError):
            raise ValueError("Price must be a number")

        if price_float <= 0:
            raise ValueError("Price must be greater than 0")

        query = """
            INSERT INTO adventures (name, description, category, difficulty, duration_hours, price, max_participants)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        adventure_id = execute_query(
            query,
            (name.strip(), description, category, difficulty, int(duration_hours), price_float, int(max_participants)),
            commit=True
        )
        return Adventure.get_by_id(adventure_id)


class AdventureBooking:
    """
    AdventureBooking model for managing adventure reservation requests.
    """

    VALID_STATUSES = ['pending', 'approved', 'rejected', 'cancelled']

    @staticmethod
    def validate(adventure_id: int, scheduled_date: str, participants: int) -> None:
        """Validate adventure booking. Raises ValueError if invalid."""
        if not scheduled_date:
            raise ValueError("Scheduled date is required")

        try:
            sched = date.fromisoformat(scheduled_date)
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")

        if sched < date.today():
            raise ValueError("Scheduled date cannot be in the past")

        try:
            p_int = int(participants)
        except (TypeError, ValueError):
            raise ValueError("Participants must be a whole number")

        if p_int < 1:
            raise ValueError("At least 1 participant is required")

        adventure = Adventure.get_by_id(adventure_id)
        if not adventure:
            raise ValueError("Adventure not found")

        if p_int > adventure['max_participants']:
            raise ValueError(f"Maximum {adventure['max_participants']} participants for this activity")

    @staticmethod
    def create(user_id: int, adventure_id: int, scheduled_date: str,
               participants: int, booking_id: int = None,
               special_requests: str = None) -> Dict:
        """
        Submit an adventure booking request.

        MVC Flow:
        1. Controller calls AdventureBooking.create() with form data
        2. Model validates and calculates total price
        3. Inserts with 'pending' status
        4. Returns complete booking dict
        """
        AdventureBooking.validate(adventure_id, scheduled_date, participants)

        adventure = Adventure.get_by_id(adventure_id)
        total_price = round(adventure['price'] * int(participants), 2)

        query = """
            INSERT INTO adventure_bookings
                (user_id, adventure_id, booking_id, scheduled_date, participants, status, total_price, special_requests)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """
        ab_id = execute_query(
            query,
            (user_id, adventure_id, booking_id, scheduled_date, int(participants), total_price, special_requests),
            commit=True
        )
        return AdventureBooking.get_by_id(ab_id, include_relations=True)

    @staticmethod
    def get_by_id(ab_id: int, include_relations: bool = False) -> Optional[Dict]:
        """Fetch an adventure booking by ID."""
        if not include_relations:
            return execute_query(
                "SELECT * FROM adventure_bookings WHERE id=?",
                (ab_id,), fetch_one=True
            )

        query = """
            SELECT
                adventure_bookings.*,
                adventures.name as adventure_name,
                adventures.category as adventure_category,
                adventures.difficulty as adventure_difficulty,
                users.first_name as user_first_name,
                users.last_name as user_last_name,
                users.email as user_email
            FROM adventure_bookings
            INNER JOIN adventures ON adventure_bookings.adventure_id = adventures.id
            INNER JOIN users ON adventure_bookings.user_id = users.id
            WHERE adventure_bookings.id = ?
        """
        result = execute_query(query, (ab_id,), fetch_one=True)
        if not result:
            return None

        return {
            **{k: v for k, v in result.items() if not k.startswith('adventure_') and not k.startswith('user_')},
            'adventure': {
                'name': result['adventure_name'],
                'category': result['adventure_category'],
                'difficulty': result['adventure_difficulty'],
            },
            'user': {
                'first_name': result['user_first_name'],
                'last_name': result['user_last_name'],
                'email': result['user_email'],
            }
        }

    @staticmethod
    def get_by_user(user_id: int) -> List[Dict]:
        """Fetch all adventure bookings for a user with adventure details."""
        query = """
            SELECT
                adventure_bookings.*,
                adventures.name as adventure_name,
                adventures.category as adventure_category,
                adventures.difficulty as adventure_difficulty
            FROM adventure_bookings
            INNER JOIN adventures ON adventure_bookings.adventure_id = adventures.id
            WHERE adventure_bookings.user_id = ?
            ORDER BY adventure_bookings.created_at DESC
        """
        results = execute_query(query, (user_id,), fetch_all=True)
        if not results:
            return []

        bookings = []
        for r in results:
            bookings.append({
                **{k: v for k, v in r.items() if not k.startswith('adventure_')},
                'adventure': {
                    'name': r['adventure_name'],
                    'category': r['adventure_category'],
                    'difficulty': r['adventure_difficulty'],
                }
            })
        return bookings

    @staticmethod
    def get_all(status: str = None) -> List[Dict]:
        """Fetch all adventure bookings (admin view)."""
        query = """
            SELECT
                adventure_bookings.*,
                adventures.name as adventure_name,
                users.first_name as user_first_name,
                users.last_name as user_last_name,
                users.email as user_email
            FROM adventure_bookings
            INNER JOIN adventures ON adventure_bookings.adventure_id = adventures.id
            INNER JOIN users ON adventure_bookings.user_id = users.id
        """
        params = []
        if status:
            query += " WHERE adventure_bookings.status=?"
            params.append(status)

        query += " ORDER BY adventure_bookings.created_at DESC"
        results = execute_query(query, tuple(params), fetch_all=True)
        if not results:
            return []

        bookings = []
        for r in results:
            bookings.append({
                **{k: v for k, v in r.items() if not k.startswith('adventure_') and not k.startswith('user_')},
                'adventure': {'name': r['adventure_name']},
                'user': {
                    'first_name': r['user_first_name'],
                    'last_name': r['user_last_name'],
                    'email': r['user_email'],
                }
            })
        return bookings

    @staticmethod
    def update_status(ab_id: int, status: str) -> Optional[Dict]:
        """Update adventure booking status (admin action)."""
        if status not in AdventureBooking.VALID_STATUSES:
            raise ValueError(f"Status must be one of {AdventureBooking.VALID_STATUSES}")

        existing = AdventureBooking.get_by_id(ab_id)
        if not existing:
            return None

        execute_query(
            "UPDATE adventure_bookings SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, ab_id), commit=True
        )
        return AdventureBooking.get_by_id(ab_id, include_relations=True)
