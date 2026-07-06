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

# Run tests
pytest
```

A pytest suite exists in `backend/tests/`. No linter is configured.

## Architecture

Flask MVC app with strict layer separation:

- **`backend/app.py`** — Entry point. Registers 3 blueprints (`auth`, `portal`, `admin`), initializes/migrates DB on first run, injects session vars into all templates via context processor.
- **`backend/controllers/`** — HTTP layer only. No SQL. Calls model methods, manages `session`, renders templates or redirects.
- **`backend/models/`** — Business logic and persistence (`user`, `property`, `booking`, `review`, `adventure`). Raises `ValueError` for validation failures. Uses `execute_query()` for all SQL.
- **`backend/services/`** — Cross-cutting integrations: `email.py` (Flask-Mail SMTP or Brevo API) and `pdf.py` (WeasyPrint rental agreement PDFs). Called from controllers/models, not the other way around.
- **`backend/database/connection.py`** — `execute_query(sql, params, fetchone, commit)` wrapper. Converts rows to dicts automatically.
- **`backend/templates/`** — Jinja2. Extend `base.html`. Display only, no logic.

## Key Patterns

**Authentication:** Session-based (`session['user_id']`, `session['user_role']`). Decorators `@login_required` and `@admin_required` are defined in `auth_controller.py` and imported by other controllers.

**Database access:** Always use `execute_query()` — never open connections directly. Parameterized queries only, written with `?` placeholders. Two dialects behind the same API: if `DATABASE_URL` is set the app runs on Postgres via psycopg (placeholder translation, `INSERT ... RETURNING id`, SQLSTATE error mapping all handled inside `connection.py`); otherwise SQLite at `DATABASE_PATH` (default: `backend/database/booking_site.db`). Keep model SQL engine-neutral (e.g. `CURRENT_DATE`, not `date('now')`).

**Validation:** Models raise `ValueError` with user-friendly messages. Controllers catch these and re-render the form with the error. `IntegrityError` (SQLite or psycopg — catch the `INTEGRITY_ERRORS` tuple from `connection.py`) is caught in `execute_query()` and re-raised with a readable `.user_message`.

**Booking lifecycle:** `pending` → `approved` | `rejected` → (`cancelled` anytime). Reviews can only be submitted after an approved stay.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | _(none — required)_ | Flask session signing. App exits at startup if unset or a known insecure default (see `_INSECURE_DEFAULTS` in `app.py`). Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`. |
| `DATABASE_PATH` | `backend/database/booking_site.db` | SQLite file location (used only when `DATABASE_URL` is unset) |
| `DATABASE_URL` | _(unset)_ | Postgres connection string (e.g. Supabase). Set → app uses Postgres via psycopg; unset → SQLite. Use the Supabase Session/pooler connection string; include `sslmode=require`. |
| `FLASK_ENV` | `development` | Set to `production` to disable debug mode and lower log verbosity |
| `MAIL_SERVER` | `smtp.gmail.com` | SMTP host for Flask-Mail (used when `BREVO_API_KEY` is not set) |
| `MAIL_PORT` | `587` | SMTP port |
| `MAIL_USE_TLS` | `true` | Whether to use STARTTLS for SMTP |
| `MAIL_USERNAME` | _(empty)_ | SMTP auth username |
| `MAIL_PASSWORD` | _(empty)_ | SMTP auth password |
| `MAIL_DEFAULT_SENDER` | `bze@wiscomfort.com` | From-address for outgoing SMTP mail |
| `BREVO_API_KEY` | _(empty)_ | If set, `backend/services/email.py` sends via the Brevo HTTP API instead of SMTP |
| `BREVO_SENDER_NAME` | _(empty)_ | Display name used for the Brevo sender |
| `ADMIN_EMAIL` | `bze@wiscomfort.com` | Recipient for admin notification emails (e.g. new booking alerts) |
| `CONTACT_EMAIL` | `bze@wiscomfort.com` | Contact address shown in templates (injected via context processor) |
| `LANDING_SITE_URL` | `https://nm90.github.io/booking-site-mar17/` | Marketing/landing site URL linked from the app; normalized to end with `/` |
| `BTB_TAX_RATE` | `0.09` | Bed tax rate applied to booking subtotals |
| `PET_SANITATION_FEE` | `75` | Flat fee added to bookings with a pet |
| `RENTAL_AGREEMENT_VERSION` | `2026-07-05` | Version string stamped on the rental agreement PDF/legal content |
| `TRUST_PROXY_HEADERS` | _(unset/false)_ | Set to `1`/`true`/`yes` to honor `X-Forwarded-*` from one reverse proxy (e.g. Koyeb's TLS terminator) via `ProxyFix` |

## Demo Accounts

- Admin: `admin@vacationrental.com` / `admin123`
- Customers: `alice@example.com` / `pass123`, `bob@example.com` / `pass123`

## Deployment (Koyeb)

The production app is `booking-site-mar17`, service `booking-site`. It uses archive + Docker builder (not the image in `koyeb.yaml`).

**Deploys are automatic:** [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) runs this same `koyeb deploy` command on every push to `main`, so merging to `main` redeploys production without any manual step. The commands below are for redeploying manually (e.g. to test a change before merging, or if the workflow needs to be re-run).

```bash
# Deploy current directory to production
# NOTE: the CLI does NOT honor .koyebignore — it only skips .git,node_modules,vendor
# by default. Pass --archive-ignore-dir for venvs/logs or the archive exceeds the 50MB limit.
koyeb deploy . booking-site-mar17/booking-site --archive-builder docker \
  --archive-ignore-dir .git --archive-ignore-dir node_modules --archive-ignore-dir vendor \
  --archive-ignore-dir venv --archive-ignore-dir .venv --archive-ignore-dir .pytest_cache \
  --archive-ignore-dir log --archive-ignore-dir logs --archive-ignore-dir backend/logs \
  --wait

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
# Prefer Compose v2 (legacy docker-compose v1 breaks on modern Engine)
docker compose version || docker-compose version
```

- Prefer `docker compose` (v2). Legacy `docker-compose` v1 can raise `KeyError: 'ContainerConfig'`; install the compose plugin if needed.

## Testing

- Do not add Flask routes after app initialization in tests. Use app factory pattern or register routes before first request.
- Always run `pytest` after modifying application code before committing.

## General

- When using external CLI tools (koyeb, docker, gh), verify the command exists with `--help` before running it.
- For GitHub API calls, always include all required fields (e.g., `description` on singleSelectOptions).
