"""medium-session: regenerate session on login, sync role from DB, block self-suspend."""

import os
import sqlite3

from backend.models.user import User


def test_login_clears_stale_session_keys(app):
    db_path = os.environ["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    pw = User.hash_password("secret12ab")
    conn.execute(
        "INSERT INTO users (email, password_hash, first_name, last_name, role, status) "
        "VALUES ('sync@example.com', ?, 'Sync', 'User', 'customer', 'active')",
        (pw,),
    )
    conn.commit()
    conn.close()

    with app.test_client() as c:
        with c.session_transaction() as s:
            s["attacker_marker"] = "x"
        c.post(
            "/auth/login",
            data={"email": "sync@example.com", "password": "secret12ab"},
            follow_redirects=False,
        )
        with c.session_transaction() as s:
            assert "attacker_marker" not in s
            assert s.get("user_id") is not None


def test_login_required_syncs_role_from_db(app):
    db_path = os.environ["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    pw = User.hash_password("adminpw12")
    conn.execute(
        "INSERT INTO users (email, password_hash, first_name, last_name, role, status) "
        "VALUES ('admin@example.com', ?, 'Ad', 'Min', 'admin', 'active')",
        (pw,),
    )
    conn.commit()
    conn.close()

    with app.test_client() as c:
        with c.session_transaction() as s:
            s["user_id"] = 1
            s["user_email"] = "admin@example.com"
            s["user_first_name"] = "Ad"
            s["user_role"] = "customer"
        c.get("/portal/", follow_redirects=False)
        with c.session_transaction() as s:
            assert s.get("user_role") == "admin"


def test_admin_cannot_suspend_self(app):
    db_path = os.environ["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    pw = User.hash_password("adminpw12")
    conn.execute(
        "INSERT INTO users (email, password_hash, first_name, last_name, role, status) "
        "VALUES ('admin@example.com', ?, 'Ad', 'Min', 'admin', 'active')",
        (pw,),
    )
    conn.commit()
    conn.close()

    with app.test_client() as c:
        c.post(
            "/auth/login",
            data={"email": "admin@example.com", "password": "adminpw12"},
            follow_redirects=False,
        )
        r = c.post(
            "/admin/users/1/status",
            data={"status": "suspended"},
            follow_redirects=False,
        )
        assert r.status_code == 302

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status FROM users WHERE id = 1"
    ).fetchone()
    conn.close()
    assert row[0] == "active"
