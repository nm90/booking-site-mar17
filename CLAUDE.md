# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Remediation backlog:** For the functional-gap audit and autonomous wave order (security, schema, session/proxy, UX), see [docs/agent-gap-runbook.md](docs/agent-gap-runbook.md).

## Commands

```bash
# Run the app
python3 backend/app.py          # http://localhost:5000

# Docker
docker compose up --build

# Initialize/reset database manually
python3 -c "from backend.database.seed import seed_database; seed_database()"
```

No test suite or linter is configured.

## Architecture

Flask MVC app with strict layer separation:

- **`backend/app.py`** — Entry point. Registers 3 blueprints, initializes DB on first run, injects session vars into all templates via context processor.
- **`backend/controllers/`** — HTTP layer only. No SQL. Calls model methods, manages `session`, renders templates or redirects.
- **`backend/models/`** — Business logic and persistence. Raises `ValueError` for validation failures. Uses `execute_query()` for all SQL.
- **`backend/database/connection.py`** — `execute_query(sql, params, fetchone, commit)` wrapper. Converts rows to dicts automatically.
- **`backend/templates/`** — Jinja2. Extend `base.html`. Display only, no logic.

## Key Patterns

**Authentication:** Session-based (`session['user_id']`, `session['user_role']`). Decorators `@login_required` and `@admin_required` are defined in `auth_controller.py` and imported by other controllers.

**Database access:** Always use `execute_query()` — never open connections directly. Parameterized queries only. The DB path comes from the `DATABASE_PATH` env var (default: `backend/database/booking_site.db`).

**Validation:** Models raise `ValueError` with user-friendly messages. Controllers catch these and re-render the form with the error. SQLite `IntegrityError` is caught in `execute_query()` and re-raised as a readable message.

**Booking lifecycle:** `pending` → `approved` | `rejected` → (`cancelled` anytime). Reviews can only be submitted after an approved stay.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key-change-in-production` | Flask session signing |
| `DATABASE_PATH` | `backend/database/booking_site.db` | SQLite file location |
| `FLASK_ENV` | `development` | Enables debug mode |

## Demo Accounts

- Admin: `admin@vacationrental.com` / `admin123`
- Customers: `alice@example.com` / `pass123`, `bob@example.com` / `pass123`

## Deployment (Koyeb)

The production app is `booking-site-mar17`, service `booking-site`. It uses archive + Docker builder (not the image in `koyeb.yaml`).

```bash
# Deploy current directory to production
koyeb deploy . booking-site-mar17/booking-site --archive-builder docker --wait

# Check service health
koyeb services get booking-site-mar17/booking-site

# View build logs
koyeb service logs 53d7d5ba -t build

# View runtime logs
koyeb service logs 53d7d5ba
```

- Always verify the koyeb CLI exists before suggesting commands (`koyeb --help`).
- Avoid persistent volumes on Koyeb; use managed databases instead.
- Always ensure `.env` files are sourced in `startup.sh`.

## Docker

```bash
# Detect Docker Compose version
docker compose version || docker-compose version
```

- Use `docker-compose` (v1) if `docker compose` (v2) is unavailable.

## Testing

- Do not add Flask routes after app initialization in tests. Use app factory pattern or register routes before first request.
- Always run `pytest` after modifying application code before committing.

## General

- When using external CLI tools (koyeb, docker, gh), verify the command exists with `--help` before running it.
- For GitHub API calls, always include all required fields (e.g., `description` on singleSelectOptions).
