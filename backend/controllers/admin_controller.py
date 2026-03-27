"""
Admin Controller - Admin dashboard and management actions.

MVC Role: CONTROLLER
- Handles all admin-facing routes
- Enforces admin_required on all routes
- Calls Model methods for approve/reject/manage operations

URL Prefix: /admin
Routes:
    GET  /admin/                          - Admin dashboard
    GET  /admin/bookings                  - All bookings
    GET  /admin/bookings/<id>             - View booking
    POST /admin/bookings/<id>/approve     - Approve booking
    POST /admin/bookings/<id>/reject      - Reject booking
    GET  /admin/reviews                   - All reviews
    POST /admin/reviews/<id>/approve      - Approve review
    POST /admin/reviews/<id>/reject       - Reject review
    GET  /admin/adventures                - Adventure catalog
    GET  /admin/adventures/new            - Show new adventure form
    POST /admin/adventures                - Create adventure
    GET  /admin/adventures/<id>/edit      - Show edit adventure form
    POST /admin/adventures/<id>           - Update adventure
    POST /admin/adventures/<id>/deactivate - Deactivate adventure
    GET  /admin/adventure-bookings        - Adventure bookings
    POST /admin/adventure-bookings/<id>/approve - Approve adventure booking
    POST /admin/adventure-bookings/<id>/reject  - Reject adventure booking
    GET  /admin/users                     - Manage users
    POST /admin/users/<id>/status         - Update user status
"""

from flask import Blueprint, request, redirect, url_for, flash, render_template
from backend.models.booking import Booking
from backend.models.review import Review
from backend.models.adventure import Adventure, AdventureBooking
from backend.models.user import User
from backend.models.property import Property
from backend.controllers.auth_controller import admin_required
from backend.services.email import send_booking_status_change, send_checkin_reminder

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ============================================================================
# DASHBOARD
# ============================================================================
@admin_bp.route('/')
@admin_required
def dashboard():
    """
    Admin dashboard overview.

    Shows pending counts and recent activity.
    """
    pending_bookings = Booking.get_all(status='pending')
    pending_reviews = Review.get_all(status='pending')
    pending_adventures = AdventureBooking.get_all(status='pending')
    all_bookings = Booking.get_all()

    return render_template('admin/dashboard.html',
                           pending_bookings=pending_bookings,
                           pending_reviews=pending_reviews,
                           pending_adventures=pending_adventures,
                           all_bookings=all_bookings)


# ============================================================================
# BOOKING MANAGEMENT
# ============================================================================
@admin_bp.route('/bookings')
@admin_required
def bookings_index():
    """View all bookings with optional status filter."""
    status = request.args.get('status')
    bookings = Booking.get_all(status=status)
    return render_template('admin/bookings.html', bookings=bookings, current_status=status)


@admin_bp.route('/bookings/<int:booking_id>')
@admin_required
def bookings_show(booking_id):
    """View a single booking's full details."""
    booking = Booking.get_by_id(booking_id, include_relations=True)
    if not booking:
        flash('Booking not found.', 'error')
        return render_template('errors/404.html'), 404
    return render_template('admin/booking_detail.html', booking=booking)


@admin_bp.route('/bookings/<int:booking_id>/approve', methods=['POST'])
@admin_required
def bookings_approve(booking_id):
    """Approve a pending booking."""
    admin_notes = request.form.get('admin_notes', '').strip() or None

    try:
        booking = Booking.update_status(booking_id, 'approved', admin_notes)
        if not booking:
            flash('Booking not found.', 'error')
        else:
            if booking.get('user'):
                send_booking_status_change(booking['user']['email'], booking['user']['first_name'], booking)
                send_checkin_reminder(booking['user']['email'], booking['user']['first_name'], booking)
            flash(f'Booking #{booking_id} has been approved.', 'success')
    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('admin.bookings_show', booking_id=booking_id))


@admin_bp.route('/bookings/<int:booking_id>/reject', methods=['POST'])
@admin_required
def bookings_reject(booking_id):
    """Reject a pending booking."""
    admin_notes = request.form.get('admin_notes', '').strip() or None

    if not admin_notes:
        flash('A reason is required when rejecting a booking.', 'error')
        return redirect(url_for('admin.bookings_show', booking_id=booking_id))

    try:
        booking = Booking.update_status(booking_id, 'rejected', admin_notes)
        if not booking:
            flash('Booking not found.', 'error')
        else:
            if booking.get('user'):
                send_booking_status_change(booking['user']['email'], booking['user']['first_name'], booking)
            flash(f'Booking #{booking_id} has been rejected.', 'success')
    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('admin.bookings_show', booking_id=booking_id))


@admin_bp.route('/bookings/<int:booking_id>/complete', methods=['POST'])
@admin_required
def bookings_complete(booking_id):
    """Mark an approved booking as completed."""
    admin_notes = request.form.get('admin_notes', '').strip() or None

    try:
        booking = Booking.update_status(booking_id, 'completed', admin_notes)
        if not booking:
            flash('Booking not found.', 'error')
        else:
            flash(f'Booking #{booking_id} has been marked as completed.', 'success')
    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('admin.bookings_show', booking_id=booking_id))


