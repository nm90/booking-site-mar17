"""
Email Service - Sends transactional emails for key booking events.

Uses Flask-Mail. Falls back gracefully if mail is not configured
(logs the email instead of sending).
"""

import logging
from flask import current_app, render_template
from flask_mail import Message

logger = logging.getLogger(__name__)


def _get_mail():
    """Get the Mail instance from the app extensions."""
    return current_app.extensions.get('mail')


def _send(subject: str, recipients: list, html_body: str, text_body: str = None):
    """Send an email. Logs instead of sending if mail is not configured."""
    mail = _get_mail()
    if not mail or not current_app.config.get('MAIL_USERNAME'):
        logger.info(f"[EMAIL NOT CONFIGURED] To: {recipients} | Subject: {subject}")
        logger.debug(f"Body: {text_body or html_body}")
        return False

    try:
        msg = Message(subject=subject, recipients=recipients)
        msg.html = html_body
        if text_body:
            msg.body = text_body
        mail.send(msg)
        logger.info(f"Email sent: '{subject}' to {recipients}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
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
