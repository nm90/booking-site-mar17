"""Tests for booking fee calculation and rental-agreement fields."""

from datetime import date, timedelta

import pytest

from backend.database.connection import execute_query
from backend.models.booking import Booking


def _seed_property_and_user():
    execute_query(
        "INSERT INTO users (id, email, password_hash, first_name, last_name, role) "
        "VALUES (1, 'fees@example.com', 'h', 'A', 'B', 'customer')",
        commit=True,
    )
    execute_query(
        "INSERT INTO properties (id, name, location, capacity, price_per_night, status) "
        "VALUES (1, 'P', 'L', 4, 100.0, 'active')",
        commit=True,
    )


class TestCalculateFees:
    def test_calculate_fees_no_pet(self, app):
        with app.app_context():
            fees = Booking.calculate_fees(
                '2026-08-01', '2026-08-06', 100.0,
                has_pet=False, btb_rate=0.09, pet_fee_flat=75.0,
            )
            assert fees['accommodation_subtotal'] == 500.0
            assert fees['btb_tax'] == 45.0
            assert fees['pet_fee'] == 0.0
            assert fees['has_pet'] is False
            assert fees['total_price'] == 545.0

    def test_calculate_fees_with_pet(self, app):
        with app.app_context():
            fees = Booking.calculate_fees(
                '2026-08-01', '2026-08-06', 100.0,
                has_pet=True, btb_rate=0.09, pet_fee_flat=75.0,
            )
            assert fees['accommodation_subtotal'] == 500.0
            assert fees['btb_tax'] == 45.0
            assert fees['pet_fee'] == 75.0
            assert fees['has_pet'] is True
            assert fees['total_price'] == 620.0

    def test_calculate_fees_uses_app_config_defaults(self, app):
        with app.app_context():
            old_btb = app.config.get('BTB_TAX_RATE')
            old_pet = app.config.get('PET_SANITATION_FEE')
            try:
                app.config['BTB_TAX_RATE'] = 0.10
                app.config['PET_SANITATION_FEE'] = 50.0
                fees = Booking.calculate_fees(
                    '2026-08-01', '2026-08-04', 200.0, has_pet=True,
                )
                assert fees['accommodation_subtotal'] == 600.0
                assert fees['btb_tax'] == 60.0
                assert fees['pet_fee'] == 50.0
                assert fees['total_price'] == 710.0
            finally:
                if old_btb is not None:
                    app.config['BTB_TAX_RATE'] = old_btb
                if old_pet is not None:
                    app.config['PET_SANITATION_FEE'] = old_pet


class TestBookingCreateFees:
    def test_create_requires_terms(self, app):
        with app.app_context():
            _seed_property_and_user()
            start = (date.today() + timedelta(days=60)).isoformat()
            end = (date.today() + timedelta(days=65)).isoformat()
            with pytest.raises(ValueError, match="Vacation Rental Agreement"):
                Booking.create(
                    user_id=1, start_date=start, end_date=end,
                    guests=2, property_id=1, terms_accepted=False,
                )

    def test_create_persists_fee_breakdown(self, app):
        with app.app_context():
            _seed_property_and_user()
            start = (date.today() + timedelta(days=70)).isoformat()
            end = (date.today() + timedelta(days=75)).isoformat()
            booking = Booking.create(
                user_id=1, start_date=start, end_date=end,
                guests=2, property_id=1, has_pet=False,
                terms_accepted=True,
            )
            assert booking['accommodation_subtotal'] == 500.0
            assert booking['btb_tax'] == 45.0
            assert booking['pet_fee'] == 0.0
            assert booking['total_price'] == 545.0
            assert booking['has_pet'] is False
            assert booking['baha_verified'] == 'not_applicable'
            assert booking['terms_accepted_at'] is not None

    def test_create_sets_baha_pending_when_pet(self, app):
        with app.app_context():
            _seed_property_and_user()
            start = (date.today() + timedelta(days=80)).isoformat()
            end = (date.today() + timedelta(days=85)).isoformat()
            booking = Booking.create(
                user_id=1, start_date=start, end_date=end,
                guests=2, property_id=1, has_pet=True,
                terms_accepted=True,
            )
            assert booking['has_pet'] is True
            assert booking['pet_fee'] == 75.0
            assert booking['total_price'] == 620.0
            assert booking['baha_verified'] == 'pending'


class TestUpdateBahaVerified:
    def test_update_baha_on_pet_booking(self, app):
        with app.app_context():
            _seed_property_and_user()
            start = (date.today() + timedelta(days=90)).isoformat()
            end = (date.today() + timedelta(days=95)).isoformat()
            booking = Booking.create(
                user_id=1, start_date=start, end_date=end,
                guests=2, property_id=1, has_pet=True,
                terms_accepted=True,
            )
            updated = Booking.update_baha_verified(booking['id'], 'verified')
            assert updated['baha_verified'] == 'verified'

    def test_update_baha_rejects_non_pet_booking(self, app):
        with app.app_context():
            _seed_property_and_user()
            start = (date.today() + timedelta(days=100)).isoformat()
            end = (date.today() + timedelta(days=105)).isoformat()
            booking = Booking.create(
                user_id=1, start_date=start, end_date=end,
                guests=2, property_id=1,
                terms_accepted=True,
            )
            with pytest.raises(ValueError, match="only applies to bookings with pets"):
                Booking.update_baha_verified(booking['id'], 'verified')
