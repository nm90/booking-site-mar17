"""Integration tests for account deactivation."""

import os
import sqlite3

import pytest


TEST_PASSWORD = 'testpass123'


@pytest.fixture()
def user_with_password(app):
    """Insert a test user with a bcrypt-hashed password, a property, and return user id."""
    from backend.models.user import User

    password_hash = User.hash_password(TEST_PASSWORD)

    db_path = os.environ["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        "INSERT INTO users (id, email, password_hash, first_name, last_name, role, email_verified) "
        "VALUES (1, 'test@example.com', ?, 'Test', 'User', 'customer', 1)",
        (password_hash,),
    )
    conn.execute(
        "INSERT INTO properties (id, name, location, capacity, price_per_night) "
        "VALUES (1, 'Test Property', 'Test Location', 10, 100.00)"
    )
    conn.commit()
    conn.close()
    return 1


def _login_session(client, user_id=1):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['user_email'] = 'test@example.com'
        sess['user_first_name'] = 'Test'
        sess['user_role'] = 'customer'


def _get_user_status(user_id):
    db_path = os.environ["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row['status'] if row else None


def _get_booking_status(booking_id):
    db_path = os.environ["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    conn.close()
    return row['status'] if row else None


def _get_adventure_booking_status(booking_id):
    db_path = os.environ["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status FROM adventure_bookings WHERE id = ?", (booking_id,)).fetchone()
    conn.close()
    return row['status'] if row else None


def _insert_booking(user_id, status='pending'):
    db_path = os.environ["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.execute(
        "INSERT INTO bookings (user_id, property_id, start_date, end_date, guests, total_price, status) "
        "VALUES (?, 1, '2026-06-01', '2026-06-05', 2, 400.00, ?)",
        (user_id, status),
    )
    booking_id = cur.lastrowid
    conn.commit()
    conn.close()
    return booking_id


def _insert_adventure_booking(user_id, status='pending'):
    db_path = os.environ["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    # Ensure an adventure exists
    conn.execute(
        "INSERT OR IGNORE INTO adventures (id, name, description, category, difficulty, duration_hours, price, max_participants, status) "
        "VALUES (1, 'Test Adventure', 'Desc', 'hiking', 'easy', 2, 50.00, 10, 'active')"
    )
    cur = conn.execute(
        "INSERT INTO adventure_bookings (user_id, adventure_id, scheduled_date, participants, total_price, status) "
        "VALUES (?, 1, '2026-06-01', 2, 100.00, ?)",
        (user_id, status),
    )
    booking_id = cur.lastrowid
    conn.commit()
    conn.close()
    return booking_id


# ---------- Authentication ----------

def test_deactivate_requires_authentication(app, user_with_password):
    client = app.test_client()
    response = client.post('/portal/deactivate-account', follow_redirects=False)
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']


# ---------- Password validation ----------

def test_deactivate_requires_password(app, user_with_password):
    client = app.test_client()
    _login_session(client)

    response = client.post('/portal/deactivate-account', data={'password': ''}, follow_redirects=True)
    body = response.get_data(as_text=True)
    assert 'Password is required' in body
    assert _get_user_status(1) == 'active'


def test_deactivate_wrong_password_rejected(app, user_with_password):
    client = app.test_client()
    _login_session(client)

    response = client.post('/portal/deactivate-account', data={'password': 'wrongpass'}, follow_redirects=True)
    body = response.get_data(as_text=True)
    assert 'Password is incorrect' in body
    assert _get_user_status(1) == 'active'


# ---------- Successful deactivation ----------

def test_deactivate_sets_user_inactive(app, user_with_password):
    client = app.test_client()
    _login_session(client)

    response = client.post(
        '/portal/deactivate-account',
        data={'password': TEST_PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']
    assert _get_user_status(1) == 'inactive'


def test_deactivate_clears_session(app, user_with_password):
    client = app.test_client()
    _login_session(client)

    client.post('/portal/deactivate-account', data={'password': TEST_PASSWORD})

    with client.session_transaction() as sess:
        assert 'user_id' not in sess


# ---------- Booking cancellation ----------

def test_deactivate_cancels_pending_bookings(app, user_with_password):
    client = app.test_client()
    _login_session(client)
    bid = _insert_booking(1, 'pending')

    client.post('/portal/deactivate-account', data={'password': TEST_PASSWORD})
    assert _get_booking_status(bid) == 'cancelled'


def test_deactivate_cancels_approved_bookings(app, user_with_password):
    client = app.test_client()
    _login_session(client)
    bid = _insert_booking(1, 'approved')

    client.post('/portal/deactivate-account', data={'password': TEST_PASSWORD})
    assert _get_booking_status(bid) == 'cancelled'


def test_deactivate_leaves_completed_bookings_untouched(app, user_with_password):
    client = app.test_client()
    _login_session(client)
    bid = _insert_booking(1, 'completed')

    client.post('/portal/deactivate-account', data={'password': TEST_PASSWORD})
    assert _get_booking_status(bid) == 'completed'


def test_deactivate_cancels_adventure_bookings(app, user_with_password):
    client = app.test_client()
    _login_session(client)
    abid = _insert_adventure_booking(1, 'pending')

    client.post('/portal/deactivate-account', data={'password': TEST_PASSWORD})
    assert _get_adventure_booking_status(abid) == 'cancelled'


# ---------- Edge cases ----------

def test_deactivated_user_cannot_login(app, user_with_password):
    from backend.models.user import User

    client = app.test_client()
    _login_session(client)
    client.post('/portal/deactivate-account', data={'password': TEST_PASSWORD})

    with app.app_context():
        result = User.authenticate('test@example.com', TEST_PASSWORD)
        assert result is None
