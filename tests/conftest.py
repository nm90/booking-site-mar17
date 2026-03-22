"""Shared test fixtures."""

import os
import tempfile
import sqlite3
import pytest


@pytest.fixture()
def app():
    """Create a Flask app with a fresh temporary database for each test."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    os.environ["DATABASE_PATH"] = db_path
    os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"

    # Build schema
    schema_path = os.path.join(
        os.path.dirname(__file__), "..", "backend", "database", "schema.sql"
    )
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

    # Reload connection module so DB_PATH picks up the env var
    import importlib
    import backend.database.connection as conn_mod
    importlib.reload(conn_mod)

    # Now import app (it will use the temp DB)
    from backend.app import app as flask_app
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False

    yield flask_app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture()
def seed_user(app):
    """Insert a test user and property, return user id."""
    import sqlite3
    db_path = os.environ["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        "INSERT INTO users (id, email, password_hash, first_name, last_name, role) "
        "VALUES (1, 'test@example.com', 'hash', 'Test', 'User', 'customer')"
    )
    conn.execute(
        "INSERT INTO users (id, email, password_hash, first_name, last_name, role) "
        "VALUES (2, 'test2@example.com', 'hash', 'Test2', 'User2', 'customer')"
    )
    conn.execute(
        "INSERT INTO properties (id, name, location, capacity, price_per_night) "
        "VALUES (1, 'Test Property', 'Test Location', 10, 100.00)"
    )
    conn.commit()
    conn.close()
    return 1
