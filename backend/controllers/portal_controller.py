"""
Portal Controller - Customer-facing views and actions.

MVC Role: CONTROLLER
- Handles all customer-facing routes
- Calls Model methods, passes data to templates
- Enforces login_required on all routes

URL Prefix: /portal
Routes:
    GET  /portal/                    - Customer dashboard
    GET  /portal/bookings            - View all bookings
    GET  /portal/bookings/new        - Show booking form
    POST /portal/bookings            - Submit booking request
    GET  /portal/bookings/<id>       - View single booking
    POST /portal/bookings/<id>/cancel - Cancel a booking
    GET  /portal/reviews/new/<booking_id> - Show review form
    POST /portal/reviews             - Submit a review
    GET  /portal/adventures          - Browse adventures
    GET  /portal/adventures/new      - Adventure booking form
    POST /portal/adventures          - Submit adventure request
"""

from flask import Blueprint, request, redirect, url_for, flash, session, render_template
from backend.models.booking import Booking
from backend.models.review import Review
from backend.models.adventure import Adventure, AdventureBooking
from backend.models.property import Property
from backend.controllers.auth_controller import login_required

portal_bp = Blueprint('portal', __name__, url_prefix='/portal')


# ============================================================================
# DASHBOARD
# ============================================================================
@portal_bp.route('/')
@login_required
def dashboard():
    """
    Customer dashboard.

    Shows summary: recent bookings, pending adventure requests.
    """
    user_id = session['user_id']
    bookings = Booking.get_by_user(user_id)
    adventure_bookings = AdventureBooking.get_by_user(user_id)

    return render_template('portal/dashboard.html',
                           bookings=bookings,
                           adventure_bookings=adventure_bookings)


# ============================================================================
# BOOKINGS
# ============================================================================
@portal_bp.route('/bookings')
@login_required
def bookings_index():
    """List all bookings for the current user."""
    user_id = session['user_id']
    bookings = Booking.get_by_user(user_id)
    return render_template('bookings/index.html', bookings=bookings)


@portal_bp.route('/bookings/new', methods=['GET'])
@login_required
def bookings_new():
    """Show the booking request form."""
    properties = Property.get_all(active_only=True)
    selected_id = request.args.get('property_id', type=int)
    return render_template('bookings/new.html', properties=properties, property_id=selected_id)


@portal_bp.route('/bookings', methods=['POST'])
@login_required
def bookings_create():
    """Submit a new booking request."""
    user_id = session['user_id']
    start_date = request.form.get('start_date', '').strip()
    end_date = request.form.get('end_date', '').strip()
    guests = request.form.get('guests', '1')
    property_id = request.form.get('property_id', type=int)
    special_requests = request.form.get('special_requests', '').strip() or None

    properties = Property.get_all(active_only=True)

    try:
        booking = Booking.create(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            guests=guests,
            property_id=property_id,
            special_requests=special_requests
        )
        flash('Booking request submitted! We will review it shortly.', 'success')
        return redirect(url_for('portal.bookings_show', booking_id=booking['id']))

    except ValueError as e:
        flash(str(e), 'error')
        return render_template('bookings/new.html',
                               start_date=start_date, end_date=end_date,
                               guests=guests, special_requests=special_requests,
                               properties=properties, property_id=property_id)

    except Exception as e:
        error_message = getattr(e, 'user_message', str(e))
        flash(error_message, 'error')
        return render_template('bookings/new.html',
                               start_date=start_date, end_date=end_date,
                               guests=guests, properties=properties,
                               property_id=property_id)


@portal_bp.route('/bookings/<int:booking_id>')
@login_required
def bookings_show(booking_id):
    """View a single booking's details."""
    user_id = session['user_id']
    booking = Booking.get_by_id(booking_id)

    if not booking:
        flash('Booking not found.', 'error')
        return render_template('errors/404.html'), 404

    if booking['user_id'] != user_id:
        flash('Access denied.', 'error')
        return redirect(url_for('portal.bookings_index'))

    # Check if the user already left a review
    existing_reviews = Review.get_by_user(user_id)
    already_reviewed = any(r['booking_id'] == booking_id for r in existing_reviews)

    return render_template('bookings/show.html',
                           booking=booking,
                           already_reviewed=already_reviewed)


