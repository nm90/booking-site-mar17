"""
Flask application entry point for Vacation Rental Booking System.

MVC Role: Application Bootstrap
- Initializes the Flask web server
- Sets up configuration
- Handles database initialization on first run
- Registers all controllers (Blueprints)
- Defines basic routes and error handlers
"""

import os
import sys
import sqlite3
import fcntl
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request, session, render_template, redirect, url_for
from flask_wtf.csrf import CSRFProtect

# Add project root to sys.path
if __name__ == '__main__' or __package__ is None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# Import Controllers (Blueprints)
from backend.controllers.auth_controller import auth_bp
from backend.controllers.portal_controller import portal_bp
from backend.controllers.admin_controller import admin_bp


# ============================================================================
# LOGGING SETUP
# ============================================================================
def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'errors.log')

    is_production = os.environ.get('FLASK_ENV', 'development').lower() == 'production'
    file_log_level = logging.WARNING if is_production else logging.DEBUG
    root_log_level = logging.WARNING if is_production else logging.DEBUG
    console_log_level = logging.WARNING if is_production else logging.DEBUG
    max_bytes = 1_048_576  # 1MB
    backup_count = 5

    logger = logging.getLogger()
    logger.setLevel(root_log_level)

    # Keep setup idempotent across reloads/tests.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(file_log_level)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_log_level)
    console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


# ============================================================================
# APPLICATION INITIALIZATION
# ============================================================================
from flask_mail import Mail

app = Flask(__name__)
csrf = CSRFProtect(app)
logger = setup_logging()

# Mail configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@cayegardencasita.com')
app.config['BREVO_API_KEY'] = os.environ.get('BREVO_API_KEY', '').strip()
app.config['BREVO_SENDER_NAME'] = os.environ.get('BREVO_SENDER_NAME', '').strip()
mail = Mail(app)

from backend.database.connection import close_connection, DB_PATH
app.teardown_appcontext(close_connection)

# ============================================================================
# CONFIGURATION
# ============================================================================
_INSECURE_DEFAULTS = {
    'dev-secret-key-change-in-production',
    'change-this-in-production',
    'secret',
    'supersecret',
    '',
}

_secret_key = os.environ.get('SECRET_KEY', '')
if _secret_key in _INSECURE_DEFAULTS:
    print("FATAL: SECRET_KEY is not set or uses a known insecure default value.")
    print("Set a cryptographically random SECRET_KEY environment variable before starting.")
    print("Generate one with:  python3 -c \"import secrets; print(secrets.token_hex(32))\"")
    sys.exit(1)

app.config['SECRET_KEY'] = _secret_key

DATABASE_DIR = os.path.join(os.path.dirname(__file__), 'database')
app.config['DATABASE_PATH'] = DB_PATH

_landing = os.environ.get('LANDING_SITE_URL', 'https://nm90.github.io/booking-site-mar17/').strip()
if not _landing.endswith('/'):
    _landing = _landing + '/'
app.config['LANDING_SITE_URL'] = _landing

_contact_email = os.environ.get('CONTACT_EMAIL', 'hello@cayegardencasita.com').strip()
app.config['CONTACT_EMAIL'] = _contact_email


# ============================================================================
# TEMPLATE CONTEXT PROCESSOR
# ============================================================================
@app.context_processor
def inject_session():
    """Make session data available to all templates."""
    return dict(
        current_user_id=session.get('user_id'),
        current_user_name=session.get('user_first_name'),
        current_user_role=session.get('user_role'),
        is_admin=session.get('user_role') == 'admin',
        is_logged_in='user_id' in session,
        landing_site_url=app.config['LANDING_SITE_URL'],
        contact_email=app.config['CONTACT_EMAIL'],
    )


# ============================================================================
# REGISTER BLUEPRINTS (CONTROLLERS)
# ============================================================================
app.register_blueprint(auth_bp)
app.register_blueprint(portal_bp)
app.register_blueprint(admin_bp)

print("=" * 60)
print("VACATION RENTAL BOOKING SYSTEM - Starting Server")
print("=" * 60)


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================
def _reviews_has_unique_booking_id(conn: sqlite3.Connection) -> bool:
    """True if reviews already enforces at most one row per booking_id."""
    cur = conn.execute("PRAGMA table_info(reviews)")
    if cur.fetchone() is None:
        return True
    for row in conn.execute("PRAGMA index_list('reviews')"):
        if not row[2]:  # not unique
            continue
        name = row[1]
        cols = {
            c[2] for c in conn.execute(f"PRAGMA index_info('{name}')").fetchall()
        }
        if cols == {"booking_id"}:
            return True
    return False


