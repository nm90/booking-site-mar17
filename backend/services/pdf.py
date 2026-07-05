"""PDF generation for rental agreement contracts."""

from flask import current_app


def _guest_display_name(booking: dict) -> str:
    user = booking.get('user') or {}
    first = (user.get('first_name') or '').strip()
    last = (user.get('last_name') or '').strip()
    name = f"{first} {last}".strip()
    return name or 'Guest'


def generate_contract_pdf(booking: dict) -> bytes:
    """Render the vacation rental agreement as a PDF byte string."""
    from weasyprint import HTML

    ctx = {
        'booking': booking,
        'guest_name': _guest_display_name(booking),
        'agreement_version': current_app.config.get('RENTAL_AGREEMENT_VERSION', '2026-07-05'),
        'has_pet': bool(booking.get('has_pet')),
    }
    html = current_app.jinja_env.get_template('pdf/agreement_contract.html').render(**ctx)
    base_url = f"file://{current_app.root_path}/templates/"
    return HTML(string=html, base_url=base_url).write_pdf()
