# Deployment Checklist (Koyeb)

## 1. Docker Build Verification

- [ ] Build the image locally:
  ```bash
  docker compose version || docker-compose version  # use v2 for compose files; v1 is EOL
  docker build -t fauxtoe/booking-site .
  ```
- [ ] Run the container locally and verify it starts:
  ```bash
  docker run --rm -p 5000:5000 \
    -e SECRET_KEY="test-secret" \
    -e DATABASE_PATH="/tmp/booking_site.db" \
    fauxtoe/booking-site
  ```
- [ ] Confirm the health check passes:
  ```bash
  curl -f http://localhost:5000/health
  ```
- [ ] Push the image to Docker Hub:
  ```bash
  docker push fauxtoe/booking-site
  ```

## 2. Environment Variable Mapping (.env → koyeb.yaml)

Map each `.env` variable to the corresponding entry in `koyeb.yaml`:

| `.env` Variable | `koyeb.yaml` Key | Value / Source |
|---|---|---|
| `SECRET_KEY` | `SECRET_KEY` | Koyeb secret `secret-key` (set via dashboard or CLI) |
| `FLASK_ENV` | `FLASK_ENV` | Hardcoded to `production` |
| `DATABASE_PATH` | `DATABASE_PATH` | `/tmp/booking_site.db` |
| — | `PYTHONUNBUFFERED` | `1` (set in koyeb.yaml and Dockerfile) |

- [ ] Create the `secret-key` secret in Koyeb:
  ```bash
  koyeb secrets create secret-key --value "$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  ```
- [ ] Verify all env vars are present in `koyeb.yaml` under `services[0].env`.
- [ ] Confirm `.env` is **not** committed or shipped in the Docker image (it is for local dev only).

## 3. startup.sh .env Sourcing

`startup.sh` is for **local development only** (creates a venv, sources `.env`, installs deps).

The Docker image uses `entrypoint.sh` instead, which:
- Auto-generates a random `SECRET_KEY` if none is provided.
- Does **not** source `.env` — all config comes from koyeb.yaml env/secrets.

- [ ] Confirm `startup.sh` is not referenced in the Dockerfile or koyeb.yaml.
- [ ] Confirm `entrypoint.sh` is copied and executable in the Dockerfile.

## 4. Deploy to Koyeb

- [ ] Deploy using the Koyeb CLI:
  ```bash
  koyeb service create booking-site \
    --app booking-site \
    --docker fauxtoe/booking-site \
    --port 5000:http \
    --env FLASK_ENV=production \
    --env PYTHONUNBUFFERED=1 \
    --env DATABASE_PATH=/tmp/booking_site.db \
    --env SECRET_KEY=@secret-key
  ```
  Or redeploy an existing service:
  ```bash
  koyeb service redeploy booking-site/booking-site
  ```
- [ ] Wait for the deployment to reach `HEALTHY` status:
  ```bash
  koyeb service get booking-site/booking-site
  ```

## 5. Post-Deploy Smoke Test

- [ ] Hit the health endpoint:
  ```bash
  curl -f https://<your-app>.koyeb.app/health
  ```
- [ ] Verify the login page loads:
  ```bash
  curl -s -o /dev/null -w "%{http_code}" https://<your-app>.koyeb.app/login
  # Expected: 200
  ```
- [ ] Test a login round-trip:
  ```bash
  curl -s -c cookies.txt -X POST https://<your-app>.koyeb.app/login \
    -d "email=admin@vacationrental.com&password=admin123" \
    -w "\n%{http_code}" -o /dev/null
  # Expected: 302 (redirect to dashboard)
  ```
- [ ] Clean up:
  ```bash
  rm -f cookies.txt
  ```
