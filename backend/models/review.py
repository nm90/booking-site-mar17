"""
Review Model - Handles feedback/review data validation and database operations.

MVC Role: MODEL
- Validates review input (rating, content, eligibility)
- Manages database queries for reviews table
- Enforces business rules (only completed stays can be reviewed)
"""

from typing import Dict, List, Optional
from backend.database.connection import execute_query


class Review:
    """
    Review model for managing customer feedback on stays.

    Business Rule: A customer can only review a booking they own
    and only if the stay has been approved/completed.
    """

    VALID_STATUSES = ['pending', 'approved', 'rejected']

    @staticmethod
    def validate(rating: int, content: str) -> None:
        """Validate review data. Raises ValueError if invalid."""
        try:
            rating_int = int(rating)
        except (TypeError, ValueError):
            raise ValueError("Rating must be a number")

        if rating_int < 1 or rating_int > 5:
            raise ValueError("Rating must be between 1 and 5 stars")

        if not content or not content.strip():
            raise ValueError("Review content is required")

        if len(content.strip()) < 10:
            raise ValueError("Review must be at least 10 characters long")

    @staticmethod
    def create(user_id: int, booking_id: int, rating: int,
               content: str, title: str = None) -> Dict:
        """
        Submit a review for a completed stay.

        MVC Flow:
        1. Controller calls Review.create() with form data
        2. Model validates input and checks booking eligibility
        3. Inserts review with 'pending' status for moderation
        4. Returns complete review dict
        """
        Review.validate(rating, content)

        # Check booking exists and belongs to this user
        booking = execute_query(
            "SELECT * FROM bookings WHERE id=? AND user_id=?",
            (booking_id, user_id), fetch_one=True
        )
        if not booking:
            raise ValueError("Booking not found or does not belong to you")

        if booking['status'] not in ['completed']:
            raise ValueError("You can only review completed stays")

        # Check not already reviewed
        existing = execute_query(
            "SELECT id FROM reviews WHERE booking_id=? AND user_id=?",
            (booking_id, user_id), fetch_one=True
        )
        if existing:
            raise ValueError("You have already submitted a review for this booking")

        query = """
            INSERT INTO reviews (user_id, booking_id, rating, title, content, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """
        review_id = execute_query(
            query, (user_id, booking_id, int(rating), title, content.strip()),
            commit=True
        )
        return Review.get_by_id(review_id, include_relations=True)

    @staticmethod
    def get_by_id(review_id: int, include_relations: bool = False) -> Optional[Dict]:
        """Fetch a review by ID, optionally with user details."""
        if not include_relations:
            return execute_query(
                "SELECT * FROM reviews WHERE id=?",
                (review_id,), fetch_one=True
            )

        query = """
            SELECT
                reviews.*,
                users.first_name as user_first_name,
                users.last_name as user_last_name,
                users.email as user_email
            FROM reviews
            INNER JOIN users ON reviews.user_id = users.id
            WHERE reviews.id = ?
        """
        result = execute_query(query, (review_id,), fetch_one=True)
        if not result:
            return None

        return {
            **{k: v for k, v in result.items() if not k.startswith('user_')},
            'user': {
                'first_name': result['user_first_name'],
                'last_name': result['user_last_name'],
                'email': result['user_email'],
            }
        }

    @staticmethod
    def get_all(status: str = None, include_relations: bool = True) -> List[Dict]:
        """Fetch all reviews, optionally filtered by status."""
        if include_relations:
            query = """
                SELECT reviews.*,
                    users.first_name as user_first_name,
                    users.last_name as user_last_name,
                    users.email as user_email
                FROM reviews
                INNER JOIN users ON reviews.user_id = users.id
            """
        else:
            query = "SELECT * FROM reviews"

        params = []
        if status:
            query += " WHERE reviews.status=?" if include_relations else " WHERE status=?"
            params.append(status)

        query += " ORDER BY reviews.created_at DESC" if include_relations else " ORDER BY created_at DESC"

        results = execute_query(query, tuple(params), fetch_all=True)
        if not results:
            return []

        if not include_relations:
            return results

        reviews = []
        for r in results:
            reviews.append({
                **{k: v for k, v in r.items() if not k.startswith('user_')},
                'user': {
                    'first_name': r['user_first_name'],
                    'last_name': r['user_last_name'],
                    'email': r['user_email'],
                }
            })
        return reviews

    @staticmethod
    def get_by_user(user_id: int) -> List[Dict]:
        """Fetch all reviews submitted by a user."""
        result = execute_query(
            "SELECT * FROM reviews WHERE user_id=? ORDER BY created_at DESC",
            (user_id,), fetch_all=True
        )
        return result if result else []

    @staticmethod
    def update_status(review_id: int, status: str) -> Optional[Dict]:
        """Update review moderation status (admin action)."""
        if status not in Review.VALID_STATUSES:
            raise ValueError(f"Status must be one of {Review.VALID_STATUSES}")

        existing = Review.get_by_id(review_id)
        if not existing:
            return None

        execute_query(
            "UPDATE reviews SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, review_id), commit=True
        )
        return Review.get_by_id(review_id, include_relations=True)

    @staticmethod
    def get_approved_reviews() -> List[Dict]:
        """Fetch all publicly visible (approved) reviews."""
        return Review.get_all(status='approved', include_relations=True)