def _migrate_reviews_one_per_booking(conn: sqlite3.Connection) -> None:
    """Dedupe reviews and add UNIQUE(booking_id) for existing databases (W3)."""
    if _reviews_has_unique_booking_id(conn):
        return
    conn.execute(
        """
        DELETE FROM reviews
        WHERE id IN (
            SELECT r.id FROM reviews r
            INNER JOIN reviews r2 ON r.booking_id = r2.booking_id AND r2.id < r.id
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX uq_reviews_booking_id ON reviews(booking_id)"
    )


_BOOKINGS_NEW_DDL = """
CREATE TABLE bookings_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled', 'completed')),
    total_price REAL NOT NULL DEFAULT 0 CHECK (total_price >= 0),
    guests INTEGER NOT NULL DEFAULT 1 CHECK (guests >= 1),
    special_requests TEXT,
    admin_notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_bookings_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_bookings_property
        FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    CHECK (end_date > start_date)
);
"""

_BOOKINGS_COPY_COLS = (
    "id, user_id, property_id, start_date, end_date, status, total_price, guests, "
    "special_requests, admin_notes, created_at, updated_at"
)

_ADV_BOOKINGS_NEW_DDL = """
CREATE TABLE adventure_bookings_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    adventure_id INTEGER NOT NULL,
    booking_id INTEGER,
    scheduled_date DATE NOT NULL,
    participants INTEGER NOT NULL DEFAULT 1 CHECK (participants >= 1),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    special_requests TEXT,
    total_price REAL NOT NULL DEFAULT 0 CHECK (total_price >= 0),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_adv_bookings_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_adv_bookings_adventure
        FOREIGN KEY (adventure_id) REFERENCES adventures(id) ON DELETE CASCADE,
    CONSTRAINT fk_adv_bookings_booking
        FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE SET NULL
);
"""

_ADV_BOOKINGS_COPY_COLS = (
    "id, user_id, adventure_id, booking_id, scheduled_date, participants, status, "
    "special_requests, total_price, created_at, updated_at"
)


def _bookings_table_needs_hardening(sql: str) -> bool:
    """True if bookings should be rebuilt (unsafe default or missing CHECKs)."""
    if not sql:
        return False
    compact = " ".join(sql.split())
    if "property_id INTEGER NOT NULL DEFAULT 1" in compact:
        return True
    markers = ("end_date > start_date", "total_price >= 0", "guests >= 1")
    return any(m not in sql for m in markers)


def _adventure_bookings_table_needs_hardening(sql: str) -> bool:
    if not sql:
        return False
    markers = ("participants >= 1", "total_price >= 0")
    return any(m not in sql for m in markers)


def _replace_bookings_with_hardened_schema(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS bookings_new;")
    conn.execute(_BOOKINGS_NEW_DDL.strip())
    conn.execute(
        f"INSERT INTO bookings_new ({_BOOKINGS_COPY_COLS}) "
        f"SELECT {_BOOKINGS_COPY_COLS} FROM bookings"
    )
    conn.execute("DROP TABLE bookings;")
    conn.execute("ALTER TABLE bookings_new RENAME TO bookings;")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings(user_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bookings_dates ON bookings(start_date, end_date);")


def _replace_adventure_bookings_with_hardened_schema(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS adventure_bookings_new;")
    conn.execute(_ADV_BOOKINGS_NEW_DDL.strip())
    conn.execute(
        f"INSERT INTO adventure_bookings_new ({_ADV_BOOKINGS_COPY_COLS}) "
        f"SELECT {_ADV_BOOKINGS_COPY_COLS} FROM adventure_bookings"
    )
    conn.execute("DROP TABLE adventure_bookings;")
    conn.execute("ALTER TABLE adventure_bookings_new RENAME TO adventure_bookings;")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_adv_bookings_user_id ON adventure_bookings(user_id);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_adv_bookings_adventure_id "
        "ON adventure_bookings(adventure_id);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_adv_bookings_status ON adventure_bookings(status);"
    )


def init_database():
    """Initialize the database if it doesn't exist."""
    db_path = app.config['DATABASE_PATH']
    schema_path = os.path.join(DATABASE_DIR, 'schema.sql')

    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    lock_path = f"{db_path}.init.lock"
    lock_file = open(lock_path, "a+b")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        if os.path.exists(db_path):
            print(f"Database found: {db_path}")
            # Run safe migrations for new columns (use direct connection —
            # execute_query() requires Flask request context which doesn't exist at startup)
            import sqlite3 as _sqlite3
            conn = _sqlite3.connect(db_path)
            for migration in [
                "ALTER TABLE properties ADD COLUMN check_in_instructions TEXT",
                "ALTER TABLE users ADD COLUMN password_reset_token TEXT",
                "ALTER TABLE users ADD COLUMN password_reset_expires DATETIME",
                "ALTER TABLE users ADD COLUMN email_verification_token TEXT",
                "ALTER TABLE users ADD COLUMN email_verification_expires DATETIME",
                "ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1",
            ]:
                try:
                    conn.execute(migration)
                except Exception:
                    pass  # Column already exists
            try:
                _migrate_reviews_one_per_booking(conn)
            except Exception as e:
                print(f"Reviews one-per-booking migration: {e}")
            conn.commit()
            conn.close()

            # Bookings: 'completed' status, no unsafe property_id default, CHECK constraints (W6)
            try:
                conn = _sqlite3.connect(db_path)
                conn.execute("PRAGMA foreign_keys = OFF;")
                cursor = conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='bookings'"
                )
                row = cursor.fetchone()
                create_sql = row[0] if row else ""
                need_completed = "'completed'" not in create_sql
                need_hardening = _bookings_table_needs_hardening(create_sql)
                if need_completed or need_hardening:
                    conn.execute("BEGIN;")
                    _replace_bookings_with_hardened_schema(conn)
                    conn.commit()
                    if need_completed:
                        print("Migrated bookings table to support 'completed' status")
                    if need_hardening:
                        print("Migrated bookings table schema constraints (property_id, CHECKs)")
                conn.execute("PRAGMA foreign_keys = ON;")
                conn.close()
            except Exception as e:
                print(f"Bookings migration check: {e}")

            # Adventure bookings: participant/price CHECKs for existing DBs (W6)
            try:
                conn = _sqlite3.connect(db_path)
                conn.execute("PRAGMA foreign_keys = OFF;")
                cursor = conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='adventure_bookings'"
                )
                row = cursor.fetchone()
                adv_sql = row[0] if row else ""
                if adv_sql and _adventure_bookings_table_needs_hardening(adv_sql):
                    conn.execute("BEGIN;")
                    _replace_adventure_bookings_with_hardened_schema(conn)
                    conn.commit()
                    print("Migrated adventure_bookings CHECK constraints")
                conn.execute("PRAGMA foreign_keys = ON;")
                conn.close()
            except Exception as e:
                print(f"Adventure bookings migration check: {e}")

            return

        print(f"Creating new database: {db_path}")

        try:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys = ON;")

            with open(schema_path, 'r') as f:
                schema_sql = f.read()

            conn.executescript(schema_sql)
            conn.commit()
            conn.close()
            print("Schema created successfully!")

            # Import and run seed data
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from backend.database.seed import insert_seed_data
            insert_seed_data()
            print("Database initialization complete!")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}", exc_info=True)
            print(f"Error initializing database: {e}")
            raise
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


