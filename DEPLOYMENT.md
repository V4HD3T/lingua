# Deployment guide

Three supported paths, cheapest-to-run first. All of them assume the
v0.1.0 pieces: the two Dockerfiles, `docker-compose.yml`, the `/health`
endpoint (rate-limit-exempt on purpose), and startup migrations
(`init_db` runs `alembic upgrade head` automatically).

## 1. Local, one command (docker compose)

```bash
docker compose up --build
```

- Frontend: http://localhost:8080 · Backend + Swagger: http://localhost:8000/docs
- SQLite persists on the `lingua-data` volume; Redis caching is on.
- `docker compose down -v` wipes the data volume for a fresh start.

## 2. Backend on Railway (or Render / Fly.io)

All three detect `backend/Dockerfile` automatically; point the service's
root directory at `backend/`.

**Environment variables** (Railway: *Variables* tab):

| Variable | Value | Why |
| --- | --- | --- |
| `SECRET_KEY` | output of `python -c "import secrets; print(secrets.token_urlsafe(64))"` | JWT signing. The app logs a loud warning if left on the default. |
| `DATABASE_URL` | `sqlite:////data/app.db` **+ attach a volume mounted at `/data`** | Without a volume, SQLite lives on the container filesystem and every deploy wipes it. |
| `FRONTEND_BASE_URL` | your Vercel URL, e.g. `https://lingua-xyz.vercel.app` | Base for verification/reset links in emails. |
| `CORS_ALLOWED_ORIGINS` | same Vercel URL (comma-separated if several) | Browser origins allowed to call the API. Setting it replaces the development defaults entirely — deployments get exactly what they ask for. |
| `REDIS_URL` | provision the platform's Redis add-on and paste its URL | Optional -- the cache silently disables itself when unset. |
| `USE_MOCK_TRANSLATION` | `true` for now | The real NLLB model needs ~3&nbsp;GB and a beefier instance; keep the mock until that's sized. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_FROM_ADDRESS` | your mail provider's values | Unset = mock email service: verification/reset emails are logged, not sent. Fine for a demo, not for real users. |

**Postgres instead of SQLite** (recommended once real users exist):
uncomment `psycopg2-binary` in `backend/requirements.txt`, set
`DATABASE_URL` to the platform's Postgres URL. Migrations run at startup
either way. *Honesty note: the migration chain is exercised in CI against
SQLite; the first Postgres deploy deserves a manual smoke test.*

## 3. Frontend on Vercel (or Netlify)

- Import the repo, set the project root to `frontend/`. Vite is
  auto-detected; `frontend/vercel.json` provides the SPA fallback rewrite
  (without it, refreshing `/courses/1` 404s).
- Set **`VITE_API_URL`** to the backend's public URL (e.g.
  `https://lingua-backend.up.railway.app`). This is a **build-time**
  value -- changing it means redeploying, not just restarting.
- Then set the backend's `FRONTEND_BASE_URL` to the Vercel URL (the two
  variables point at each other).

## Loading course content

The deployed database starts with only the seeded demo course. Load the
shipped content packs (Turkish A1, Spanish A2) once per environment:

```bash
python scripts/import_content.py          # inside the backend container/service
```

Idempotent, so re-running after a redeploy is safe. See
`backend/README.md` for the pack format.

## Secrets management rules

- `.env` files never enter git (`.gitignore` already covers them);
  `\.env.example` documents every variable with safe defaults.
- One secret per environment: local, staging, and prod each get their own
  `SECRET_KEY`. Rotating it invalidates all outstanding JWTs -- that's a
  feature (instant global logout), just do it knowingly.
- The startup warning about a default `SECRET_KEY` is the last line of
  defense, not the process.

## Post-deploy checklist

1. `GET /health` returns 200 with the expected version.
2. Register -> the verification email arrives (or, with mock email, its
   link appears in the backend logs).
3. A translate request from the deployed frontend succeeds (proves CORS
   and `VITE_API_URL` are consistent).
4. `docker compose logs backend` / platform logs show **no**
   `insecure_default_secret_key` warning.
5. The app is installable: open the deployed frontend on a phone and
   check the browser offers "Add to home screen" (PWA manifest + service
   worker are served over HTTPS).
6. Rate limiting sees real client IPs: hit an auth endpoint 6x and check
   the 429 logs a real address, not the proxy's (the Dockerfile's
   `--proxy-headers` handles this on Railway/Render/Fly).
