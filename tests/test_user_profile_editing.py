"""Integration tests for profile editing in the portal."""

import os
import sqlite3


def _set_logged_in_session(client, user_id=1, email='test@example.com', first_name='Test', role='customer'):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['user_email'] = email
        sess['user_first_name'] = first_name
        sess['user_role'] = role


def _get_user_row(user_id):
    db_path = os.environ["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, email, first_name, last_name, phone_number FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def test_profile_page_requires_authentication(app, seed_user):
    client = app.test_client()

    response = client.get('/portal/profile', follow_redirects=False)

    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']


def test_authenticated_user_can_view_profile_page(app, seed_user):
    client = app.test_client()
    _set_logged_in_session(client)

    response = client.get('/portal/profile')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'My Profile' in body
    assert 'value="Test"' in body
    assert 'value="User"' in body
    assert 'value="test@example.com"' in body


def test_profile_update_persists_and_refreshes_session_values(app, seed_user):
    client = app.test_client()
    _set_logged_in_session(client)

    db_path = os.environ["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET phone_number = ? WHERE id = ?", ("555-1111", 1))
    conn.commit()
    conn.close()

    response = client.post(
        '/portal/profile',
        data={
            'first_name': 'Updated',
            'last_name': 'Person',
            'email': 'updated@example.com',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert 'Profile updated successfully.' in response.get_data(as_text=True)

    updated = _get_user_row(1)
    assert updated is not None
    assert updated['first_name'] == 'Updated'
    assert updated['last_name'] == 'Person'
    assert updated['email'] == 'updated@example.com'
    assert updated['phone_number'] == '555-1111'

    with client.session_transaction() as sess:
        assert sess['user_first_name'] == 'Updated'
        assert sess['user_email'] == 'updated@example.com'


def test_profile_update_rejects_invalid_email(app, seed_user):
    client = app.test_client()
    _set_logged_in_session(client)

    response = client.post(
        '/portal/profile',
        data={
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'not-an-email',
        },
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Invalid email format: not-an-email' in body

    user = _get_user_row(1)
    assert user['email'] == 'test@example.com'


def test_profile_update_rejects_duplicate_email(app, seed_user):
    client = app.test_client()
    _set_logged_in_session(client)

    response = client.post(
        '/portal/profile',
        data={
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test2@example.com',
        },
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'An account with this email already exists' in body

    user = _get_user_row(1)
    assert user['email'] == 'test@example.com'
