 Phased Plan: Add Supabase (Postgres) as an Alternate Database

 Context

 The app currently runs on SQLite only (backend/database/connection.py, driver sqlite3). We want to be able to
 run against a Supabase Postgres database while keeping SQLite for local development — the driver is chosen
 at runtime by an env var. Connection is via direct Postgres (Supabase connection string) using psycopg, so
 all existing raw SQL in the models stays. No existing SQLite data is migrated; Supabase starts from a fresh
 schema + seed.

 The app's SQL is almost entirely portable. Only a handful of things are SQLite-specific:

 - Placeholders: every model query uses ?; psycopg needs %s.
 - Insert IDs: execute_query() returns cursor.lastrowid (line 82); Postgres needs INSERT ... RETURNING id.
 - date('now'): used in Booking.transition_completed() (backend/models/booking.py, the only occurrence);
 portable replacement is CURRENT_DATE (valid in both engines).
 - Error parsing: _parse_integrity_error() matches SQLite error text; Postgres uses SQLSTATE codes.
 - Schema DDL / init: AUTOINCREMENT, executescript(), PRAGMA, sqlite_master migrations are SQLite-only.

 The strategy is to centralize all dialect differences in connection.py + a new Postgres schema/init path, so
 model files change almost not at all.

 Design overview

 connection.py gains a single decision point: if DATABASE_URL is set → Postgres (psycopg); else → SQLite
 (current behavior). A small internal helper reports the active dialect. Everything else — placeholder
 translation, dict rows, RETURNING, error mapping, transactions — is handled inside execute_query() and the
 transaction context manager, so callers keep using ?-style queries and expect a returned insert id.

 ---
 Phase 1 — Driver abstraction in backend/database/connection.py

 Rewrite the infrastructure layer to support both drivers behind the same API (get_connection,
 close_connection, begin_immediate, execute_query).

 1. Dialect selection: add DATABASE_URL = os.environ.get('DATABASE_URL') and a helper _is_postgres() returning
 bool(DATABASE_URL). Keep DB_PATH for the SQLite path.
 2. get_connection():
   - Postgres: import psycopg + from psycopg.rows import dict_row; psycopg.connect(DATABASE_URL,
 row_factory=dict_row) stored on g.db. dict_row makes fetchone/fetchall return dicts, matching the current
 dict(row) behavior — so the dict(result) conversions become pass-throughs.
   - SQLite: unchanged (sqlite3.connect, sqlite3.Row, PRAGMA foreign_keys = ON).
 3. execute_query() — branch on dialect:
   - Placeholders: for Postgres, translate ? → %s (e.g. a _translate(query) helper). Add a verification step
 to grep model SQL for any literal % (e.g. LIKE '%x%') which would need %% under psycopg — see Verification.
   - Insert id (replaces lastrowid): when commit=True and the statement is an INSERT lacking a RETURNING,
 append RETURNING id, execute, and return cursor.fetchone()['id']. For non-INSERT commits (UPDATE/DELETE),
 return None (models ignore the return value there, matching today). SQLite path keeps returning
 cursor.lastrowid.
   - Row conversion: with dict_row, return result/results directly (SQLite keeps dict(...)).
   - Error handling: catch sqlite3.IntegrityError and psycopg.errors.IntegrityError; attach .user_message via
 the parser below.
 4. _parse_integrity_error(): generalize. For psycopg, branch on e.sqlstate — 23505 unique, 23503 FK, 23502
 not-null, 23514 check — using e.diag.constraint_name / e.diag.column_name to build the same user-facing
 strings (preserve the special users.email → "An account with this email already exists" case by checking the
 constraint name users_email_unique). Keep the existing SQLite string-parsing branch.
 5. begin_immediate(): for Postgres, psycopg opens a transaction implicitly (autocommit off) — use a plain
 conn transaction (no BEGIN IMMEDIATE); keep commit/rollback + g.in_transaction semantics identical. SQLite
 branch unchanged.
 6. Dependency: add psycopg[binary] to requirements.txt.

 Critical file: backend/database/connection.py (single most important change).

 Phase 2 — Postgres schema + driver-aware seed

 1. New backend/database/schema_postgres.sql: port schema.sql with:
   - id INTEGER PRIMARY KEY AUTOINCREMENT → id SERIAL PRIMARY KEY.
   - DATETIME → TIMESTAMP; REAL → NUMERIC(10,2) (or keep REAL); DATE/TEXT/INTEGER/CHECK/FK/UNIQUE/indexes port
 as-is.
   - Keep email_verified as INTEGER (0/1), not BOOLEAN, so user.py's SET email_verified = 1 / bool(...) logic
 needs no change. Same for any other 0/1 flags.
   - Because Supabase starts fresh, bake the already-"hardened" constraints (the ones app.py migrations add
 for existing SQLite DBs) directly into this schema — no runtime migrations needed for Postgres.
 2. backend/database/seed.py: make insert_seed_data() dialect-aware. Factor the connection open into a helper:
 Postgres uses psycopg.connect(DATABASE_URL) with %s placeholders; SQLite unchanged. The seed statements that
 already use ? need placeholder translation (reuse the Phase-1 helper) or a parameter-style switch. The
 PRAGMA foreign_keys = ON at the top of insert_seed_data() is SQLite-only — skip it on Postgres (FKs are
 always enforced there). Seed rows never insert explicit id values — the booking/review inserts only
 reference user_id/property_id/booking_id as FK literals — so they work as-is with SERIAL (sequences start
 at 1 and stay in sync).

 Phase 3 — App initialization branching in backend/app.py

 init_database() (line 310) currently assumes a SQLite file. Add a dialect branch at the top:

 - Postgres: connect via psycopg; check information_schema.tables for users. If absent → run
 schema_postgres.sql (execute the whole script), then insert_seed_data(). If present → do nothing (no
 ALTER/rebuild migrations; the Postgres schema is authoritative). Skip all fcntl file-lock and sqlite_master
 logic.
 - SQLite: keep the entire existing path (file lock, executescript, ALTER-based migrations, table rebuilds)
 unchanged.

 app.config['DATABASE_PATH'] wiring stays for SQLite; guard file-path usage behind the SQLite branch.

 Phase 4 — Portable SQL fixes in models

 Small, engine-neutral edits (work on both SQLite and Postgres):

 - Replace date('now') with CURRENT_DATE in Booking.transition_completed() (backend/models/booking.py). This
 is the only date('now') in the codebase — backend/models/adventure.py has no equivalent.
 - backend/models/review.py: it catches sqlite3.IntegrityError directly (line ~85) around the duplicate-review
 insert. Change to catch the shared integrity error — simplest: catch Exception and re-check, or import a
 tuple INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.errors.IntegrityError) exposed from connection.py.
 Prefer exposing that tuple from connection.py and importing it here.

 No other model SQL changes expected (placeholders handled centrally in Phase 1).

 Phase 5 — Config, env, and docs

 - Document DATABASE_URL (Supabase Postgres connection string) in CLAUDE.md's Environment Variables table and
 note the "set it → Postgres, unset → SQLite" behavior.
 - Ensure startup.sh sources .env (per CLAUDE.md deployment note) so DATABASE_URL reaches the app on Koyeb.
 - Note the Supabase connection-string choice: use the Session/pooler connection string for a long-lived Flask
 process (per-request connection via g), and that Supabase requires SSL (psycopg honors sslmode in the URL).

 ---
 Verification

 1. SQLite regression (unset DATABASE_URL): python3 backend/app.py, confirm DB init + seed still work, log in
 with a demo account, create/approve a booking, submit a review (verifies insert-id + duplicate-review error
 path).
 2. Postgres path: create a Supabase project, export DATABASE_URL=postgresql://..., run the app. Confirm
 schema auto-creates, seed inserts, and the same flows (signup → duplicate-email error, booking create → id
 returned, review duplicate → friendly message, transition_completed uses CURRENT_DATE).
 3. Placeholder/% audit: grep model + seed SQL for literal % (e.g. LIKE '%...%'). If any exist, ensure the
 translation layer emits %% for psycopg; otherwise confirm none exist so plain ?→%s is safe.
 4. Error-mapping spot check: force a unique violation and a FK violation on Postgres; confirm
 _parse_integrity_error() yields the same user-facing strings as SQLite.
 5. No test suite exists; verification is manual per above (and CLAUDE.md's "run the app" flow).

 Out of scope

 - Migrating existing SQLite rows into Supabase (fresh seed only, per decision).
 - Supabase Auth / RLS / PostgREST — we use raw Postgres over psycopg, not the Supabase SDK.
 - Removing SQLite (kept for local dev).
