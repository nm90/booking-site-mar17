"""Shared fixtures for backend tests."""

import os
import tempfile
import pytest
from backend.app import app as flask_app


@pytest.fixture
def app(tmp_path):
    """Create a Flask app configured for testing with a temp database."""
    db_path = str(tmp_path / "test.db")
    flask_app.config['TESTING'] = True
    os.environ['DATABASE_PATH'] = db_path

    # Initialize schema in test DB
    import sqlite3
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'schema.sql')
    conn = sqlite3.connect(db_path)
    with open(schema_path, 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

    # Update connection module's DB_PATH
    import backend.database.connection as conn_mod
    conn_mod.DB_PATH = db_path

    yield flask_app

    os.environ.pop('DATABASE_PATH', None)


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()
