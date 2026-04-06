"""
User Model - Handles user data validation and database operations.

MVC Role: MODEL
- Validates user input
- Manages database queries for users table
- Contains business logic for user operations
- Returns data structures (dicts) to controllers
"""

import re
import hashlib
import secrets
import bcrypt
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from backend.database.connection import execute_query


class User:
    """
    User model for managing user data and operations.

    Demonstrates the MODEL layer in MVC:
    - Data validation
    - Database operations (CRUD)
    - Business logic (authentication, roles)
    """

    EMAIL_PATTERN = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    VALID_ROLES = ['customer', 'admin']
    VALID_STATUSES = ['active', 'inactive', 'suspended']

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt with cost factor 12."""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

    @staticmethod
    def _is_sha256_hash(password_hash: str) -> bool:
        """Return True if the stored hash looks like a raw SHA-256 hex digest."""
        return len(password_hash) == 64 and all(c in '0123456789abcdef' for c in password_hash)

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        """Verify a plaintext password against a stored hash (bcrypt or legacy SHA-256)."""
        if User._is_sha256_hash(password_hash):
            return hashlib.sha256(password.encode()).hexdigest() == password_hash
        return bcrypt.checkpw(password.encode(), password_hash.encode())

    @staticmethod
    def validate(email: str, first_name: str, last_name: str,
                 password: str = None, role: str = 'customer') -> None:
        """
        Validate user data before database operations.

        Raises ValueError with descriptive message if validation fails.
        """
        if not first_name or not first_name.strip():
            raise ValueError("First name is required")

        if not last_name or not last_name.strip():
            raise ValueError("Last name is required")

        if not email or not email.strip():
            raise ValueError("Email is required")

        if not re.match(User.EMAIL_PATTERN, email):
            raise ValueError(f"Invalid email format: {email}")

        if password is not None and len(password) < 6:
            raise ValueError("Password must be at least 6 characters")

        if role not in User.VALID_ROLES:
            raise ValueError(f"Role must be one of {User.VALID_ROLES}")

    @staticmethod
    def create(email: str, first_name: str, last_name: str,
               password: str, phone_number: str = None, role: str = 'customer') -> Dict:
        """
        Create a new user in the database.

        MVC Flow:
        1. Controller calls User.create() with form data
        2. Model validates and inserts into database
        3. Returns complete user dict
        """
        User.validate(email, first_name, last_name, password, role)

        password_hash = User.hash_password(password)
        query = """
            INSERT INTO users (email, password_hash, first_name, last_name, phone_number, role)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        user_id = execute_query(
            query,
            (email, password_hash, first_name, last_name, phone_number, role),
            commit=True
        )
        return User.get_by_id(user_id)

    @staticmethod
    def get_by_id(user_id: int) -> Optional[Dict]:
        """Fetch a user by their ID. Returns None if not found."""
        return execute_query(
            "SELECT id, email, first_name, last_name, phone_number, role, status, email_verified, created_at FROM users WHERE id = ?",
            (user_id,), fetch_one=True
        )

    @staticmethod
    def get_by_email(email: str) -> Optional[Dict]:
        """Fetch a user by email (includes password_hash for auth)."""
        return execute_query(
            "SELECT * FROM users WHERE email = ?",
            (email,), fetch_one=True
        )

    @staticmethod
    def get_all() -> List[Dict]:
        """Fetch all users ordered by creation date."""
        result = execute_query(
            "SELECT id, email, first_name, last_name, phone_number, role, status, created_at FROM users ORDER BY created_at DESC",
            fetch_all=True
        )
        return result if result else []

    @staticmethod
    def authenticate(email: str, password: str) -> Optional[Dict]:
        """
        Authenticate a user with email and password.

        Legacy SHA-256 hashes are transparently migrated to bcrypt on first
        successful login so that all active accounts eventually use bcrypt.

        Returns user dict if credentials are valid, None otherwise.
        """
        user = User.get_by_email(email)
        if not user:
            return None

        if not User._verify_password(password, user['password_hash']):
            return None

        if user['status'] != 'active':
            return None

        # Migrate legacy SHA-256 hash to bcrypt on successful login
        if User._is_sha256_hash(user['password_hash']):
            new_hash = User.hash_password(password)
            execute_query(
                "UPDATE users SET password_hash=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (new_hash, user['id']),
                commit=True
            )

        # Return safe user dict (without password_hash)
        return User.get_by_id(user['id'])

    @staticmethod
    def update(user_id: int, first_name: str, last_name: str,
               email: str, phone_number: str = None) -> Optional[Dict]:
        """Update an existing user's profile information."""
        existing = User.get_by_id(user_id)
        if not existing:
            return None

        first_name = (first_name or '').strip()
        last_name = (last_name or '').strip()
        email = (email or '').strip()

        if phone_number is None:
            phone_number = existing.get('phone_number')
        else:
            phone_number = phone_number.strip() or None

        User.validate(email, first_name, last_name)

        execute_query(
            "UPDATE users SET first_name=?, last_name=?, email=?, phone_number=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (first_name, last_name, email, phone_number, user_id),
            commit=True
        )
        return User.get_by_id(user_id)

    @staticmethod
    def update_status(user_id: int, status: str) -> Optional[Dict]:
        """Update a user's account status (admin action)."""
        if status not in User.VALID_STATUSES:
            raise ValueError(f"Status must be one of {User.VALID_STATUSES}")

        existing = User.get_by_id(user_id)
        if not existing:
            return None

        execute_query(
            "UPDATE users SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, user_id), commit=True
        )
        return User.get_by_id(user_id)

    @staticmethod
    def generate_reset_token(email: str) -> Optional[str]:
        """Generate a password reset token for the given email.

        Returns the token if user exists, None otherwise.
        Does not reveal whether the email exists (caller handles messaging).
        """
        user = User.get_by_email(email)
        if not user or user['status'] != 'active':
            return None

        token = secrets.token_urlsafe(32)
        expires = (datetime.utcnow() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')

        execute_query(
            "UPDATE users SET password_reset_token=?, password_reset_expires=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (token, expires, user['id']),
            commit=True
        )
        return token

    @staticmethod
    def get_by_reset_token(token: str) -> Optional[Dict]:
        """Fetch a user by valid (non-expired) reset token."""
        if not token:
            return None
        return execute_query(
            """SELECT id, email, first_name, last_name, role, status
               FROM users
               WHERE password_reset_token = ?
                 AND password_reset_expires > CURRENT_TIMESTAMP
                 AND status = 'active'""",
            (token,), fetch_one=True
        )

    @staticmethod
    def reset_password(token: str, new_password: str) -> Optional[Dict]:
        """Reset password using a valid token. Returns user dict or None."""
        if not new_password or len(new_password) < 6:
            raise ValueError("Password must be at least 6 characters")

        user = User.get_by_reset_token(token)
        if not user:
            return None

        password_hash = User.hash_password(new_password)
        execute_query(
            """UPDATE users
               SET password_hash=?, password_reset_token=NULL, password_reset_expires=NULL,
                   updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (password_hash, user['id']),
            commit=True
        )
        return User.get_by_id(user['id'])

    @staticmethod
    def generate_verification_token(user_id: int) -> str:
        """Generate an email verification token for the given user.

        Returns the token string. Expires in 24 hours.
        """
        token = secrets.token_urlsafe(32)
        expires = (datetime.utcnow() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')

        execute_query(
            "UPDATE users SET email_verification_token=?, email_verification_expires=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (token, expires, user_id),
            commit=True
        )
        return token

    @staticmethod
    def verify_email(token: str) -> Optional[Dict]:
        """Verify a user's email using a valid (non-expired) token.

        Sets email_verified=1, clears token columns. Returns user dict or None.
        """
        if not token:
            return None

        user = execute_query(
            """SELECT id FROM users
               WHERE email_verification_token = ?
                 AND email_verification_expires > CURRENT_TIMESTAMP""",
            (token,), fetch_one=True
        )
        if not user:
            return None

        execute_query(
            """UPDATE users
               SET email_verified = 1, email_verification_token = NULL,
                   email_verification_expires = NULL, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (user['id'],),
            commit=True
        )
        return User.get_by_id(user['id'])

    @staticmethod
    def is_email_verified(user_id: int) -> bool:
        """Check whether a user's email is verified."""
        user = execute_query(
            "SELECT email_verified FROM users WHERE id = ?",
            (user_id,), fetch_one=True
        )
        if not user:
            return False
        return bool(user.get('email_verified', 1))

    @staticmethod
    def update_password(user_id: int, current_password: str, new_password: str) -> Optional[Dict]:
        """Change a user's password after verifying their current password.

        Raises ValueError if current password is wrong or new password is invalid.
        Returns updated user dict.
        """
        user = execute_query("SELECT * FROM users WHERE id = ?", (user_id,), fetch_one=True)
        if not user:
            return None

        if not User._verify_password(current_password, user['password_hash']):
            raise ValueError("Current password is incorrect")

        if not new_password or len(new_password) < 6:
            raise ValueError("New password must be at least 6 characters")

        password_hash = User.hash_password(new_password)
        execute_query(
            "UPDATE users SET password_hash=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (password_hash, user_id),
            commit=True
        )
        return User.get_by_id(user_id)

    @staticmethod
    def delete(user_id: int) -> bool:
        """Delete a user. Returns True if deleted, False if not found."""
        existing = User.get_by_id(user_id)
        if not existing:
            return False

        execute_query("DELETE FROM users WHERE id=?", (user_id,), commit=True)
        return True
