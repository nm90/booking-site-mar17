"""
Seed data for the Vacation Rental Booking System.
Inserts sample users, properties, bookings, reviews, and adventures.
"""

import sqlite3
import os
import sys
import bcrypt

# Allow standalone execution
if __name__ == '__main__' or __package__ is None:
    _db_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.dirname(os.path.dirname(_db_dir))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

from backend.database.connection import DB_PATH, DATABASE_URL, translate_placeholders


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with cost factor 12."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def _open_seed_connection():
    """Open a standalone connection for seeding (no Flask context at init time)."""
    if DATABASE_URL:
        import psycopg
        return psycopg.connect(DATABASE_URL)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def insert_seed_data():
    raw_conn = _open_seed_connection()

    class _Conn:
        """Translate ?-placeholders so the seed statements work on both engines."""
        def execute(self, sql, params=()):
            if DATABASE_URL:
                return raw_conn.execute(translate_placeholders(sql), params)
            return raw_conn.execute(sql, params)

        def commit(self):
            raw_conn.commit()

        def rollback(self):
            raw_conn.rollback()

        def close(self):
            raw_conn.close()

    conn = _Conn()

    try:
        # Users
        conn.execute("""
            INSERT INTO users (email, password_hash, first_name, last_name, role, email_verified)
            VALUES (?, ?, ?, ?, ?, 1)
        """, ('happy@wiscomfort.com', hash_password('test1234'), 'Admin', 'User', 'admin'))

        conn.execute("""
            INSERT INTO users (email, password_hash, first_name, last_name, phone_number, role, email_verified)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, ('alice@example.com', hash_password('pass123'), 'Alice', 'Johnson', '555-0101', 'customer'))

        conn.execute("""
            INSERT INTO users (email, password_hash, first_name, last_name, phone_number, role, email_verified)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, ('bob@example.com', hash_password('pass123'), 'Bob', 'Smith', '555-0102', 'customer'))

        # Properties
        conn.execute("""
            INSERT INTO properties (name, description, location, capacity, price_per_night)
            VALUES (?, ?, ?, ?, ?)
        """, (
            'Caye Garden Casita',
            'Charming tropical casita in lush gardens — private cottage-style rental in San Pedro Town, Ambergris Caye.',
            'San Pedro Town, Ambergris Caye, Belize',
            4, 200.00
        ))

        # conn.execute("""
        #     INSERT INTO properties (name, description, location, capacity, price_per_night)
        #     VALUES (?, ?, ?, ?, ?)
        # """, (
        #     'Ocean Breeze Cottage',
        #     'A cozy seaside cottage perfect for couples or small families, steps from the beach.',
        #     'Placencia, Belize',
        #     4, 250.00
        # ))
        #
        # conn.execute("""
        #     INSERT INTO properties (name, description, location, capacity, price_per_night)
        #     VALUES (?, ?, ?, ?, ?)
        # """, (
        #     'Mountain Retreat Lodge',
        #     'Spacious lodge nestled in the hills with panoramic views and hiking trails.',
        #     'San Ignacio, Belize',
        #     12, 600.00
        # ))

        # Bookings (gross total = subtotal + 9% BTB tax; $200/night)
        conn.execute("""
            INSERT INTO bookings (
                user_id, property_id, start_date, end_date, status,
                accommodation_subtotal, btb_tax, has_pet, pet_fee, total_price, guests
            )
            VALUES (2, 1, '2026-04-10', '2026-04-15', 'approved', 1000.00, 90.00, 0, 0, 1090.00, 4)
        """)

        conn.execute("""
            INSERT INTO bookings (
                user_id, property_id, start_date, end_date, status,
                accommodation_subtotal, btb_tax, has_pet, pet_fee, total_price,
                guests, special_requests
            )
            VALUES (3, 1, '2026-05-01', '2026-05-07', 'pending', 1200.00, 108.00, 0, 0, 1308.00, 4,
                    'Early check-in if possible')
        """)

        conn.execute("""
            INSERT INTO bookings (
                user_id, property_id, start_date, end_date, status,
                accommodation_subtotal, btb_tax, has_pet, pet_fee, total_price, guests
            )
            VALUES (2, 1, '2026-03-01', '2026-03-05', 'completed', 800.00, 72.00, 0, 0, 872.00, 2)
        """)

        # Review
        conn.execute("""
            INSERT INTO reviews (user_id, booking_id, rating, title, content, status)
            VALUES (2, 3, 5, 'Absolutely amazing stay!',
                'The casita exceeded all expectations — lush garden, quiet neighborhood, and a perfect base for the reef. Will definitely book again!',
                'approved')
        """)

        # Adventures
        # conn.execute("""
        #     INSERT INTO adventures (name, description, category, difficulty, duration_hours, price, max_participants)
        #     VALUES (?, ?, ?, ?, ?, ?, ?)
        # """, ('Sunset Kayaking', 'Paddle along the coastline and watch the sunset from the water.', 'Water Sports', 'easy', 2, 75.00, 8))
        #
        # conn.execute("""
        #     INSERT INTO adventures (name, description, category, difficulty, duration_hours, price, max_participants)
        #     VALUES (?, ?, ?, ?, ?, ?, ?)
        # """, ('Cliff Hiking Trail', 'Explore dramatic coastal cliffs with guided hiking tour.', 'Hiking', 'moderate', 4, 55.00, 12))
        #
        # conn.execute("""
        #     INSERT INTO adventures (name, description, category, difficulty, duration_hours, price, max_participants)
        #     VALUES (?, ?, ?, ?, ?, ?, ?)
        # """, ('Scuba Diving Discovery', 'Discover underwater life with professional PADI instructors.', 'Diving', 'easy', 3, 120.00, 6))
        #
        # conn.execute("""
        #     INSERT INTO adventures (name, description, category, difficulty, duration_hours, price, max_participants)
        #     VALUES (?, ?, ?, ?, ?, ?, ?)
        # """, ('Surf Lessons', 'Learn to surf with experienced local instructors on the best breaks.', 'Water Sports', 'easy', 2, 85.00, 4))
        #
        # # Adventure Booking
        # conn.execute("""
        #     INSERT INTO adventure_bookings (user_id, adventure_id, booking_id, scheduled_date, participants, status, total_price)
        #     VALUES (2, 1, 3, '2026-03-03', 2, 'approved', 150.00)
        # """)

        conn.commit()
        print("Seed data inserted successfully!")

    except Exception as e:
        conn.rollback()
        print(f"Error inserting seed data: {e}")
        raise
    finally:
        conn.close()


seed_database = insert_seed_data

if __name__ == '__main__':
    insert_seed_data()
