from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient


def test_register_success(client: TestClient) -> None:
    """Test successful user registration returns 201 and never leaks password_hash."""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "student@example.com",
            "password": "supersecretpassword",
            "display_name": "Recall Student",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "student@example.com"
    assert data["display_name"] == "Recall Student"
    assert "id" in data
    assert "created_at" in data
    # Password hash must NEVER be returned in response
    assert "password_hash" not in data
    assert "password" not in data


def test_register_duplicate_email(client: TestClient) -> None:
    """Test that registering an already registered email (case-insensitive) returns 409 EMAIL_EXISTS."""
    # First registration
    client.post(
        "/api/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "supersecretpassword",
            "display_name": "First User",
        },
    )

    # Second registration with uppercase variant
    response = client.post(
        "/api/auth/register",
        json={
            "email": "DUPLICATE@example.com",
            "password": "anothersecretpassword",
            "display_name": "Second User",
        },
    )
    assert response.status_code == 409
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "EMAIL_EXISTS"


def test_register_password_too_long(client: TestClient) -> None:
    """Test that passwords exceeding bcrypt's 72-byte limit are rejected with 400 PASSWORD_TOO_LONG."""
    long_password = "a" * 73
    response = client.post(
        "/api/auth/register",
        json={
            "email": "toolong@example.com",
            "password": long_password,
            "display_name": "Long Password User",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "PASSWORD_TOO_LONG"


def test_register_password_too_short(client: TestClient) -> None:
    """Test that passwords shorter than 8 characters return 422 VALIDATION_ERROR."""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "short@example.com",
            "password": "short",
            "display_name": "Short Password User",
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_login_success(client: TestClient) -> None:
    """Test valid login returns 200 and access_token."""
    client.post(
        "/api/auth/register",
        json={
            "email": "loginuser@example.com",
            "password": "validpassword123",
            "display_name": "Login User",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email": "LOGINUSER@example.com",
            "password": "validpassword123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20


def test_login_wrong_password(client: TestClient) -> None:
    """Test login with wrong password returns 401 INVALID_CREDENTIALS."""
    client.post(
        "/api/auth/register",
        json={
            "email": "wrongpass@example.com",
            "password": "correctpassword",
            "display_name": "Wrong Pass User",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email": "wrongpass@example.com",
            "password": "incorrectpassword",
        },
    )
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_nonexistent_email(client: TestClient) -> None:
    """Test login with nonexistent email returns 401 INVALID_CREDENTIALS."""
    response = client.post(
        "/api/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "anypassword",
        },
    )
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_authenticated(client: TestClient) -> None:
    """Test GET /api/me returns current user info when valid Bearer token is provided."""
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "me@example.com",
            "password": "securepassword",
            "display_name": "Me User",
        },
    )
    assert reg.status_code == 201

    login = client.post(
        "/api/auth/login",
        json={
            "email": "me@example.com",
            "password": "securepassword",
        },
    )
    token = login.json()["access_token"]

    response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"
    assert data["display_name"] == "Me User"
    assert "password_hash" not in data


def test_me_update_profile(client: TestClient) -> None:
    """Test PATCH /api/me updates display_name and exam_date."""
    client.post(
        "/api/auth/register",
        json={
            "email": "patchme@example.com",
            "password": "securepassword",
            "display_name": "Old Name",
        },
    )
    login = client.post(
        "/api/auth/login",
        json={
            "email": "patchme@example.com",
            "password": "securepassword",
        },
    )
    token = login.json()["access_token"]

    exam_date_str = "2026-12-15T09:00:00Z"
    patch_res = client.patch(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "display_name": "Updated Name",
            "exam_date": exam_date_str,
        },
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["display_name"] == "Updated Name"
    assert data["exam_date"] is not None


def test_me_unauthenticated(client: TestClient) -> None:
    """Test GET /api/me without Authorization header returns 401 INVALID_TOKEN."""
    response = client.get("/api/me")
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_TOKEN"


def test_me_invalid_token(client: TestClient) -> None:
    """Test GET /api/me with invalid Authorization header returns 401 INVALID_TOKEN."""
    response = client.get(
        "/api/me",
        headers={"Authorization": "Bearer invalid.fake.token"},
    )
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_TOKEN"
