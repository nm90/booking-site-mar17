"""Model tests for admin adventure CRUD behavior."""

import pytest

from backend.models.adventure import Adventure


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
