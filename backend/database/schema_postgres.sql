-- Vacation Rental Booking System - Postgres Schema (Supabase)
--
-- Port of schema.sql for Postgres. Used when DATABASE_URL is set.
-- Differences from the SQLite schema:
-- - SERIAL primary keys instead of AUTOINCREMENT
-- - TIMESTAMP(0) instead of DATETIME (second precision, so the text form
--   matches SQLite's 'YYYY-MM-DD HH:MM:SS'; connection.py loads dates and
--   timestamps as text), DOUBLE PRECISION instead of REAL (keeps psycopg
--   returning floats — NUMERIC would surface Decimal into float arithmetic)
-- - 0/1 integer flags (email_verified) stay INTEGER so model logic is unchanged
-- - Hardened constraints that app.py migrates into existing SQLite DBs are
--   baked in directly; Postgres databases start fresh and never migrate.

-- ============================================================================
-- USERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_reset_token TEXT,
    password_reset_expires TIMESTAMP(0),
    email_verification_token TEXT,
    email_verification_expires TIMESTAMP(0),
    email_verified INTEGER NOT NULL DEFAULT 0,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    phone_number TEXT,
    role TEXT NOT NULL DEFAULT 'customer'
        CHECK (role IN ('customer', 'admin')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'suspended')),
    created_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT users_email_unique UNIQUE (email)
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ============================================================================
-- PROPERTIES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS properties (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    check_in_instructions TEXT,
    location TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    price_per_night DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'maintenance')),
    created_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- BOOKINGS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled', 'completed')),
    accommodation_subtotal DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (accommodation_subtotal >= 0),
    btb_tax DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (btb_tax >= 0),
    has_pet INTEGER NOT NULL DEFAULT 0 CHECK (has_pet IN (0, 1)),
    pet_fee DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (pet_fee >= 0),
    total_price DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (total_price >= 0),
    guests INTEGER NOT NULL DEFAULT 1 CHECK (guests >= 1),
    special_requests TEXT,
    admin_notes TEXT,
    terms_accepted_at TIMESTAMP(0),
    baha_verified TEXT NOT NULL DEFAULT 'not_applicable'
        CHECK (baha_verified IN ('not_applicable', 'pending', 'verified')),
    created_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_bookings_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_bookings_property
        FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    CHECK (end_date > start_date)
);

CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_dates ON bookings(start_date, end_date);

-- ============================================================================
-- REVIEWS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    booking_id INTEGER NOT NULL,
    rating INTEGER NOT NULL
        CHECK (rating BETWEEN 1 AND 5),
    title TEXT,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reviews_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_reviews_booking
        FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    CONSTRAINT uq_reviews_booking UNIQUE (booking_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_reviews_booking_id ON reviews(booking_id);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status);

-- ============================================================================
-- ADVENTURES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS adventures (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    difficulty TEXT NOT NULL DEFAULT 'easy'
        CHECK (difficulty IN ('easy', 'moderate', 'hard', 'extreme')),
    duration_hours INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    max_participants INTEGER NOT NULL DEFAULT 10,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- ADVENTURE BOOKINGS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS adventure_bookings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    adventure_id INTEGER NOT NULL,
    booking_id INTEGER,
    scheduled_date DATE NOT NULL,
    participants INTEGER NOT NULL DEFAULT 1 CHECK (participants >= 1),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    special_requests TEXT,
    admin_notes TEXT,
    total_price DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (total_price >= 0),
    created_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_adv_bookings_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_adv_bookings_adventure
        FOREIGN KEY (adventure_id) REFERENCES adventures(id) ON DELETE CASCADE,
    CONSTRAINT fk_adv_bookings_booking
        FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_adv_bookings_user_id ON adventure_bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_adv_bookings_adventure_id ON adventure_bookings(adventure_id);
CREATE INDEX IF NOT EXISTS idx_adv_bookings_status ON adventure_bookings(status);
