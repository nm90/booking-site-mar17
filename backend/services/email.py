"""
Email Service - Sends transactional emails for key booking events.

Uses Brevo's Transactional API when BREVO_API_KEY is set; otherwise Flask-Mail
(SMTP) when MAIL_USERNAME is set. Falls back to logging if neither is configured.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from flask import current_app, render_template
from flask_mail import Message

logger = logging.getLogger(__name__)

BREVO_SMTP_EMAIL_URL = "https://api.brevo.com/v3/smtp/email"


def _get_mail():
    """Get the Mail instance from the app extensions."""
    return current_app.extensions.get('mail')


def _brevo_sender_from_config(config: dict) -> Optional[Dict[str, str]]:
    """Build Brevo sender dict from MAIL_DEFAULT_SENDER and optional BREVO_SENDER_NAME."""
    raw = config.get('MAIL_DEFAULT_SENDER')
    brevo_name = (config.get('BREVO_SENDER_NAME') or '').strip() or None

    if isinstance(raw, tuple) and len(raw) >= 2:
        name_part = (raw[0] or '').strip() or brevo_name
        email = (raw[1] or '').strip()
        if not email:
            return None
        out: Dict[str, str] = {'email': email}
        if name_part:
            out['name'] = name_part
        return out

    if isinstance(raw, str):
        email = raw.strip()
        if not email:
            return None
        out = {'email': email}
        if brevo_name:
            out['name'] = brevo_name
        return out

    return None


def _send_via_brevo(
    api_key: str,
    sender: Dict[str, str],
    subject: str,
    recipients: List[str],
    html_body: str,
    text_body: Optional[str],
) -> bool:
    payload: Dict[str, Any] = {
        'sender': sender,
        'to': [{'email': r} for r in recipients],
        'subject': subject,
        'htmlContent': html_body,
    }
    if text_body:
        payload['textContent'] = text_body

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        BREVO_SMTP_EMAIL_URL,
        data=data,
        headers={
            'Content-Type': 'application/json',
            'api-key': api_key,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if 200 <= resp.status < 300:
                return True
            logger.error("Brevo API returned unexpected status %s", resp.status)
            return False
    except urllib.error.HTTPError as e:
        logger.error("Brevo API error: HTTP %s", e.code)
        return False
    except urllib.error.URLError as e:
        logger.error("Brevo API request failed: %s", e.reason)
        return False
    except OSError as e:
        logger.error("Brevo API request failed: %s", e)
        return False


def _send(subject: str, recipients: list, html_body: str, text_body: str = None):
    """Send an email via Brevo, SMTP, or log if not configured."""
    api_key = (current_app.config.get('BREVO_API_KEY') or '').strip()
    if api_key:
        sender = _brevo_sender_from_config(current_app.config)
        if not sender:
            logger.warning(
                "BREVO_API_KEY is set but MAIL_DEFAULT_SENDER has no valid email; skipping send."
            )
            return False
        ok = _send_via_brevo(api_key, sender, subject, recipients, html_body, text_body)
        if ok:
            logger.info("Email sent (Brevo): '%s' to %s", subject, recipients)
        return ok

    mail = _get_mail()
    if not mail or not current_app.config.get('MAIL_USERNAME'):
        logger.info("[EMAIL NOT CONFIGURED] To: %s | Subject: %s", recipients, subject)
        logger.debug("Body: %s", text_body or html_body)
        return False

    try:
        msg = Message(subject=subject, recipients=recipients)
        msg.html = html_body
        if text_body:
            msg.body = text_body
        mail.send(msg)
        logger.info("Email sent: '%s' to %s", subject, recipients)
        return True
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False


def send_booking_confirmation(guest_email: str, guest_name: str, booking: dict):
    """Email guest when their booking request is submitted."""
    _send(
        subject=f"Booking Request Received \u2014 {booking['property']['name']}",
        recipients=[guest_email],
        html_body=render_template('emails/booking_confirmation.html',
                                  guest_name=guest_name, booking=booking),
        text_body=f"Hi {guest_name}, your booking request for {booking['property']['name']} "
                  f"({booking['start_date']} to {booking['end_date']}) has been received. "
                  f"We'll review it and get back to you shortly."
    )


def send_booking_status_change(guest_email: str, guest_name: str, booking: dict):
    """Email guest when booking is approved, rejected, or cancelled by admin."""
    status = booking['status']
    subjects = {
        'approved': f"Booking Approved \u2014 {booking['property']['name']}",
        'rejected': f"Booking Update \u2014 {booking['property']['name']}",
        'cancelled': f"Booking Cancelled \u2014 {booking['property']['name']}",
    }
    _send(
        subject=subjects.get(status, f"Booking Update \u2014 {booking['property']['name']}"),
        recipients=[guest_email],
        html_body=render_template('emails/booking_status.html',
                                  guest_name=guest_name, booking=booking),
        text_body=f"Hi {guest_name}, your booking for {booking['property']['name']} "
                  f"({booking['start_date']} to {booking['end_date']}) has been {status}."
    )


def send_password_reset(email: str, reset_url: str):
    """Email user a password reset link."""
    _send(
        subject="Password Reset \u2014 Caye Garden Casita",
        recipients=[email],
        html_body=render_template('emails/password_reset.html',
                                  reset_url=reset_url),
        text_body=f"You requested a password reset. Click this link to set a new password: {reset_url}\n"
                  f"This link expires in 1 hour. If you didn't request this, ignore this email."
    )


def send_checkin_reminder(guest_email: str, guest_name: str, booking: dict):
    """Email guest check-in instructions before arrival (for approved bookings)."""
    if not booking.get('property', {}).get('check_in_instructions'):
        return
    _send(
        subject=f"Check-in Details \u2014 {booking['property']['name']}",
        recipients=[guest_email],
        html_body=render_template('emails/checkin_reminder.html',
                                  guest_name=guest_name, booking=booking),
        text_body=f"Hi {guest_name}, here are your check-in details for {booking['property']['name']}:\n\n"
                  f"{booking['property']['check_in_instructions']}"
    )


def notify_admin_new_booking(admin_email: str, booking: dict):
    """Notify admin when a new booking request is submitted."""
    _send(
        subject=f"New Booking Request \u2014 {booking['property']['name']}",
        recipients=[admin_email],
        html_body=render_template('emails/admin_new_booking.html', booking=booking),
        text_body=f"New booking request from {booking.get('user', {}).get('first_name', 'Guest')} "
                  f"for {booking['property']['name']} ({booking['start_date']} to {booking['end_date']})."
    )
