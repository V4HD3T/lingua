"""Guards for cross-boundary contracts that unit tests can't see (v0.1.3
post-release scan).

Each test here exists because the corresponding mistake shipped once: a
CORS allowlist that rejected the origin the E2E suite actually browses
from, and a Docker image that omitted the content packs its own
deployment guide told operators to import."""

from pathlib import Path

from app.config import Settings
from app.main import docs_urls
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


# --- API documentation exposure (v0.1.10) -----------------------------------


def test_api_docs_are_off_unless_asked_for():
    """The whole point of the default. A deployment that configures
    nothing must not publish a map of its own API -- admin routes,
    request shapes and validation rules included."""
    assert Settings().enable_api_docs is False


def test_disabling_docs_removes_the_schema_too():
    """Hiding the UI while leaving /openapi.json up would be theatre: the
    schema is the part worth having."""
    assert docs_urls(False) == {"docs_url": None, "redoc_url": None, "openapi_url": None}


def test_enabling_docs_restores_all_three_routes():
    assert docs_urls(True) == {
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
    }


def test_running_app_serves_no_docs_by_default(client):
    # The app object under test was built with the default settings.
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, f"{path} is exposed"


def test_development_setups_switch_docs_back_on():
    """backend/README.md's setup step is `cp .env.example .env`, and the
    READMEs point at Swagger under docker compose. If either stopped
    enabling it, the code default would silently take the documented dev
    experience away."""
    env_example = (BACKEND_DIR / ".env.example").read_text(encoding="utf-8")
    compose = (BACKEND_DIR.parent / "docker-compose.yml").read_text(encoding="utf-8")
    assert "ENABLE_API_DOCS=true" in env_example
    assert "ENABLE_API_DOCS" in compose


# --- content packs reach the runtime ----------------------------------------


def test_content_packs_are_present_and_discoverable():
    assert CONTENT_DIR.is_dir(), f"content directory missing at {CONTENT_DIR}"
    assert available_packs(), "no content packs found"


# --- the image must not hand X-Forwarded-For back to uvicorn (v0.1.4) ------


def test_docker_image_does_not_blanket_trust_forwarded_headers():
    """`--forwarded-allow-ips "*"` makes uvicorn overwrite request.client
    with the leftmost X-Forwarded-For entry -- which the caller writes.
    That turned every per-IP rate limit into a suggestion. The app reads
    the chain itself now (TRUSTED_PROXY_HOPS); this guards against the
    flag being reinstated as an apparently-innocent 'see real client IPs
    behind the proxy' fix."""
    dockerfile = (BACKEND_DIR / "Dockerfile").read_text()
    cmd = [line for line in dockerfile.splitlines() if line.startswith("CMD")]
    assert cmd, "no CMD line found in the Dockerfile"
    assert "--forwarded-allow-ips" not in cmd[0], (
        "uvicorn is trusting forwarded headers again -- per-IP rate limiting "
        "is only as trustworthy as whatever this flag allows"
    )


def test_deployment_guide_documents_the_proxy_hop_setting():
    """The old guide told operators the Dockerfile's --proxy-headers
    handled real client IPs for them. It no longer does, and a deployment
    that misses this silently rate-limits every visitor as one client."""
    guide = (BACKEND_DIR.parent / "DEPLOYMENT.md").read_text(encoding="utf-8")
    assert "TRUSTED_PROXY_HOPS" in guide


def test_docker_image_ships_the_content_directory():
    """DEPLOYMENT.md instructs operators to run scripts/import_content.py
    inside the backend container. If the image doesn't carry content/, the
    script finds nothing -- and used to exit 0, so the deploy log showed a
    successful import that imported nothing."""
    dockerfile = (BACKEND_DIR / "Dockerfile").read_text()
    assert "COPY content" in dockerfile
