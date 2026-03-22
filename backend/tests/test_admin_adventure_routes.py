"""Route tests for admin adventure CRUD and moderation endpoints."""

from backend.database.connection import execute_query
from backend.models.adventure import Adventure, AdventureBooking


def _create_admin_user():
    return execute_query(
        """
        INSERT INTO users (email, password_hash, first_name, last_name, role, status)
        VALUES (?, ?, ?, ?, 'admin', 'active')
        """,
        ("admin@test.local", "hash", "Admin", "Tester"),
        commit=True,
    )


def _create_customer_user():
    return execute_query(
        """
        INSERT INTO users (email, password_hash, first_name, last_name, role, status)
        VALUES (?, ?, ?, ?, 'customer', 'active')
        """,
        ("guest@test.local", "hash", "Guest", "User"),
        commit=True,
    )


def _login_as_admin(client, admin_id):
    with client.session_transaction() as session:
        session["user_id"] = admin_id
        session["user_role"] = "admin"
        session["user_first_name"] = "Admin"


class TestAdminAdventureRoutes:
    def test_admin_required_for_adventure_catalog(self, client):
        response = client.get("/admin/adventures")
        assert response.status_code == 302
        assert "/auth/login" in response.location

    def test_admin_can_create_update_and_deactivate_adventure(self, app, client):
        app.config["WTF_CSRF_ENABLED"] = False
        with app.app_context():
            admin_id = _create_admin_user()

        _login_as_admin(client, admin_id)

        create_response = client.post(
            "/admin/adventures",
            data={
                "name": "Reef Snorkeling",
                "description": "Coral reef experience",
                "category": "Diving",
                "difficulty": "easy",
                "duration_hours": "2",
                "price": "85.00",
                "max_participants": "6",
            },
            follow_redirects=True,
        )
        assert create_response.status_code == 200
        assert b"created successfully" in create_response.data

        with app.app_context():
            created = Adventure.get_all(active_only=False)[0]
            adventure_id = created["id"]

        update_response = client.post(
            f"/admin/adventures/{adventure_id}",
            data={
                "name": "Reef Snorkeling Plus",
                "description": "Extended reef route",
                "category": "Diving",
                "difficulty": "moderate",
                "duration_hours": "3",
                "price": "120.00",
                "max_participants": "8",
                "status": "active",
            },
            follow_redirects=True,
        )
        assert update_response.status_code == 200
        assert b"updated successfully" in update_response.data

        deactivate_response = client.post(
            f"/admin/adventures/{adventure_id}/deactivate",
            follow_redirects=True,
        )
        assert deactivate_response.status_code == 200
        assert b"deactivated" in deactivate_response.data

        with app.app_context():
            updated = Adventure.get_by_id(adventure_id)
            assert updated["name"] == "Reef Snorkeling Plus"
            assert updated["status"] == "inactive"

    def test_create_validation_error_re_renders_form(self, app, client):
        app.config["WTF_CSRF_ENABLED"] = False
        with app.app_context():
            admin_id = _create_admin_user()

        _login_as_admin(client, admin_id)

        response = client.post(
            "/admin/adventures",
            data={
                "name": "Zipline",
                "description": "Forest zipline",
                "category": "Nature",
                "difficulty": "easy",
                "duration_hours": "2",
                "price": "-10",
                "max_participants": "10",
            },
        )
        assert response.status_code == 200
        assert b"Price must be greater than 0" in response.data

    def test_adventure_booking_moderation_still_works(self, app, client):
        app.config["WTF_CSRF_ENABLED"] = False
        with app.app_context():
            admin_id = _create_admin_user()
            customer_id = _create_customer_user()
            adventure_id = execute_query(
                """
                INSERT INTO adventures (name, description, category, difficulty, duration_hours, price, max_participants, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                ("Jungle Hike", "Rainforest trek", "Hiking", "moderate", 4, 75.0, 10),
                commit=True,
            )
            booking_id = execute_query(
                """
                INSERT INTO adventure_bookings (user_id, adventure_id, scheduled_date, participants, status, total_price)
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (customer_id, adventure_id, "2099-01-01", 2, 150.0),
                commit=True,
            )

        _login_as_admin(client, admin_id)

        index_response = client.get("/admin/adventure-bookings")
        assert index_response.status_code == 200
        assert b"Adventure Bookings" in index_response.data

        approve_response = client.post(
            f"/admin/adventure-bookings/{booking_id}/approve",
            follow_redirects=True,
        )
        assert approve_response.status_code == 200
        assert b"approved" in approve_response.data

        with app.app_context():
            booking = AdventureBooking.get_by_id(booking_id)
            assert booking["status"] == "approved"