@portal_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
def bookings_cancel(booking_id):
    """Cancel a booking."""
    user_id = session['user_id']

    try:
        booking = Booking.cancel(booking_id, user_id)
        if not booking:
            flash('Booking not found.', 'error')
        else:
            flash('Booking cancelled successfully.', 'success')
    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('portal.bookings_index'))


# ============================================================================
# REVIEWS / FEEDBACK
# ============================================================================
@portal_bp.route('/reviews/new/<int:booking_id>', methods=['GET'])
@login_required
def reviews_new(booking_id):
    """Show the review submission form for a booking."""
    user_id = session['user_id']
    booking = Booking.get_by_id(booking_id)

    if not booking or booking['user_id'] != user_id:
        flash('Booking not found.', 'error')
        return redirect(url_for('portal.bookings_index'))

    if booking['status'] != 'completed':
        flash('You can only review completed stays.', 'error')
        return redirect(url_for('portal.bookings_show', booking_id=booking_id))

    return render_template('feedback/new.html', booking=booking)


@portal_bp.route('/reviews', methods=['POST'])
@login_required
def reviews_create():
    """Submit a review for a completed stay."""
    user_id = session['user_id']
    booking_id = request.form.get('booking_id', type=int)
    rating = request.form.get('rating', '5')
    title = request.form.get('title', '').strip() or None
    content = request.form.get('content', '').strip()

    try:
        Review.create(
            user_id=user_id,
            booking_id=booking_id,
            rating=rating,
            content=content,
            title=title
        )
        flash('Thank you for your feedback! Your review is pending approval.', 'success')
        return redirect(url_for('portal.bookings_show', booking_id=booking_id))

    except ValueError as e:
        flash(str(e), 'error')
        booking = Booking.get_by_id(booking_id)
        return render_template('feedback/new.html',
                               booking=booking,
                               rating=rating, title=title, content=content)


# ============================================================================
# ADVENTURES
# ============================================================================
@portal_bp.route('/adventures')
@login_required
def adventures_index():
    """Browse available adventure activities."""
    adventures = Adventure.get_all(active_only=True)
    my_bookings = AdventureBooking.get_by_user(session['user_id'])
    return render_template('adventures/index.html',
                           adventures=adventures,
                           my_bookings=my_bookings)


@portal_bp.route('/adventures/new', methods=['GET'])
@login_required
def adventures_new():
    """Show the adventure booking request form."""
    adventure_id = request.args.get('adventure_id', type=int)
    adventures = Adventure.get_all(active_only=True)
    selected = Adventure.get_by_id(adventure_id) if adventure_id else None

    # Get user's approved stay bookings for linking
    user_bookings = Booking.get_by_user(session['user_id'])
    stay_bookings = [b for b in user_bookings if b['status'] == 'approved']

    return render_template('adventures/new.html',
                           adventures=adventures,
                           selected_adventure=selected,
                           stay_bookings=stay_bookings)


@portal_bp.route('/adventures', methods=['POST'])
@login_required
def adventures_create():
    """Submit an adventure booking request."""
    user_id = session['user_id']
    adventure_id = request.form.get('adventure_id', type=int)
    scheduled_date = request.form.get('scheduled_date', '').strip()
    participants = request.form.get('participants', '1')
    booking_id = request.form.get('booking_id', type=int) or None
    special_requests = request.form.get('special_requests', '').strip() or None

    try:
        ab = AdventureBooking.create(
            user_id=user_id,
            adventure_id=adventure_id,
            scheduled_date=scheduled_date,
            participants=participants,
            booking_id=booking_id,
            special_requests=special_requests
        )
        flash('Adventure booking request submitted!', 'success')
        return redirect(url_for('portal.adventures_index'))

    except ValueError as e:
        flash(str(e), 'error')
        adventures = Adventure.get_all(active_only=True)
        user_bookings = Booking.get_by_user(user_id)
        stay_bookings = [b for b in user_bookings if b['status'] == 'approved']
        return render_template('adventures/new.html',
                               adventures=adventures,
                               stay_bookings=stay_bookings,
                               adventure_id=adventure_id,
                               scheduled_date=scheduled_date,
                               participants=participants)
