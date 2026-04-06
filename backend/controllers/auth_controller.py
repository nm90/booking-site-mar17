"""
Auth Controller - Handles user registration, login, and logout.

MVC Role: CONTROLLER
- Receives HTTP requests
- Calls User Model methods
- Manages session state
- Returns responses to the client

URL Prefix: /auth
Routes:
    GET  /auth/register  - Show registration form
    POST /auth/register  - Create new user
    GET  /auth/login     - Show login form
    POST /auth/login     - Authenticate user
    POST /auth/logout    - Log out current user
"""

import logging
from flask import Blueprint, request, redirect, url_for, flash, session, render_template
from backend.models.user import User
from backend.services.email import send_password_reset, send_email_verification

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def _sync_session_from_db_user(user: dict) -> None:
    """Refresh cached session fields from the database (role, name, email)."""
    session['user_email'] = user['email']
    session['user_first_name'] = user['first_name']
    session['user_role'] = user['role']


def login_required(f):
    """Decorator: redirect to login if user is not authenticated.

    Re-verifies user existence and active status from the database on every
    request so that suspended or deleted accounts are denied immediately.
    """
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        user = User.get_by_id(session['user_id'])
        if not user or user['status'] != 'active':
            session.clear()
            flash('Your account is no longer active. Please log in again.', 'warning')
            return redirect(url_for('auth.login'))
        _sync_session_from_db_user(user)
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator: redirect to home if user is not an admin.

    Re-verifies user existence, active status, and admin role from the database
    on every request so that revoked privileges take effect immediately.
    """
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        user = User.get_by_id(session['user_id'])
        if not user or user['status'] != 'active':
            session.clear()
            flash('Your account is no longer active. Please log in again.', 'warning')
            return redirect(url_for('auth.login'))
        if user['role'] != 'admin':
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('portal.dashboard'))
        _sync_session_from_db_user(user)
        return f(*args, **kwargs)
    return decorated


# ============================================================================
# REGISTRATION
# ============================================================================
@auth_bp.route('/register', methods=['GET'])
def register():
    """Show the registration form."""
    if 'user_id' in session:
        return redirect(url_for('portal.dashboard'))
    return render_template('users/register.html')


@auth_bp.route('/register', methods=['POST'])
def do_register():
    """Create a new customer account from form data."""
    email = request.form.get('email', '').strip()
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    password = request.form.get('password', '')
    phone_number = request.form.get('phone_number', '').strip() or None

    try:
        user = User.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            phone_number=phone_number,
            role='customer'
        )

        # Send verification email
        token = User.generate_verification_token(user['id'])
        verification_url = url_for('auth.verify_email', token=token, _external=True)
        send_email_verification(email, verification_url)

        flash('Account created! Please check your email to verify your account before logging in.', 'success')
        return redirect(url_for('auth.login'))

    except ValueError as e:
        flash(str(e), 'error')
        return render_template('users/register.html',
                               email=email, first_name=first_name,
                               last_name=last_name, phone_number=phone_number)

    except Exception as e:
        error_message = getattr(e, 'user_message', str(e))
        flash(error_message, 'error')
        return render_template('users/register.html',
                               email=email, first_name=first_name,
                               last_name=last_name, phone_number=phone_number)


# ============================================================================
# LOGIN / LOGOUT
# ============================================================================
@auth_bp.route('/login', methods=['GET'])
def login():
    """Show the login form."""
    if 'user_id' in session:
        if session.get('user_role') == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('portal.dashboard'))
    return render_template('users/login.html')


@auth_bp.route('/login', methods=['POST'])
def do_login():
    """Authenticate user and establish session."""
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')

    if not email or not password:
        flash('Email and password are required.', 'error')
        return render_template('users/login.html', email=email)

    user = User.authenticate(email, password)

    if not user:
        flash('Invalid email or password.', 'error')
        return render_template('users/login.html', email=email)

    if not User.is_email_verified(user['id']):
        session.clear()
        session['pending_verification_email'] = email
        flash('Please verify your email address before logging in. Check your inbox for a verification link.', 'warning')
        return redirect(url_for('auth.login'))

    session.clear()
    session['user_id'] = user['id']
    session['user_email'] = user['email']
    session['user_first_name'] = user['first_name']
    session['user_role'] = user['role']

    flash(f"Welcome back, {user['first_name']}!", 'success')

    if user['role'] == 'admin':
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('portal.dashboard'))


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Clear session and redirect to login."""
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))


# ============================================================================
# EMAIL VERIFICATION
# ============================================================================
@auth_bp.route('/verify-email/<token>', methods=['GET'])
def verify_email(token):
    """Verify a user's email address via token link."""
    user = User.verify_email(token)
    if user:
        session.pop('pending_verification_email', None)
        flash('Email verified successfully! You can now log in.', 'success')
    else:
        flash('This verification link is invalid or has expired.', 'error')
    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend the verification email for an unverified account."""
    email = request.form.get('email', '').strip()
    if not email:
        flash('Email address is required.', 'error')
        return redirect(url_for('auth.login'))

    user = User.get_by_email(email)
    if user and not user.get('email_verified'):
        token = User.generate_verification_token(user['id'])
        verification_url = url_for('auth.verify_email', token=token, _external=True)
        send_email_verification(email, verification_url)

    # Same message whether user exists or not (prevents enumeration)
    flash('If an unverified account exists with that email, a new verification link has been sent.', 'success')
    return redirect(url_for('auth.login'))


# ============================================================================
# PASSWORD RESET
# ============================================================================
@auth_bp.route('/forgot-password', methods=['GET'])
def forgot_password():
    """Show the forgot password form."""
    if 'user_id' in session:
        return redirect(url_for('portal.dashboard'))
    return render_template('users/forgot_password.html')


@auth_bp.route('/forgot-password', methods=['POST'])
def do_forgot_password():
    """Handle forgot password form submission."""
    email = request.form.get('email', '').strip()

    if not email:
        flash('Please enter your email address.', 'error')
        return render_template('users/forgot_password.html')

    token = User.generate_reset_token(email)

    if token:
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        send_password_reset(email, reset_url)
        logging.getLogger(__name__).info("Password reset requested (email redacted; token not logged)")

    # Same message whether email exists or not (prevents enumeration)
    flash('If an account exists with that email, a reset link has been sent.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/reset-password/<token>', methods=['GET'])
def reset_password(token):
    """Show the password reset form."""
    if 'user_id' in session:
        return redirect(url_for('portal.dashboard'))

    user = User.get_by_reset_token(token)
    if not user:
        flash('This reset link is invalid or has expired.', 'error')
        return redirect(url_for('auth.forgot_password'))

    return render_template('users/reset_password.html', token=token)


@auth_bp.route('/reset-password/<token>', methods=['POST'])
def do_reset_password(token):
    """Process the password reset."""
    password = request.form.get('password', '')
    password_confirm = request.form.get('password_confirm', '')

    if password != password_confirm:
        flash('Passwords do not match.', 'error')
        return render_template('users/reset_password.html', token=token)

    try:
        user = User.reset_password(token, password)
        if not user:
            flash('This reset link is invalid or has expired.', 'error')
            return redirect(url_for('auth.forgot_password'))

        flash('Password reset successfully. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    except ValueError as e:
        flash(str(e), 'error')
        return render_template('users/reset_password.html', token=token)