init_database()


# ============================================================================
# AUTO-COMPLETE BOOKINGS
# ============================================================================
from backend.models.booking import Booking

@app.before_request
def auto_complete_bookings():
    # Skip DB work for health checks and static assets (critical-before-request).
    if request.path == '/health' or request.endpoint == 'static':
        return None
    Booking.transition_completed()


# ============================================================================
# ROOT ROUTE
# ============================================================================
@app.route('/')
def index():
    """Redirect root to appropriate page based on login state."""
    if 'user_id' in session:
        if session.get('user_role') == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('portal.dashboard'))
    return redirect(url_for('auth.login'))


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


# ============================================================================
# ERROR HANDLERS
# ============================================================================
@app.errorhandler(404)
def not_found(error):
    logger.warning(f"404: {request.method} {request.path}")
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    logger.exception(f"500: {request.method} {request.path}")
    return render_template('errors/500.html'), 500


@app.errorhandler(403)
def forbidden(error):
    return render_template('errors/403.html'), 403


from flask_wtf.csrf import CSRFError

@app.errorhandler(CSRFError)
def handle_csrf_error(error):
    return render_template('errors/403.html'), 403


# Honor X-Forwarded-* from one reverse proxy (TLS terminators, e.g. Koyeb) when enabled.
if os.environ.get('TRUST_PROXY_HEADERS', '').lower() in ('1', 'true', 'yes'):
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_port=1,
        x_prefix=1,
    )


# ============================================================================
# MAIN EXECUTION
# ============================================================================
if __name__ == '__main__':
    print("\nStarting Flask development server...")
    print("Visit: http://localhost:5000")
    print("\nDefault accounts:")
    print("  Admin:    admin@vacationrental.com / admin123")
    print("  Customer: alice@example.com / pass123")
    print("  Customer: bob@example.com / pass123")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60)
    is_debug = os.environ.get('FLASK_ENV', 'development') != 'production'
    app.run(debug=is_debug, port=5000, host='0.0.0.0')
