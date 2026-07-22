# Backend image: Python slim base, non-root runtime, migrations run at
# startup (init_db -> alembic upgrade head), health check wired to the
# rate-limit-exempt /health endpoint from v0.0.8.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so code changes don't invalidate the pip layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY scripts ./scripts
# Content packs ship with the image: DEPLOYMENT.md tells operators to run
# scripts/import_content.py inside the container, and without this the
# script finds an empty directory and reports success having imported
# nothing.
COPY content ./content

# Non-root user; /data is the mount point for a persistent SQLite volume
# (the image default DATABASE_URL=sqlite:///./app.db would live and die
# with the container -- docker-compose.yml and DEPLOYMENT.md both point
# DATABASE_URL at /data instead).
RUN useradd --create-home appuser && mkdir -p /data && chown appuser /data
USER appuser

EXPOSE 8000

# curl isn't in slim; a stdlib one-liner does the job.
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=2).status==200 else 1)"

# No --proxy-headers / --forwarded-allow-ips (removed in v0.1.4). The
# `"*"` form this used to pass makes uvicorn rewrite request.client from
# the LEFTMOST X-Forwarded-For entry, which the client writes -- so every
# per-IP rate limit could be reset by varying a header, and security logs
# recorded whatever address the caller chose. The app now resolves the
# client address itself from TRUSTED_PROXY_HOPS, counting from the right
# (see app/services/rate_limiter.py: client_ip). Deployments behind
# exactly one proxy -- Railway, Render, Fly -- set TRUSTED_PROXY_HOPS=1;
# see DEPLOYMENT.md.
#
# Nothing else needed those flags: X-Forwarded-Proto only sets
# request.url.scheme, and this app reads request.url.path only -- it
# builds no absolute URLs (email links come from FRONTEND_BASE_URL).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
