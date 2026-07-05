"""Smoke tests for rental agreement PDF generation."""

import pytest

from backend.services.pdf import generate_contract_pdf

weasyprint = pytest.importorskip('weasyprint')


def _sample_booking():
    return {
        'id': 7,
        'start_date': '2026-08-01',
        'end_date': '2026-08-06',
        'guests': 2,
        'has_pet': True,
        'pet_fee': 75.0,
        'accommodation_subtotal': 500.0,
        'btb_tax': 45.0,
        'total_price': 620.0,
        'terms_accepted_at': '2026-07-01 12:00:00',
        'created_at': '2026-07-01 12:00:00',
        'user': {'first_name': 'Alice', 'last_name': 'Johnson'},
        'property': {
            'name': 'Caye Garden Casita',
            'location': 'San Pedro Town, Ambergris Caye, Belize',
        },
    }


def test_generate_contract_pdf_returns_pdf_bytes(app):
    with app.app_context():
        pdf = generate_contract_pdf(_sample_booking())
    assert pdf[:4] == b'%PDF'
    assert len(pdf) > 1000


def test_generate_contract_pdf_without_pet(app):
    booking = _sample_booking()
    booking['has_pet'] = False
    booking['pet_fee'] = 0.0
    booking['total_price'] = 545.0
    with app.app_context():
        pdf = generate_contract_pdf(booking)
    assert pdf[:4] == b'%PDF'
