"""Model tests for admin adventure CRUD behavior."""

import pytest
from datetime import date, timedelta

from backend.database.connection import execute_query
from backend.models.adventure import Adventure, AdventureBooking


class TestAdventureModel:
    def test_create_update_and_deactivate(self, app):
        with app.app_context():
            created = Adventure.create(
                name="Mangrove Kayak Tour",
                description="Paddle through mangrove tunnels.",
                category="Water Sports",
                difficulty="easy",
                duration_hours=3,
                price=99.5,
                max_participants=8,
            )

            assert created["name"] == "Mangrove Kayak Tour"
            assert created["status"] == "active"

            updated = Adventure.update(
                adventure_id=created["id"],
                name="Mangrove Kayak Expedition",
                description="Longer route with wildlife stops.",
                category="Water Sports",
                difficulty="moderate",
                duration_hours=4,
                price=129.0,
                max_participants=10,
                status="active",
            )

            assert updated["name"] == "Mangrove Kayak Expedition"
            assert updated["difficulty"] == "moderate"
            assert updated["duration_hours"] == 4
            assert updated["price"] == 129.0
            assert updated["max_participants"] == 10

            deactivated = Adventure.deactivate(created["id"])
            assert deactivated["status"] == "inactive"

    @pytest.mark.parametrize(
        "payload, expected_error",
        [
            (
                {
                    "name": "  ",
                    "description": "x",
                    "category": "Water Sports",
                    "difficulty": "easy",
                    "duration_hours": 2,
                    "price": 50,
                    "max_participants": 5,
                },
                "Adventure name is required",
            ),
            (
                {
                    "name": "Cave Dive",
                    "description": "x",
                    "category": "Diving",
                    "difficulty": "insane",
                    "duration_hours": 2,
                    "price": 50,
                    "max_participants": 5,
                },
                "Difficulty must be one of",
            ),
            (
                {
                    "name": "Cave Dive",
                    "description": "x",
                    "category": "Diving",
                    "difficulty": "hard",
                    "duration_hours": 0,
                    "price": 50,
                    "max_participants": 5,
                },
                "Duration must be at least 1 hour",
            ),
            (
                {
                    "name": "Cave Dive",
                    "description": "x",
                    "category": "Diving",
                    "difficulty": "hard",
                    "duration_hours": 2,
                    "price": -1,
                    "max_participants": 5,
                },
                "Price must be greater than 0",
            ),
            (
                {
                    "name": "Cave Dive",
                    "description": "x",
                    "category": "Diving",
                    "difficulty": "hard",
                    "duration_hours": 2,
                    "price": 50,
                    "max_participants": 0,
                },
                "Max participants must be at least 1",
            ),
        ],
    )
    def test_create_validation_errors(self, app, payload, expected_error):
        with app.app_context():
            with pytest.raises(ValueError, match=expected_error):
                Adventure.create(**payload)


def _create_customer(email: str, first_name: str = "Guest") -> int:
    return execute_query(
        """
        INSERT INTO users (email, password_hash, first_name, last_name, role, status)
        VALUES (?, ?, ?, ?, 'customer', 'active')
        """,
        (email, "hash", first_name, "User"),
        commit=True,
    )


def _create_property() -> int:
    return execute_query(
        """
        INSERT INTO properties (name, description, location, capacity, price_per_night, status)
        VALUES (?, ?, ?, ?, ?, 'active')
        """,
        ("Villa Test", "Test property", "Beach", 4, 220.0),
        commit=True,
    )


