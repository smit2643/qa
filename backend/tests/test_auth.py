import pytest


def test_signup_returns_token(client):
    res = client.post("/api/v1/auth/signup", json={
        "email": "alice@example.com",
        "name": "Alice",
        "password": "securepass123",
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_signup_duplicate_email_returns_400(client):
    payload = {"email": "bob@example.com", "name": "Bob", "password": "securepass123"}
    client.post("/api/v1/auth/signup", json=payload)
    res = client.post("/api/v1/auth/signup", json=payload)
    assert res.status_code == 400
    assert "already registered" in res.json()["detail"]


def test_signup_weak_password_returns_422(client):
    res = client.post("/api/v1/auth/signup", json={
        "email": "weak@example.com", "name": "Weak", "password": "short"
    })
    assert res.status_code == 422


def test_login_correct_credentials(client):
    client.post("/api/v1/auth/signup", json={
        "email": "carol@example.com", "name": "Carol", "password": "securepass123"
    })
    res = client.post("/api/v1/auth/login", json={
        "email": "carol@example.com", "password": "securepass123"
    })
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password_returns_401(client):
    client.post("/api/v1/auth/signup", json={
        "email": "dave@example.com", "name": "Dave", "password": "correctpass123"
    })
    res = client.post("/api/v1/auth/login", json={
        "email": "dave@example.com", "password": "wrongpassword"
    })
    assert res.status_code == 401


def test_me_returns_user(client):
    signup_res = client.post("/api/v1/auth/signup", json={
        "email": "eve@example.com", "name": "Eve", "password": "securepass123"
    })
    token = signup_res.json()["access_token"]
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert data["email"] == "eve@example.com"
    assert data["name"] == "Eve"
    assert data["is_active"] is True


def test_me_without_token_returns_403(client):
    res = client.get("/api/v1/auth/me")
    assert res.status_code in (401, 403)


def test_me_with_invalid_token_returns_401(client):
    res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert res.status_code == 401
