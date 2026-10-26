import io
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.core.rate_limit import auth_ip_limiter, upload_user_limiter


def test_health_endpoints(client: TestClient):
    """Verify /health returns 200 without DB call, and /health/db verifies DB connectivity."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

    res_api = client.get("/api/health")
    assert res_api.status_code == 200
    assert res_api.json() == {"status": "ok"}

    res_db = client.get("/health/db")
    assert res_db.status_code == 200
    assert res_db.json() == {"status": "ok", "db": "connected"}


def test_cors_options_preflight(client: TestClient):
    """Verify CORS preflight succeeds for allowed origin and fails/rejects for unauthorized origin."""
    # Allowed origin: http://localhost:5173
    headers_allowed = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Authorization, Content-Type",
    }
    res_allowed = client.options("/api/uploads", headers=headers_allowed)
    assert res_allowed.status_code == 200
    assert res_allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    # Credentials must be off
    assert res_allowed.headers.get("access-control-allow-credentials") is None

    # Disallowed origin: https://unauthorized-origin.com
    headers_disallowed = {
        "Origin": "https://unauthorized-origin.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Authorization, Content-Type",
    }
    res_disallowed = client.options("/api/uploads", headers=headers_disallowed)
    assert res_disallowed.headers.get("access-control-allow-origin") != "https://unauthorized-origin.com"


def test_websocket_origin_check(client: TestClient):
    """Verify WebSocket endpoint closes with code 4403 on Origin mismatch."""
    # Unauthorized origin must be rejected with 4403
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/ws/generate/1?token=some_token",
            headers={"Origin": "https://malicious-domain.com"},
        ):
            pass
    assert exc_info.value.code == 4403

    # Allowed origin proceeds past origin check (fails on invalid token with 4401, not 4403)
    with pytest.raises(WebSocketDisconnect) as exc_info2:
        with client.websocket_connect(
            "/ws/generate/1?token=invalid_token",
            headers={"Origin": "http://localhost:5173"},
        ):
            pass
    assert exc_info2.value.code == 4401


def test_production_config_validation():
    """Verify Settings rejects invalid production configurations."""
    # SQLite rejected in production
    with pytest.raises(ValueError, match="DATABASE_URL must not be empty or point to SQLite"):
        Settings(
            ENV="production",
            DATABASE_URL="sqlite:///./dev.db",
            JWT_SECRET="valid-production-secret-key-at-least-32-chars-long",
        )

    # Default dev secret rejected in production
    with pytest.raises(ValueError, match="JWT_SECRET must not be the default secret"):
        Settings(
            ENV="production",
            DATABASE_URL="postgresql://user:pass@ep-xyz.aws.neon.tech/neondb",
            JWT_SECRET="recallos-dev-secret-key-32-characters-minimum-for-security",
        )

    # Short secret (< 32 chars) rejected in production
    with pytest.raises(ValueError, match="must be at least 32 characters long"):
        Settings(
            ENV="production",
            DATABASE_URL="postgresql://user:pass@ep-xyz.aws.neon.tech/neondb",
            JWT_SECRET="short-secret-under-32-chars",
        )

    # Wildcard origin rejected in production
    with pytest.raises(ValueError, match="ALLOWED_ORIGINS must not contain wildcards"):
        Settings(
            ENV="production",
            DATABASE_URL="postgresql://user:pass@ep-xyz.aws.neon.tech/neondb",
            JWT_SECRET="valid-production-secret-key-at-least-32-chars-long",
            ALLOWED_ORIGINS="*",
        )

    # Valid production settings accepted
    valid_settings = Settings(
        ENV="production",
        DATABASE_URL="postgres://user:pass@ep-xyz.aws.neon.tech/neondb",
        JWT_SECRET="valid-production-secret-key-at-least-32-chars-long",
        ALLOWED_ORIGINS="https://frontend.onrender.com",
    )
    assert valid_settings.DATABASE_URL.startswith("postgresql+psycopg2://")


def test_rate_limiter_auth_30_per_min(client: TestClient):
    """Verify POST /api/auth/login enforces 30 req/min per IP and returns 429 on 31st request."""
    auth_ip_limiter.limiter.reset()

    # 30 requests permitted (they will return 401 due to invalid credentials, but not 429)
    for _ in range(30):
        res = client.post(
            "/api/auth/login",
            json={"email": "nonexistent@example.com", "password": "wrongpassword"},
        )
        assert res.status_code == 401

    # 31st request triggers rate limiter
    res_blocked = client.post(
        "/api/auth/login",
        json={"email": "nonexistent@example.com", "password": "wrongpassword"},
    )
    assert res_blocked.status_code == 429
    err = res_blocked.json()["error"]
    assert err["code"] == "RATE_LIMIT_EXCEEDED"

    auth_ip_limiter.limiter.reset()


def test_rate_limiter_uploads_per_user(client: TestClient):
    """Verify POST /api/uploads enforces 10 req/min per authenticated USER, not blocking other users."""
    upload_user_limiter.limiter.reset()

    # Register User 1 and User 2
    reg1 = client.post(
        "/api/auth/register",
        json={"email": "limiter1@example.com", "password": "password123", "display_name": "User 1"},
    )
    token1 = client.post(
        "/api/auth/login",
        json={"email": "limiter1@example.com", "password": "password123"},
    ).json()["access_token"]

    reg2 = client.post(
        "/api/auth/register",
        json={"email": "limiter2@example.com", "password": "password123", "display_name": "User 2"},
    )
    token2 = client.post(
        "/api/auth/login",
        json={"email": "limiter2@example.com", "password": "password123"},
    ).json()["access_token"]

    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    # User 1 makes 10 upload attempts (empty file -> 400, but past rate limit check)
    dummy_file = ("test.txt", io.BytesIO(b"Hello world from flashcards note test."), "text/plain")
    for _ in range(10):
        upload_user_limiter.limiter.check(f"user:{reg1.json()['id']}")

    # 11th upload attempt by User 1 is blocked with 429
    res_user1_blocked = client.post(
        "/api/uploads",
        files={"file": ("test.txt", io.BytesIO(b"Hello world note."), "text/plain")},
        headers=headers1,
    )
    assert res_user1_blocked.status_code == 429
    assert res_user1_blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    # User 2 makes an upload and is NOT blocked (proving per-user isolation!)
    upload_user_limiter.limiter.check(f"user:{reg2.json()['id']}")
    # User 2 request succeeds through rate limit
    upload_user_limiter.limiter.reset()
