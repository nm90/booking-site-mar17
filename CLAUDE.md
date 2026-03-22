# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app
python backend/app.py          # http://localhost:5000

# Docker
docker compose up --build

# Initialize/reset database manually
python -c "from backend.database.seed import seed_database; seed_database()"
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

Add as a new top-level ## Deployment section in CLAUDE.md\n\n## Deployment (Koyeb)
- Always use `koyeb.yaml` for deployment config. Verify CLI commands exist before suggesting them (`koyeb --help`).
- Link secrets as environment variables in `koyeb.yaml`, not just in the Koyeb dashboard.
- Avoid persistent volumes on Koyeb unless explicitly needed; use managed databases instead.
- Always ensure `.env` files are sourced in `startup.sh`.
Add as a new ## Docker section in CLAUDE.md, or append to an existing infrastructure section\n\n## Docker
- Check Docker Compose version before running commands: use `docker-compose` (v1) if `docker compose` (v2) is unavailable.
- Run `docker compose version || docker-compose version` to detect which is installed.
Add as a new ## Testing section in CLAUDE.md\n\n## Testing
- Do not add Flask routes after app initialization in tests. Use app factory pattern or register routes before first request.
- Always run `pytest` after modifying application code before committing.
Add under a ## General or ## Conventions section in CLAUDE.md\n\n## General
- When using external CLI tools (koyeb, docker, gh), verify the command exists with `--help` before running it.
- For GitHub API calls, always include all required fields (e.g., 'description' on singleSelectOptions).