def _create_stay_booking(
    user_id: int, property_id: int, start_date: date, end_date: date, status: str = "approved"
) -> int:
    return execute_query(
        """
        INSERT INTO bookings (user_id, property_id, start_date, end_date, status, total_price, guests)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, property_id, start_date.isoformat(), end_date.isoformat(), status, 600.0, 2),
        commit=True,
    )


class TestAdventureBookingLinkedStayValidation:
    def test_create_with_linked_stay_date_inside_window_succeeds(self, app):
        with app.app_context():
            user_id = _create_customer("alice-linked@test.local", first_name="Alice")
            property_id = _create_property()
            adventure = Adventure.create(
                name="Sunset Paddle",
                description="Lagoon paddle tour",
                category="Water Sports",
                difficulty="easy",
                duration_hours=2,
                price=80.0,
                max_participants=8,
            )
            start_date = date.today() + timedelta(days=10)
            end_date = start_date + timedelta(days=4)
            booking_id = _create_stay_booking(user_id, property_id, start_date, end_date, status="approved")

            scheduled_date = (start_date + timedelta(days=1)).isoformat()
            created = AdventureBooking.create(
                user_id=user_id,
                adventure_id=adventure["id"],
                scheduled_date=scheduled_date,
                participants=2,
                booking_id=booking_id,
                special_requests="Need life jackets",
            )

            assert created["booking_id"] == booking_id
            assert created["scheduled_date"] == scheduled_date

    def test_create_with_linked_stay_date_before_start_raises_error(self, app):
        with app.app_context():
            user_id = _create_customer("before-start@test.local")
            property_id = _create_property()
            adventure = Adventure.create(
                name="Trail Ride",
                description="Forest trail horse ride",
                category="Nature",
                difficulty="moderate",
                duration_hours=3,
                price=120.0,
                max_participants=6,
            )
            start_date = date.today() + timedelta(days=12)
            end_date = start_date + timedelta(days=3)
            booking_id = _create_stay_booking(user_id, property_id, start_date, end_date, status="approved")

            with pytest.raises(ValueError, match="Adventure date must be within your linked stay dates"):
                AdventureBooking.create(
                    user_id=user_id,
                    adventure_id=adventure["id"],
                    scheduled_date=(start_date - timedelta(days=1)).isoformat(),
                    participants=2,
                    booking_id=booking_id,
                )

    def test_create_with_linked_stay_date_on_or_after_checkout_raises_error(self, app):
        with app.app_context():
            user_id = _create_customer("checkout-edge@test.local")
            property_id = _create_property()
            adventure = Adventure.create(
                name="Cliff Walk",
                description="Guided coastal hike",
                category="Hiking",
                difficulty="hard",
                duration_hours=5,
                price=140.0,
                max_participants=10,
            )
            start_date = date.today() + timedelta(days=15)
            end_date = start_date + timedelta(days=5)
            booking_id = _create_stay_booking(user_id, property_id, start_date, end_date, status="approved")

            with pytest.raises(ValueError, match="Adventure date must be within your linked stay dates"):
                AdventureBooking.create(
                    user_id=user_id,
                    adventure_id=adventure["id"],
                    scheduled_date=end_date.isoformat(),
                    participants=2,
                    booking_id=booking_id,
                )

            with pytest.raises(ValueError, match="Adventure date must be within your linked stay dates"):
                AdventureBooking.create(
                    user_id=user_id,
                    adventure_id=adventure["id"],
                    scheduled_date=(end_date + timedelta(days=1)).isoformat(),
                    participants=2,
                    booking_id=booking_id,
                )

    def test_create_with_linked_stay_owned_by_other_user_raises_error(self, app):
        with app.app_context():
            owner_id = _create_customer("stay-owner@test.local", first_name="Owner")
            attacker_id = _create_customer("other-user@test.local", first_name="Other")
            property_id = _create_property()
            adventure = Adventure.create(
                name="Kayak Sprint",
                description="Fast kayak route",
                category="Water Sports",
                difficulty="moderate",
                duration_hours=2,
                price=95.0,
                max_participants=8,
            )
            start_date = date.today() + timedelta(days=9)
            end_date = start_date + timedelta(days=4)
            booking_id = _create_stay_booking(owner_id, property_id, start_date, end_date, status="approved")

            with pytest.raises(ValueError, match="You can only link your own stay bookings"):
                AdventureBooking.create(
                    user_id=attacker_id,
                    adventure_id=adventure["id"],
                    scheduled_date=(start_date + timedelta(days=1)).isoformat(),
                    participants=1,
                    booking_id=booking_id,
                )

    def test_create_with_unapproved_linked_stay_raises_error(self, app):
        with app.app_context():
            user_id = _create_customer("pending-stay@test.local")
            property_id = _create_property()
            adventure = Adventure.create(
                name="Island Trek",
                description="Island trail adventure",
                category="Hiking",
                difficulty="easy",
                duration_hours=4,
                price=110.0,
                max_participants=12,
            )
            start_date = date.today() + timedelta(days=11)
            end_date = start_date + timedelta(days=3)
            booking_id = _create_stay_booking(user_id, property_id, start_date, end_date, status="pending")

            with pytest.raises(ValueError, match="Only approved stays can be linked to an adventure booking"):
                AdventureBooking.create(
                    user_id=user_id,
                    adventure_id=adventure["id"],
                    scheduled_date=(start_date + timedelta(days=1)).isoformat(),
                    participants=2,
                    booking_id=booking_id,
                )


class TestAdventureInactivePolicy:
    def test_create_rejects_inactive_adventure(self, app):
        with app.app_context():
            user_id = _create_customer("inactive-adv-create@test.local")
            adv = Adventure.create(
                name="Sunset Sail",
                description="Evening cruise",
                category="Water Sports",
                difficulty="easy",
                duration_hours=2,
                price=75.0,
                max_participants=20,
            )
            Adventure.deactivate(adv["id"])
            sched = (date.today() + timedelta(days=20)).isoformat()
            with pytest.raises(ValueError, match="not available for booking"):
                AdventureBooking.create(
                    user_id=user_id,
                    adventure_id=adv["id"],
                    scheduled_date=sched,
                    participants=2,
                )

    def test_approve_rejects_when_adventure_inactive(self, app):
        with app.app_context():
            user_id = _create_customer("inactive-adv-approve@test.local")
            adv = Adventure.create(
                name="Morning Hike",
                description="Ridge walk",
                category="Hiking",
                difficulty="moderate",
                duration_hours=3,
                price=40.0,
                max_participants=15,
            )
            sched = (date.today() + timedelta(days=21)).isoformat()
            pending = AdventureBooking.create(
                user_id=user_id,
                adventure_id=adv["id"],
                scheduled_date=sched,
                participants=1,
            )
            Adventure.deactivate(adv["id"])
            with pytest.raises(ValueError, match="not active"):
                AdventureBooking.update_status(pending["id"], "approved")


class TestAdventureDateCapacity:
    def test_create_rejects_when_date_already_at_capacity(self, app):
        with app.app_context():
            u1 = _create_customer("cap-a@test.local")
            u2 = _create_customer("cap-b@test.local")
            adv = Adventure.create(
                name="Group Snorkel",
                description="Reef tour",
                category="Water Sports",
                difficulty="easy",
                duration_hours=2,
                price=60.0,
                max_participants=8,
            )
            sched = (date.today() + timedelta(days=30)).isoformat()
            AdventureBooking.create(
                user_id=u1, adventure_id=adv["id"], scheduled_date=sched, participants=5
            )
            with pytest.raises(ValueError, match="capacity for this date"):
                AdventureBooking.create(
                    user_id=u2, adventure_id=adv["id"], scheduled_date=sched, participants=5
                )

    def test_second_pending_cannot_be_approved_over_capacity(self, app):
        """Two overlapping pendings that exceed max (e.g. legacy rows): only one can be approved."""
        with app.app_context():
            u1 = _create_customer("cap-c@test.local")
            u2 = _create_customer("cap-d@test.local")
            adv = Adventure.create(
                name="Zip Line",
                description="Canopy run",
                category="Adventure",
                difficulty="moderate",
                duration_hours=2,
                price=120.0,
                max_participants=10,
            )
            sched = (date.today() + timedelta(days=31)).isoformat()
            aid1 = execute_query(
                """
                INSERT INTO adventure_bookings
                    (user_id, adventure_id, scheduled_date, participants, status, total_price)
                VALUES (?, ?, ?, 6, 'pending', 1.0)
                """,
                (u1, adv["id"], sched),
                commit=True,
            )
            aid2 = execute_query(
                """
                INSERT INTO adventure_bookings
                    (user_id, adventure_id, scheduled_date, participants, status, total_price)
                VALUES (?, ?, ?, 6, 'pending', 1.0)
                """,
                (u2, adv["id"], sched),
                commit=True,
            )
            AdventureBooking.update_status(aid1, "approved")
            with pytest.raises(ValueError, match="would be exceeded"):
                AdventureBooking.update_status(aid2, "approved")
