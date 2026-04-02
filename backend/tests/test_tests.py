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
def suite_setup(client, auth_headers):
    org_id = client.get("/api/v1/organizations", headers=auth_headers).json()[0]["id"]
    project_res = client.post("/api/v1/projects", json={
        "name": "Test Case Project",
        "target_url": "https://example.com",
        "organization_id": org_id,
    }, headers=auth_headers)
    assert project_res.status_code == 200
    project_id = project_res.json()["id"]

    suite_res = client.post("/api/v1/suites", json={
        "name": "Test Case Suite",
        "project_id": project_id,
    }, headers=auth_headers)
    assert suite_res.status_code == 200
    suite_id = suite_res.json()["id"]

    return auth_headers, suite_id


def test_create_test_in_accessible_suite(client, suite_setup):
    auth_headers, suite_id = suite_setup
    res = client.post("/api/v1/tests", json={
        "name": "Login Test",
        "suite_id": suite_id,
    }, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Login Test"
    assert data["suite_id"] == suite_id
    assert data["version"] == 1


def test_create_test_in_inaccessible_suite(client, suite_setup):
    _, suite_id = suite_setup
    # Create a second user (not in the org) and try to create a test
    client.post("/api/v1/auth/signup", json={
        "email": "stranger@example.com", "name": "Stranger", "password": "securepass123"
    })
    stranger_token = client.post("/api/v1/auth/login", json={
        "email": "stranger@example.com", "password": "securepass123"
    }).json()["access_token"]
    stranger_headers = {"Authorization": f"Bearer {stranger_token}"}

    res = client.post("/api/v1/tests", json={
        "name": "Hacked Test",
        "suite_id": suite_id,
    }, headers=stranger_headers)
    assert res.status_code == 403


def test_list_tests_returns_created_test(client, suite_setup):
    auth_headers, suite_id = suite_setup
    create_res = client.post("/api/v1/tests", json={
        "name": "Listed Test",
        "suite_id": suite_id,
    }, headers=auth_headers)
    assert create_res.status_code == 200
    created_id = create_res.json()["id"]

    res = client.get(f"/api/v1/suites/{suite_id}/tests", headers=auth_headers)
    assert res.status_code == 200
    ids = [t["id"] for t in res.json()]
    assert created_id in ids


def test_get_test_by_id(client, suite_setup):
    auth_headers, suite_id = suite_setup
    create_res = client.post("/api/v1/tests", json={
        "name": "Gettable Test",
        "suite_id": suite_id,
    }, headers=auth_headers)
    assert create_res.status_code == 200
    test_id = create_res.json()["id"]

    res = client.get(f"/api/v1/tests/{test_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["id"] == test_id


def test_update_test_name_no_version_bump(client, suite_setup):
    auth_headers, suite_id = suite_setup
    create_res = client.post("/api/v1/tests", json={
        "name": "Original Name",
        "suite_id": suite_id,
    }, headers=auth_headers)
    assert create_res.status_code == 200
    test_id = create_res.json()["id"]

    res = client.patch(f"/api/v1/tests/{test_id}", json={
        "name": "Updated Name",
    }, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Updated Name"
    assert data["version"] == 1


def test_update_test_code_bumps_version(client, suite_setup):
    auth_headers, suite_id = suite_setup
    create_res = client.post("/api/v1/tests", json={
        "name": "Code Test",
        "suite_id": suite_id,
    }, headers=auth_headers)
    assert create_res.status_code == 200
    test_id = create_res.json()["id"]

    res = client.patch(f"/api/v1/tests/{test_id}", json={
        "code": "console.log('hello')",
    }, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["version"] == 2


def test_update_test_code_twice_bumps_version_to_3(client, suite_setup):
    auth_headers, suite_id = suite_setup
    create_res = client.post("/api/v1/tests", json={
        "name": "Version Test",
        "suite_id": suite_id,
    }, headers=auth_headers)
    assert create_res.status_code == 200
    test_id = create_res.json()["id"]

    client.patch(f"/api/v1/tests/{test_id}", json={"code": "v1 code"}, headers=auth_headers)
    res = client.patch(f"/api/v1/tests/{test_id}", json={"code": "v2 code"}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["version"] == 3


def test_delete_test_then_get_returns_404(client, suite_setup):
    auth_headers, suite_id = suite_setup
    create_res = client.post("/api/v1/tests", json={
        "name": "Deletable Test",
        "suite_id": suite_id,
    }, headers=auth_headers)
    assert create_res.status_code == 200
    test_id = create_res.json()["id"]

    del_res = client.delete(f"/api/v1/tests/{test_id}", headers=auth_headers)
    assert del_res.status_code in (200, 204)

    get_res = client.get(f"/api/v1/tests/{test_id}", headers=auth_headers)
    assert get_res.status_code == 404
