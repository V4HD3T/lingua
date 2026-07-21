"""Guards for cross-boundary contracts that unit tests can't see (v0.1.3
post-release scan).

Each test here exists because the corresponding mistake shipped once: a
CORS allowlist that rejected the origin the E2E suite actually browses
from, and a Docker image that omitted the content packs its own
deployment guide told operators to import."""

from pathlib import Path

from app.config import Settings
from app.services.content_import import CONTENT_DIR, available_packs

BACKEND_DIR = Path(__file__).resolve().parent.parent


# --- CORS allowlist ---------------------------------------------------------


def test_dev_default_allows_both_spellings_of_the_dev_server():
    # To a browser these are different origins; Playwright browses the
    # numeric one while the app's default config named the other.
    origins = Settings(cors_allowed_origins="").cors_origins
    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins


def test_dev_default_includes_the_configured_frontend_origin():
    origins = Settings(
        cors_allowed_origins="", frontend_base_url="http://localhost:8080"
    ).cors_origins
    assert "http://localhost:8080" in origins  # docker-compose serves the SPA here


def test_explicit_setting_wins_and_excludes_dev_origins():
    origins = Settings(cors_allowed_origins="https://lingua.example.app").cors_origins
    assert origins == ["https://lingua.example.app"]


def test_explicit_setting_parses_a_list():
    origins = Settings(
        cors_allowed_origins="https://a.example, https://b.example"
    ).cors_origins
    assert origins == ["https://a.example", "https://b.example"]


def test_running_app_returns_cors_headers_for_both_dev_origins(client):
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        response = client.get("/courses", headers={"Origin": origin})
        assert response.headers.get("access-control-allow-origin") == origin, (
            f"{origin} was rejected -- browser calls from it would fail silently"
        )


def test_preflight_succeeds_for_an_authenticated_call(client):
    response = client.options(
        "/translate/history",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200


# --- content packs reach the runtime ----------------------------------------


def test_content_packs_are_present_and_discoverable():
    assert CONTENT_DIR.is_dir(), f"content directory missing at {CONTENT_DIR}"
    assert available_packs(), "no content packs found"


def test_docker_image_ships_the_content_directory():
    """DEPLOYMENT.md instructs operators to run scripts/import_content.py
    inside the backend container. If the image doesn't carry content/, the
    script finds nothing -- and used to exit 0, so the deploy log showed a
    successful import that imported nothing."""
    dockerfile = (BACKEND_DIR / "Dockerfile").read_text()
    assert "COPY content" in dockerfile