# ============================================================================
# REVIEW MODERATION
# ============================================================================
@admin_bp.route('/reviews')
@admin_required
def reviews_index():
    """View all reviews with optional status filter."""
    status = request.args.get('status')
    reviews = Review.get_all(status=status)
    return render_template('admin/reviews.html', reviews=reviews, current_status=status)


@admin_bp.route('/reviews/<int:review_id>/approve', methods=['POST'])
@admin_required
def reviews_approve(review_id):
    """Approve a pending review."""
    review = Review.update_status(review_id, 'approved')
    if not review:
        flash('Review not found.', 'error')
    else:
        flash('Review approved and published.', 'success')
    return redirect(url_for('admin.reviews_index'))


@admin_bp.route('/reviews/<int:review_id>/reject', methods=['POST'])
@admin_required
def reviews_reject(review_id):
    """Reject/remove a review."""
    review = Review.update_status(review_id, 'rejected')
    if not review:
        flash('Review not found.', 'error')
    else:
        flash('Review rejected.', 'success')
    return redirect(url_for('admin.reviews_index'))


# ============================================================================
# ADVENTURE CATALOG MANAGEMENT
# ============================================================================
@admin_bp.route('/adventures')
@admin_required
def adventures_index():
    """View all adventures (including inactive)."""
    adventures = Adventure.get_all(active_only=False)
    return render_template('admin/adventures.html', adventures=adventures)


@admin_bp.route('/adventures/new')
@admin_required
def adventures_new():
    """Show the create adventure form."""
    return render_template('admin/adventure_form.html', valid_difficulties=Adventure.VALID_DIFFICULTIES)


@admin_bp.route('/adventures', methods=['POST'])
@admin_required
def adventures_create():
    """Handle adventure creation."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    category = request.form.get('category', '').strip()
    difficulty = request.form.get('difficulty', '').strip()
    duration_hours = request.form.get('duration_hours', '')
    price = request.form.get('price', '')
    max_participants = request.form.get('max_participants', '')

    try:
        adventure = Adventure.create(
            name=name,
            description=description,
            category=category,
            difficulty=difficulty,
            duration_hours=duration_hours,
            price=price,
            max_participants=max_participants
        )
        flash(f'Adventure "{adventure["name"]}" created successfully.', 'success')
        return redirect(url_for('admin.adventures_index'))
    except ValueError as e:
        flash(str(e), 'error')
        return render_template(
            'admin/adventure_form.html',
            valid_difficulties=Adventure.VALID_DIFFICULTIES,
            adventure={
                'name': name,
                'description': description,
                'category': category,
                'difficulty': difficulty,
                'duration_hours': duration_hours,
                'price': price,
                'max_participants': max_participants,
            }
        )


@admin_bp.route('/adventures/<int:adventure_id>/edit')
@admin_required
def adventures_edit(adventure_id):
    """Show the edit adventure form."""
    adventure = Adventure.get_by_id(adventure_id)
    if not adventure:
        flash('Adventure not found.', 'error')
        return redirect(url_for('admin.adventures_index'))
    return render_template('admin/adventure_form.html',
                           adventure=adventure,
                           valid_difficulties=Adventure.VALID_DIFFICULTIES,
                           valid_statuses=Adventure.VALID_STATUSES)


@admin_bp.route('/adventures/<int:adventure_id>', methods=['POST'])
@admin_required
def adventures_update(adventure_id):
    """Handle adventure update."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    category = request.form.get('category', '').strip()
    difficulty = request.form.get('difficulty', '').strip()
    duration_hours = request.form.get('duration_hours', '')
    price = request.form.get('price', '')
    max_participants = request.form.get('max_participants', '')
    status = request.form.get('status', 'active').strip()

    try:
        adventure = Adventure.update(
            adventure_id=adventure_id,
            name=name,
            description=description,
            category=category,
            difficulty=difficulty,
            duration_hours=duration_hours,
            price=price,
            max_participants=max_participants,
            status=status
        )
        if not adventure:
            flash('Adventure not found.', 'error')
        else:
            flash(f'Adventure "{adventure["name"]}" updated successfully.', 'success')
        return redirect(url_for('admin.adventures_index'))
    except ValueError as e:
        flash(str(e), 'error')
        return render_template(
            'admin/adventure_form.html',
            valid_difficulties=Adventure.VALID_DIFFICULTIES,
            valid_statuses=Adventure.VALID_STATUSES,
            adventure={
                'id': adventure_id,
                'name': name,
                'description': description,
                'category': category,
                'difficulty': difficulty,
                'duration_hours': duration_hours,
                'price': price,
                'max_participants': max_participants,
                'status': status
            }
        )


