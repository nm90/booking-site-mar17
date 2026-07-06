# 🌅 Sunset Villa — Vacation Rental Booking System

A Flask MVC application implementing a full vacation rental booking system: customer booking requests, admin approval workflows, reviews, an adventure add-on catalog, and multi-property management — following the patterns established in the educational-mvc project.

## Architecture

Follows the same Flask MVC structure as `educational-mvc`:

```
backend/
├── app.py                          # Application bootstrap: config, DB init/migrations, blueprints, error handlers
├── controllers/
│   ├── auth_controller.py          # Register/login/logout, email verification, password reset, auth decorators
│   ├── portal_controller.py        # Customer-facing routes under /portal/* (dashboard, profile, bookings, reviews, adventures)
│   └── admin_controller.py         # Admin routes (/admin/bookings, /reviews, /adventures, /users, /properties)
├── models/
│   ├── user.py                     # User model (auth, CRUD, roles, password reset / email verification tokens)
│   ├── property.py                 # Property model (vacation rental listings, capacity, pricing)
│   ├── booking.py                  # Booking model (availability, pricing/fees, lifecycle, auto-complete)
│   ├── review.py                   # Review model (feedback, moderation)
│   └── adventure.py                # Adventure + AdventureBooking models
├── services/
│   ├── email.py                    # Transactional email (Flask-Mail SMTP or Brevo API), templated notifications
│   └── pdf.py                      # Rental agreement PDF generation (WeasyPrint)
├── database/
│   ├── schema.sql                  # SQLite schema (users, properties, bookings, reviews, adventures)
│   ├── schema_postgres.sql         # Equivalent schema for the Postgres/Supabase dialect
│   ├── connection.py                # execute_query() helper; picks SQLite or Postgres based on DATABASE_URL
│   └── seed.py                     # Sample data (admin, customers, property, adventures)
├── templates/
│   ├── base.html                   # Shared layout + navigation
│   ├── users/     (login, register, forgot/reset password)
│   ├── portal/    (dashboard, profile)
│   ├── bookings/  (index, new, show)
│   ├── feedback/  (new)
│   ├── adventures/(index, new)
│   ├── admin/     (dashboard, bookings, reviews, adventures, adventure_bookings, users, properties)
│   ├── emails/    (transactional email templates)
│   ├── legal/     (rental agreement content)
│   ├── pdf/       (contract PDF layout)
│   └── errors/    (404, 500, 403)
├── static/
│   ├── css/main.css
│   └── js/main.js
└── tests/                          # pytest suite (models, routes, PDF generation, schema/migrations)
```

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Generate a secure SECRET_KEY (required — the app refuses to start without one)
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Run the server
python backend/app.py
```

Visit http://localhost:5000

> **Security requirement:** `SECRET_KEY` must be set to a cryptographically random value.
> The application will exit immediately if it detects a missing or well-known insecure default key.

By default the app uses a local SQLite database (created and seeded automatically on first run). To run against Postgres (e.g. Supabase) instead, set `DATABASE_URL` — see [Environment Variables](#environment-variables) below and `CLAUDE.md` for details.

### Demo Accounts

| Role     | Email                         | Password  |
|----------|-------------------------------|-----------|
| Admin    | admin@vacationrental.com      | admin123  |
| Customer | alice@example.com             | pass123   |
| Customer | bob@example.com               | pass123   |

## Running with Docker

Use **Docker Compose v2** (the `docker compose` plugin — note the space). Legacy `docker-compose` v1 is incompatible with current Docker Engine and fails with `KeyError: 'ContainerConfig'` when recreating containers.

```bash
docker compose up --build
```

If `docker: unknown command: docker compose`, install the plugin (e.g. on Debian/Ubuntu: `sudo apt-get install docker-compose-v2`).

The Docker entrypoint automatically generates a random `SECRET_KEY` if one is not provided.
To use a persistent key across restarts, pass it explicitly:

```bash
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") docker compose up --build
```

## Running Tests

```bash
pip install -r requirements.txt pytest   # pytest is not in requirements.txt
pytest
```

The suite in `backend/tests/` covers models (booking pricing/availability, adventures, properties, reviews), route-level behavior, contract PDF generation, and the SQLite/Postgres connection layer. There is no separate linter configured for this project.

## Environment Variables

See the table in [`CLAUDE.md`](CLAUDE.md#environment-variables) for the full list of environment variables the app reads (database selection, mail delivery, fees/tax rates, proxy handling, etc.).

## Features

### Customer Portal
- Register / log in / log out, with email verification and forgot/reset password flows
- Request a stay booking (date picker, auto-calculated price including taxes/fees, availability check)
- View all bookings with statuses; download the rental agreement as a PDF
- Cancel pending or approved bookings
- Leave feedback/reviews on approved stays (star rating + text)
- Browse adventure catalog and submit adventure booking requests
- Manage profile details and deactivate account

### Admin Dashboard
- Overview of all pending actions (bookings, reviews, adventures)
- Approve or reject booking requests with optional notes; mark stays complete
- Moderate guest reviews (approve / reject)
- Approve or reject adventure booking requests
- Manage user accounts (activate / suspend)
- Manage properties (create, edit, delete listings — deletion is refused if the property has any booking history)

## MVC Pattern

Following `educational-mvc` conventions:

- **Models** — Validate input, execute SQL via `execute_query()`, return dicts. Never touched by views.
- **Controllers** — Blueprints. Call model methods, handle errors, render templates or redirect. No SQL.
- **Views (Templates)** — Jinja2 extending `base.html`. Display data only. No business logic.
- **`app.py`** — Bootstrap: registers blueprints, initializes DB, defines error handlers.

## Further Reading

- [`CLAUDE.md`](CLAUDE.md) — architecture, key patterns, environment variables, deployment commands
- [`DEPLOYMENT.md`](DEPLOYMENT.md) — pre-deploy checklist
- [`KOYEB_DEPLOYMENT.md`](KOYEB_DEPLOYMENT.md) — step-by-step Koyeb deployment guide
- [`docs/db-plan.md`](docs/db-plan.md) — database design notes
