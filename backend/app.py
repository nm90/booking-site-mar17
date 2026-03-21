"""
Flask application entry point for Vacation Rental Booking System.

MVC Role: Application Bootstrap
- Initializes the Flask web server
- Sets up configuration and CORS
- Handles database initialization on first run
- Registers all controllers (Blueprints)
- Defines basic routes and error handlers
"""

import os
import sys
import sqlite3
import logging
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

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


# ============================================================================
# APPLICATION INITIALIZATION
# ============================================================================
app = Flask(__name__)
csrf = CSRFProtect(app)
logger = setup_logging()

from backend.database.connection import close_connection
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
app.config['DATABASE_PATH'] = os.environ.get(
    'DATABASE_PATH',
    os.path.join(DATABASE_DIR, 'booking_site.db')
)


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
        is_logged_in='user_id' in session
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
def init_database():
    """Initialize the database if it doesn't exist."""
    db_path = app.config['DATABASE_PATH']
    schema_path = os.path.join(DATABASE_DIR, 'schema.sql')

    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    if os.path.exists(db_path):
        print(f"Database found: {db_path}")
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


init_database()


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
