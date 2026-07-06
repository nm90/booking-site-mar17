# Koyeb Deployment Guide — Vacation Rental Booking System

> **Note:** This guide walks through setting up a *new* Koyeb service via Koyeb's own Git integration (Step 2). The current production service (`booking-site-mar17/booking-site`) instead redeploys through [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) — a GitHub Actions workflow that runs the Koyeb CLI's archive + Docker builder (`koyeb deploy`) on every push to `main`, after a prerequisite job that builds and pushes the `fauxtoe/booking-site` image to DockerHub (kept for `koyeb.yaml`; the archive deploy itself rebuilds from source). It's still a git-driven flow, just via GitHub Actions rather than Koyeb's native "Deploy with Git" autodeploy. See [`CLAUDE.md`](CLAUDE.md#deployment-koyeb) for the exact command and how to run it manually.

## Prerequisites

- [ ] GitHub account
- [ ] GitHub repository created and code pushed
- [ ] Koyeb account (https://app.koyeb.com)

---

## Step 1: Push to GitHub

```bash
git init
git add .
git commit -m "chore: initial commit"
git remote add origin https://github.com/YOUR_USERNAME/booking-site.git
git branch -M main
git push -u origin main
```

Confirm these files are in your repository:

| File | Purpose |
|---|---|
| `Procfile` | Tells Koyeb how to start the app |
| `Dockerfile` | Container build instructions |
| `koyeb.yaml` | Service configuration |
| `.koyebignore` | Files to skip during deployment triggers |
| `.dockerignore` | Files excluded from Docker build context |
| `requirements.txt` | Python dependencies |
| `backend/app.py` | Application entry point |

---

## Step 2: Connect Koyeb to GitHub

1. Go to [Koyeb Dashboard](https://app.koyeb.com)
2. **Profile icon → Settings → Connected Accounts**
3. Click **Install GitHub App**
4. Authorize and select your `booking-site` repository
5. Click **Install**

---

## Step 3: Create the Service

### 3.1 Start deployment
1. Click **+ Create Service**
2. Select **Deploy with Git**

### 3.2 Select repository
1. Choose **GitHub**
2. Select `booking-site`
3. Click **Next**

### 3.3 Builder settings
- **Branch**: `main`
- **Builder**: `Dockerfile` (auto-detected)
- **Dockerfile path**: `Dockerfile`
- **Autodeploy**: ✅ Enabled
- Click **Next**

### 3.4 Environment variables

Add all of these:

| Key | Value | Notes |
|---|---|---|
| `FLASK_ENV` | `production` | Disables debug mode |
| `PYTHONUNBUFFERED` | `1` | Required for container log streaming |
| `SECRET_KEY` | *(generated — see below)* | **Required** — Flask session security |
| `DATABASE_PATH` | `/tmp/booking_site.db` | Ephemeral SQLite path on Koyeb |

**Generate a SECRET_KEY:**

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and paste it as the `SECRET_KEY` value. Keep it secret — never commit it to git.

### 3.5 Instance & scaling
- **Instance**: Eco (smallest tier, sufficient for this app)
- **Region**: Choose one closest to your users
- **Min instances**: `1`
- **Max instances**: `1`

### 3.6 Health check (auto-configured)
- **Endpoint**: `/health`
- **Interval**: 30s
- **Timeout**: 10s

### 3.7 Deploy
1. Review all settings
2. Click **Create & Deploy**
3. Wait for all stages to go green:
   - ✅ Building
   - ✅ Pushing
   - ✅ Deploying
   - ✅ Running

---

## Step 4: Verify

1. In the service overview, copy the public URL:
   `https://booking-site-[random].koyeb.app`
2. Open it — you should be redirected to the login page
3. Confirm the health check: `https://your-app.koyeb.app/health` → `{"status": "ok"}`
4. Log in with the demo accounts:
   - **Admin**: `admin@vacationrental.com` / `admin123`
   - **Customer**: `alice@example.com` / `pass123`

---

## Step 5: Automatic Deployments

Every `git push` to `main` triggers a redeploy automatically — not via Koyeb's own Git integration, but through [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml), which runs on GitHub Actions and calls the Koyeb CLI's archive-based `koyeb deploy` (see [`CLAUDE.md`](CLAUDE.md#deployment-koyeb)).

```bash
# Make a change, then:
git add .
git commit -m "feat: my change"
git push origin main
# → GitHub Actions builds and runs `koyeb deploy`, redeploying production
```

---

## Database Persistence

> **SQLite (default) is ephemeral on Koyeb.** Without `DATABASE_URL` set, the app uses the SQLite file at `DATABASE_PATH` (e.g. `/tmp/booking_site.db`), which is wiped on each deployment. Seed data is re-inserted automatically on startup, so the demo accounts always work — but real booking data will not survive a redeploy.

### Option A — Koyeb Persistent Volume

1. Service **Settings → Disks → Add Disk**
2. Mount path: `/data`
3. Update env var: `DATABASE_PATH` → `/data/booking_site.db`
4. Redeploy

Data survives redeployments, but `CLAUDE.md` recommends avoiding persistent volumes on Koyeb in favor of a managed database (Option B).

### Option B — Postgres / Supabase (recommended for production)

The app already supports Postgres natively — no code changes needed:

1. Provision a Postgres database (Supabase's Session/pooler connection string works well).
2. Set the `DATABASE_URL` env var to that connection string, including `sslmode=require`.
3. On startup, `backend/app.py` detects `DATABASE_URL`, creates the schema from `backend/database/schema_postgres.sql` if it doesn't exist yet, and runs idempotent migrations on subsequent boots.
4. `DATABASE_PATH` is ignored once `DATABASE_URL` is set.

See the `DATABASE_URL` row in [`CLAUDE.md`](CLAUDE.md#environment-variables) for details.

---

## Troubleshooting

### Build fails

```
ERROR: Could not find requirements.txt
```
→ Make sure `requirements.txt` is in the **repository root**, not inside `backend/`.

### Service crashes immediately

1. Click **Logs** tab in Koyeb
2. Common causes:
   - `SECRET_KEY` not set → add it in environment variables
   - Import error → check all `requirements.txt` entries are correct
   - Port mismatch → confirm `koyeb.yaml` has `port: 5000`

### Health check fails

1. Verify `/health` route exists in `backend/app.py`
2. Increase health check timeout to 30s in **Settings → Health Check**
3. Check logs for startup errors

### 500 errors after deploy

Usually a missing env var. Verify `SECRET_KEY`, `FLASK_ENV`, and `PYTHONUNBUFFERED` are all set.

---

## Environment Variables Reference

| Variable | Value | Required | Purpose |
|---|---|---|---|
| `FLASK_ENV` | `production` | ✅ | Disables debug mode |
| `PYTHONUNBUFFERED` | `1` | ✅ | Streams logs to Koyeb console |
| `SECRET_KEY` | *random hex* | ✅ | Flask session encryption |
| `DATABASE_PATH` | `/tmp/booking_site.db` | No | SQLite path (ignored if `DATABASE_URL` is set) |
| `DATABASE_URL` | Postgres/Supabase connection string | No (recommended) | Switches persistence to Postgres — see Option B above |
| `TRUST_PROXY_HEADERS` | `true` | Recommended | Honors `X-Forwarded-*` from Koyeb's TLS-terminating proxy |

For the full set of app-level environment variables (mail delivery, fees/tax rates, contact links, etc.), see the table in [`CLAUDE.md`](CLAUDE.md#environment-variables).

---

## Deployment Checklist

| Item | Status |
|---|---|
| `Procfile` | ✅ |
| `Dockerfile` | ✅ |
| `koyeb.yaml` | ✅ |
| `.koyebignore` | ✅ |
| `.dockerignore` | ✅ |
| `.gitignore` | ✅ |
| `debug=False` in production | ✅ |
| `/health` endpoint | ✅ |
| GitHub repository | ⏳ Push your code |
| Koyeb account | ⏳ Create at koyeb.com |
| `SECRET_KEY` env var | ⏳ Generate and set in Koyeb |

---

**Resources**
- [Koyeb Docs: Deploy with Git](https://www.koyeb.com/docs/build-and-deploy/git)
- [Koyeb Docs: Environment Variables](https://www.koyeb.com/docs/reference/environment-variables)
- [Koyeb Docs: Persistent Storage](https://www.koyeb.com/docs/reference/disks)
