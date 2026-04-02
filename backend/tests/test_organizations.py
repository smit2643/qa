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


def test_list_orgs_returns_personal_org(client, auth_headers):
    res = client.get("/api/v1/organizations", headers=auth_headers)
    assert res.status_code == 200
    orgs = res.json()
    assert len(orgs) == 1
    assert "Owner User" in orgs[0]["name"]


def test_get_org_by_id(client, auth_headers):
    orgs = client.get("/api/v1/organizations", headers=auth_headers).json()
    org_id = orgs[0]["id"]
    res = client.get(f"/api/v1/organizations/{org_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["id"] == org_id


def test_update_org_name(client, auth_headers):
    org_id = client.get("/api/v1/organizations", headers=auth_headers).json()[0]["id"]
    res = client.patch(f"/api/v1/organizations/{org_id}", json={"name": "New Name"}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "New Name"


def test_list_members_shows_owner(client, auth_headers):
    org_id = client.get("/api/v1/organizations", headers=auth_headers).json()[0]["id"]
    res = client.get(f"/api/v1/organizations/{org_id}/members", headers=auth_headers)
    assert res.status_code == 200
    members = res.json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"
    assert members[0]["user_email"] == "owner@example.com"


def test_invite_member(client, auth_headers):
    # Create a second user to invite
    client.post("/api/v1/auth/signup", json={
        "email": "member@example.com", "name": "Member", "password": "securepass123"
    })
    org_id = client.get("/api/v1/organizations", headers=auth_headers).json()[0]["id"]
    res = client.post(f"/api/v1/organizations/{org_id}/members", json={
        "email": "member@example.com", "role": "member"
    }, headers=auth_headers)
    assert res.status_code == 200

    members = client.get(f"/api/v1/organizations/{org_id}/members", headers=auth_headers).json()
    assert len(members) == 2


def test_invite_nonexistent_user_returns_404(client, auth_headers):
    org_id = client.get("/api/v1/organizations", headers=auth_headers).json()[0]["id"]
    res = client.post(f"/api/v1/organizations/{org_id}/members", json={
        "email": "nobody@example.com", "role": "member"
    }, headers=auth_headers)
    assert res.status_code == 404


def test_remove_member(client, auth_headers):
    client.post("/api/v1/auth/signup", json={
        "email": "todelete@example.com", "name": "ToDelete", "password": "securepass123"
    })
    org_id = client.get("/api/v1/organizations", headers=auth_headers).json()[0]["id"]
    members_before = client.post(f"/api/v1/organizations/{org_id}/members", json={
        "email": "todelete@example.com", "role": "member"
    }, headers=auth_headers)

    # Get the new member's user_id
    members = client.get(f"/api/v1/organizations/{org_id}/members", headers=auth_headers).json()
    member = next(m for m in members if m["user_email"] == "todelete@example.com")

    res = client.delete(f"/api/v1/organizations/{org_id}/members/{member['user_id']}", headers=auth_headers)
    assert res.status_code == 204


def test_viewer_cannot_update_org(client, auth_headers):
    # Create viewer user
    client.post("/api/v1/auth/signup", json={
        "email": "viewer@example.com", "name": "Viewer", "password": "securepass123"
    })
    org_id = client.get("/api/v1/organizations", headers=auth_headers).json()[0]["id"]
    client.post(f"/api/v1/organizations/{org_id}/members", json={
        "email": "viewer@example.com", "role": "viewer"
    }, headers=auth_headers)

    # Login as viewer
    viewer_token = client.post("/api/v1/auth/login", json={
        "email": "viewer@example.com", "password": "securepass123"
    }).json()["access_token"]

    res = client.patch(f"/api/v1/organizations/{org_id}",
        json={"name": "Hacked"},
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert res.status_code == 403


def test_oauth_github_login_redirects(client):
    """When GitHub OAuth is not configured, returns 501."""
    res = client.get("/api/v1/auth/github/login", follow_redirects=False)
    # Either 501 (not configured) or 307 redirect (configured)
    assert res.status_code in (307, 501)


def test_oauth_google_login_redirects(client):
    res = client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert res.status_code in (307, 501)
