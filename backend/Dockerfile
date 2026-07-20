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

# --proxy-headers so client_ip() (rate limiting, security logs) sees the
# real client address behind the TLS-terminating proxies of
# Railway/Render/Fly. --forwarded-allow-ips='*' trusts any upstream to
# set those headers -- correct on those platforms (their proxy is always
# in front) and harmless in local compose (nothing sends the headers);
# do NOT expose this container directly to the internet without a proxy.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
