import pytest


@pytest.fixture
def test_setup(client):
    # Create user and login
    client.post("/api/v1/auth/signup", json={
        "email": "stepuser@example.com",
        "name": "Step User",
        "password": "securepass123",
    })
    res = client.post("/api/v1/auth/login", json={
        "email": "stepuser@example.com",
        "password": "securepass123",
    })
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get auto-created org
    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]

    # Create project
    project_res = client.post("/api/v1/projects", json={
        "name": "Step Project",
        "target_url": "https://example.com",
        "organization_id": org_id,
    }, headers=headers)
    assert project_res.status_code == 200
    project_id = project_res.json()["id"]

    # Create suite
    suite_res = client.post("/api/v1/suites", json={
        "name": "Step Suite",
        "project_id": project_id,
    }, headers=headers)
    assert suite_res.status_code == 200
    suite_id = suite_res.json()["id"]

    # Create test case
    test_res = client.post("/api/v1/tests", json={
        "name": "Step Test Case",
        "suite_id": suite_id,
    }, headers=headers)
    assert test_res.status_code == 200
    test_id = test_res.json()["id"]

    return headers, test_id


def test_create_step_in_accessible_test(client, test_setup):
    headers, test_id = test_setup
    res = client.post("/api/v1/steps", json={
        "test_id": test_id,
        "order": 0,
        "action": "click",
        "selector": "#submit-btn",
        "description": "Click submit",
    }, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["test_id"] == test_id
    assert data["action"] == "click"
    assert data["selector"] == "#submit-btn"
    assert data["order"] == 0
    assert data["is_assertion"] is False
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_list_steps_returns_in_order(client, test_setup):
    headers, test_id = test_setup
    # Create two steps
    client.post("/api/v1/steps", json={
        "test_id": test_id, "order": 0, "action": "navigate", "value": "https://example.com",
    }, headers=headers)
    client.post("/api/v1/steps", json={
        "test_id": test_id, "order": 1, "action": "click", "selector": "#btn",
    }, headers=headers)

    res = client.get(f"/api/v1/tests/{test_id}/steps", headers=headers)
    assert res.status_code == 200
    steps = res.json()
    assert len(steps) == 2
    assert steps[0]["order"] == 0
    assert steps[1]["order"] == 1
    assert steps[0]["action"] == "navigate"
    assert steps[1]["action"] == "click"


def test_get_step_by_id(client, test_setup):
    headers, test_id = test_setup
    create_res = client.post("/api/v1/steps", json={
        "test_id": test_id, "order": 0, "action": "wait", "value": "1000",
    }, headers=headers)
    assert create_res.status_code == 200
    step_id = create_res.json()["id"]

    res = client.get(f"/api/v1/steps/{step_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["id"] == step_id
    assert res.json()["action"] == "wait"


def test_update_step_selector(client, test_setup):
    headers, test_id = test_setup
    create_res = client.post("/api/v1/steps", json={
        "test_id": test_id, "order": 0, "action": "click", "selector": "#old-btn",
    }, headers=headers)
    assert create_res.status_code == 200
    step_id = create_res.json()["id"]

    res = client.patch(f"/api/v1/steps/{step_id}", json={
        "selector": "#new-btn",
    }, headers=headers)
    assert res.status_code == 200
    assert res.json()["selector"] == "#new-btn"
    assert res.json()["action"] == "click"


def test_delete_step_then_list_is_empty(client, test_setup):
    headers, test_id = test_setup
    create_res = client.post("/api/v1/steps", json={
        "test_id": test_id, "order": 0, "action": "click", "selector": "#btn",
    }, headers=headers)
    assert create_res.status_code == 200
    step_id = create_res.json()["id"]

    del_res = client.delete(f"/api/v1/steps/{step_id}", headers=headers)
    assert del_res.status_code in (200, 204)

    list_res = client.get(f"/api/v1/tests/{test_id}/steps", headers=headers)
    assert list_res.status_code == 200
    assert list_res.json() == []


def test_reorder_steps(client, test_setup):
    headers, test_id = test_setup
    # Create 3 steps in order 0, 1, 2
    ids = []
    for i, action in enumerate(["navigate", "click", "assert"]):
        res = client.post("/api/v1/steps", json={
            "test_id": test_id, "order": i, "action": action,
        }, headers=headers)
        assert res.status_code == 200
        ids.append(res.json()["id"])

    # Reorder: put them in reverse (2, 1, 0)
    new_order = [ids[2], ids[1], ids[0]]
    reorder_res = client.post(f"/api/v1/tests/{test_id}/steps/reorder", json={
        "step_ids": new_order,
    }, headers=headers)
    assert reorder_res.status_code == 200
    returned = reorder_res.json()
    assert len(returned) == 3
    # First in result should have order=0
    assert returned[0]["id"] == ids[2]
    assert returned[0]["order"] == 0
    assert returned[1]["id"] == ids[1]
    assert returned[1]["order"] == 1
    assert returned[2]["id"] == ids[0]
    assert returned[2]["order"] == 2

    # Verify via list endpoint
    list_res = client.get(f"/api/v1/tests/{test_id}/steps", headers=headers)
    assert list_res.status_code == 200
    steps = list_res.json()
    assert steps[0]["id"] == ids[2]
    assert steps[0]["order"] == 0


def test_create_step_in_inaccessible_test(client, test_setup):
    _, test_id = test_setup
    # Create a stranger user
    client.post("/api/v1/auth/signup", json={
        "email": "stranger_steps@example.com",
        "name": "Stranger",
        "password": "securepass123",
    })
    stranger_token = client.post("/api/v1/auth/login", json={
        "email": "stranger_steps@example.com",
        "password": "securepass123",
    }).json()["access_token"]
    stranger_headers = {"Authorization": f"Bearer {stranger_token}"}

    res = client.post("/api/v1/steps", json={
        "test_id": test_id, "order": 0, "action": "click",
    }, headers=stranger_headers)
    assert res.status_code == 403