@admin_bp.route('/adventures/<int:adventure_id>/deactivate', methods=['POST'])
@admin_required
def adventures_deactivate(adventure_id):
    """Deactivate an adventure."""
    adventure = Adventure.deactivate(adventure_id)
    if not adventure:
        flash('Adventure not found.', 'error')
    else:
        flash(f'Adventure "{adventure["name"]}" deactivated.', 'success')
    return redirect(url_for('admin.adventures_index'))


# ============================================================================
# ADVENTURE BOOKING MANAGEMENT
# ============================================================================
@admin_bp.route('/adventure-bookings')
@admin_required
def adventure_bookings_index():
    """View all adventure booking requests."""
    status = request.args.get('status')
    bookings = AdventureBooking.get_all(status=status)
    return render_template('admin/adventure_bookings.html', bookings=bookings, current_status=status)


@admin_bp.route('/adventure-bookings/<int:ab_id>/approve', methods=['POST'])
@admin_required
def adventure_bookings_approve(ab_id):
    """Approve an adventure booking."""
    ab = AdventureBooking.update_status(ab_id, 'approved')
    if not ab:
        flash('Adventure booking not found.', 'error')
    else:
        flash('Adventure booking approved.', 'success')
    return redirect(url_for('admin.adventure_bookings_index'))


@admin_bp.route('/adventure-bookings/<int:ab_id>/reject', methods=['POST'])
@admin_required
def adventure_bookings_reject(ab_id):
    """Reject an adventure booking."""
    ab = AdventureBooking.update_status(ab_id, 'rejected')
    if not ab:
        flash('Adventure booking not found.', 'error')
    else:
        flash('Adventure booking rejected.', 'success')
    return redirect(url_for('admin.adventure_bookings_index'))


# ============================================================================
# USER MANAGEMENT
# ============================================================================
@admin_bp.route('/users')
@admin_required
def users_index():
    """View all users."""
    users = User.get_all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/<int:user_id>/status', methods=['POST'])
@admin_required
def users_update_status(user_id):
    """Suspend or activate a user account."""
    status = request.form.get('status', '').strip()

    try:
        user = User.update_status(user_id, status)
        if not user:
            flash('User not found.', 'error')
        else:
            flash(f"User account status updated to '{status}'.", 'success')
    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('admin.users_index'))


# ============================================================================
# PROPERTY MANAGEMENT
# ============================================================================
@admin_bp.route('/properties')
@admin_required
def properties_index():
    """View all properties."""
    properties = Property.get_all()
    return render_template('admin/properties.html', properties=properties)


@admin_bp.route('/properties/new')
@admin_required
def properties_new():
    """Show the create property form."""
    return render_template('admin/property_form.html')


@admin_bp.route('/properties', methods=['POST'])
@admin_required
def properties_create():
    """Handle property creation."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    location = request.form.get('location', '').strip()
    capacity = request.form.get('capacity', '')
    price_per_night = request.form.get('price_per_night', '')
    check_in_instructions = request.form.get('check_in_instructions', '').strip()

    try:
        prop = Property.create(name, description, location, capacity, price_per_night,
                               check_in_instructions=check_in_instructions)
        flash(f'Property "{prop["name"]}" created successfully.', 'success')
        return redirect(url_for('admin.properties_index'))
    except ValueError as e:
        flash(str(e), 'error')
        return render_template('admin/property_form.html',
                               name=name, description=description, location=location,
                               capacity=capacity, price_per_night=price_per_night,
                               check_in_instructions=check_in_instructions)


@admin_bp.route('/properties/<int:property_id>/edit')
@admin_required
def properties_edit(property_id):
    """Show the edit property form."""
    prop = Property.get_by_id(property_id)
    if not prop:
        flash('Property not found.', 'error')
        return redirect(url_for('admin.properties_index'))
    return render_template('admin/property_form.html', property=prop)


@admin_bp.route('/properties/<int:property_id>', methods=['POST'])
@admin_required
def properties_update(property_id):
    """Handle property update."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    location = request.form.get('location', '').strip()
    capacity = request.form.get('capacity', '')
    price_per_night = request.form.get('price_per_night', '')
    status = request.form.get('status', 'active')
    check_in_instructions = request.form.get('check_in_instructions', '').strip()

    try:
        prop = Property.update(property_id, name, description, location,
                               capacity, price_per_night, status,
                               check_in_instructions=check_in_instructions)
        if not prop:
            flash('Property not found.', 'error')
        else:
            flash(f'Property "{prop["name"]}" updated successfully.', 'success')
        return redirect(url_for('admin.properties_index'))
    except ValueError as e:
        flash(str(e), 'error')
        return render_template('admin/property_form.html',
                               property={'id': property_id, 'name': name, 'description': description,
                                         'location': location, 'capacity': capacity,
                                         'price_per_night': price_per_night, 'status': status,
                                         'check_in_instructions': check_in_instructions})


@admin_bp.route('/properties/<int:property_id>/delete', methods=['POST'])
@admin_required
def properties_delete(property_id):
    """Handle property deletion."""
    try:
        Property.delete(property_id)
        flash('Property deleted successfully.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.properties_index'))
