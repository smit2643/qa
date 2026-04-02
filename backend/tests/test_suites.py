import pytest


@pytest.fixture
def auth_headers(client):
    client.post("/api/v1/auth/signup", json={
        "email": "owner@example.com", "name": "Owner User", "password": "securepass123"
    })
    res = client.post("/api/v1/auth/login", json={
        "email": "owner@example.com", "password": "securepass123"
    })
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def project(client, auth_headers):
    org_id = client.get("/api/v1/organizations", headers=auth_headers).json()[0]["id"]
    res = client.post("/api/v1/projects", json={
        "name": "Suite Test Project",
        "target_url": "https://example.com",
        "organization_id": org_id,
    }, headers=auth_headers)
    assert res.status_code == 200
    return res.json()


@pytest.fixture
def suite(client, auth_headers, project):
    res = client.post("/api/v1/suites", json={
        "name": "My Suite",
        "project_id": project["id"],
    }, headers=auth_headers)
    assert res.status_code == 200
    return res.json()


def test_create_suite_in_accessible_project(client, auth_headers, project):
    res = client.post("/api/v1/suites", json={
        "name": "Smoke Tests",
        "project_id": project["id"],
    }, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Smoke Tests"
    assert data["project_id"] == project["id"]


def test_list_suites_returns_created_suite(client, auth_headers, project, suite):
    res = client.get(f"/api/v1/projects/{project['id']}/suites", headers=auth_headers)
    assert res.status_code == 200
    ids = [s["id"] for s in res.json()]
    assert suite["id"] in ids


def test_get_suite_by_id(client, auth_headers, suite):
    res = client.get(f"/api/v1/suites/{suite['id']}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["id"] == suite["id"]


def test_update_suite_name(client, auth_headers, suite):
    res = client.patch(f"/api/v1/suites/{suite['id']}", json={
        "name": "Renamed Suite"
    }, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Renamed Suite"


def test_delete_suite_then_get_returns_404(client, auth_headers, suite):
    res = client.delete(f"/api/v1/suites/{suite['id']}", headers=auth_headers)
    assert res.status_code in (200, 204)
    res = client.get(f"/api/v1/suites/{suite['id']}", headers=auth_headers)
    assert res.status_code == 404
