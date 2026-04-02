import io
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
def org_id(client, auth_headers):
    orgs = client.get("/api/v1/organizations", headers=auth_headers).json()
    return orgs[0]["id"]


@pytest.fixture
def project(client, auth_headers, org_id):
    res = client.post("/api/v1/projects", json={
        "name": "My Project",
        "target_url": "https://example.com",
        "organization_id": org_id,
    }, headers=auth_headers)
    assert res.status_code == 200
    return res.json()


def test_create_project_returns_api_key(client, auth_headers, org_id):
    res = client.post("/api/v1/projects", json={
        "name": "Test Project",
        "target_url": "https://example.com",
        "organization_id": org_id,
    }, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Test Project"
    assert "api_key" in data
    assert len(data["api_key"]) == 64


def test_create_project_in_foreign_org_returns_403(client, auth_headers):
    # Create a second user and get their org
    client.post("/api/v1/auth/signup", json={
        "email": "other@example.com", "name": "Other User", "password": "securepass123"
    })
    other_token = client.post("/api/v1/auth/login", json={
        "email": "other@example.com", "password": "securepass123"
    }).json()["access_token"]
    other_org_id = client.get(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {other_token}"}
    ).json()[0]["id"]

    res = client.post("/api/v1/projects", json={
        "name": "Hacked Project",
        "target_url": "https://example.com",
        "organization_id": other_org_id,
    }, headers=auth_headers)
    assert res.status_code == 403


def test_list_projects_returns_created_project(client, auth_headers, org_id, project):
    res = client.get(f"/api/v1/organizations/{org_id}/projects", headers=auth_headers)
    assert res.status_code == 200
    ids = [p["id"] for p in res.json()]
    assert project["id"] in ids


def test_get_project_by_id(client, auth_headers, project):
    res = client.get(f"/api/v1/projects/{project['id']}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["id"] == project["id"]


def test_get_project_in_foreign_org_returns_403(client, auth_headers, project):
    # Create another user who is not in the org
    client.post("/api/v1/auth/signup", json={
        "email": "stranger@example.com", "name": "Stranger", "password": "securepass123"
    })
    stranger_token = client.post("/api/v1/auth/login", json={
        "email": "stranger@example.com", "password": "securepass123"
    }).json()["access_token"]

    res = client.get(
        f"/api/v1/projects/{project['id']}",
        headers={"Authorization": f"Bearer {stranger_token}"}
    )
    assert res.status_code == 403


def test_update_project_name(client, auth_headers, project):
    res = client.patch(f"/api/v1/projects/{project['id']}", json={
        "name": "Updated Name"
    }, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Updated Name"


def test_delete_project_then_get_returns_404(client, auth_headers, project):
    res = client.delete(f"/api/v1/projects/{project['id']}", headers=auth_headers)
    assert res.status_code in (200, 204)
    res = client.get(f"/api/v1/projects/{project['id']}", headers=auth_headers)
    assert res.status_code == 404


def test_rotate_api_key_returns_new_key(client, auth_headers, project):
    old_key = project["api_key"]
    res = client.post(f"/api/v1/projects/{project['id']}/rotate-api-key", headers=auth_headers)
    assert res.status_code == 200
    new_key = res.json()["api_key"]
    assert new_key != old_key
    assert len(new_key) == 64


def test_upload_storage_state(client, auth_headers, project):
    project_id = project["id"]
    files = {"file": ("storageState.json", io.BytesIO(b'{"cookies": [], "origins": []}'), "application/json")}
    res = client.post(f"/api/v1/projects/{project_id}/storage-state", files=files, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["storage_state_json"] is not None
    assert "cookies" in data["storage_state_json"]


def test_upload_storage_state_invalid_json(client, auth_headers, project):
    project_id = project["id"]
    files = {"file": ("storageState.json", io.BytesIO(b'not valid json!!!'), "application/json")}
    res = client.post(f"/api/v1/projects/{project_id}/storage-state", files=files, headers=auth_headers)
    assert res.status_code == 422


def test_delete_storage_state(client, auth_headers, project):
    project_id = project["id"]
    # First upload
    files = {"file": ("storageState.json", io.BytesIO(b'{"cookies": [], "origins": []}'), "application/json")}
    res = client.post(f"/api/v1/projects/{project_id}/storage-state", files=files, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["storage_state_json"] is not None
    # Then delete
    res = client.delete(f"/api/v1/projects/{project_id}/storage-state", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["message"] == "Storage state removed"
    # Verify it's gone
    res = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["storage_state_json"] is None
