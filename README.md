# 🌅 Sunset Villa — Vacation Rental Booking System

A Flask MVC application implementing the full vacation rental booking system as specified in the requirements, following the patterns established in the educational-mvc project.

## Architecture

Follows the same Flask MVC structure as `educational-mvc`:

```
backend/
├── app.py                          # Application bootstrap (registers blueprints, init DB)
├── controllers/
│   ├── auth_controller.py          # Registration, login, logout + auth decorators
│   ├── portal_controller.py        # All customer-facing routes (/portal/*)
│   └── admin_controller.py         # All admin routes (/admin/*)
├── models/
│   ├── user.py                     # User model (auth, CRUD, roles)
│   ├── booking.py                  # Booking model (availability, lifecycle)
│   ├── review.py                   # Review model (feedback, moderation)
│   └── adventure.py                # Adventure + AdventureBooking models
├── database/
│   ├── schema.sql                  # SQLite schema (users, bookings, reviews, adventures)
│   ├── connection.py               # execute_query() helper
│   └── seed.py                     # Sample data (admin, customers, property, adventures)
├── templates/
│   ├── base.html                   # Shared layout + navigation
│   ├── users/   (login, register)
│   ├── portal/  (dashboard)
│   ├── bookings/(index, new, show)
│   ├── feedback/(new)
│   ├── adventures/(index, new)
│   ├── admin/   (dashboard, bookings, booking_detail, reviews, adventures, users)
│   └── errors/  (404, 500, 403)
└── static/
    ├── css/main.css
    └── js/main.js
```

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python backend/app.py
```

Visit http://localhost:5000

### Demo Accounts

| Role     | Email                         | Password  |
|----------|-------------------------------|-----------|
| Admin    | admin@vacationrental.com      | admin123  |
| Customer | alice@example.com             | pass123   |
| Customer | bob@example.com               | pass123   |

## Running with Docker

```bash
docker-compose up --build
```

## Features

### Customer Portal
- Register / log in / log out
- Request a stay booking (date picker, auto-calculated price, availability check)
- View all bookings with statuses
- Cancel pending or approved bookings
- Leave feedback/reviews on approved stays (star rating + text)
- Browse adventure catalog and submit adventure booking requests

### Admin Dashboard
- Overview of all pending actions (bookings, reviews, adventures)
- Approve or reject booking requests with optional notes
- Moderate guest reviews (approve / reject)
- Approve or reject adventure booking requests
- Manage user accounts (activate / suspend)

## MVC Pattern

Following `educational-mvc` conventions:

- **Models** — Validate input, execute SQL via `execute_query()`, return dicts. Never touched by views.
- **Controllers** — Blueprints. Call model methods, handle errors, render templates or redirect. No SQL.
- **Views (Templates)** — Jinja2 extending `base.html`. Display data only. No business logic.
- **`app.py`** — Bootstrap: registers blueprints, initializes DB, defines error handlers.
