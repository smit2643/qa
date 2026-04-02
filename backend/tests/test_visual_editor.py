"""Tests for Phase 4 Task 19: Visual step editor API."""

import pytest


@pytest.fixture
def editor_setup(client):
    """Create user → org → project → suite → test. Return (headers, test_id)."""
    client.post("/api/v1/auth/signup", json={
        "email": "editor@example.com",
        "name": "Editor User",
        "password": "securepass123",
    })
    res = client.post("/api/v1/auth/login", json={
        "email": "editor@example.com",
        "password": "securepass123",
    })
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]

    proj = client.post("/api/v1/projects", json={
        "name": "Editor Project",
        "target_url": "https://example.com",
        "organization_id": org_id,
    }, headers=headers)
    assert proj.status_code == 200

    suite = client.post("/api/v1/suites", json={
        "name": "Editor Suite",
        "project_id": proj.json()["id"],
    }, headers=headers)
    assert suite.status_code == 200

    test = client.post("/api/v1/tests", json={
        "name": "Editor Test",
        "suite_id": suite.json()["id"],
    }, headers=headers)
    assert test.status_code == 200

    return headers, test.json()["id"]


def _create_step(client, headers, test_id, order, action, selector=None, value=None):
    res = client.post("/api/v1/steps", json={
        "test_id": test_id,
        "order": order,
        "action": action,
        "selector": selector,
        "value": value,
    }, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Bulk replace
# ---------------------------------------------------------------------------

def test_bulk_replace_replaces_all_steps(client, editor_setup):
    headers, test_id = editor_setup
    # Create 2 original steps
    _create_step(client, headers, test_id, 0, "navigate", value="https://old.com")
    _create_step(client, headers, test_id, 1, "click", selector="OldBtn")

    # Replace with 3 new steps
    res = client.put(f"/api/v1/tests/{test_id}/steps", json=[
        {"action": "navigate", "value": "https://new.com"},
        {"action": "click", "selector": "Login"},
        {"action": "type", "selector": "Email", "value": "x@y.com"},
    ], headers=headers)
    assert res.status_code == 200, res.text
    steps = res.json()
    assert len(steps) == 3
    assert steps[0]["action"] == "navigate"
    assert steps[0]["order"] == 0
    assert steps[1]["action"] == "click"
    assert steps[1]["order"] == 1
    assert steps[2]["action"] == "type"
    assert steps[2]["order"] == 2


def test_bulk_replace_old_steps_gone(client, editor_setup):
    headers, test_id = editor_setup
    s = _create_step(client, headers, test_id, 0, "click", selector="OldBtn")
    old_id = s["id"]

    client.put(f"/api/v1/tests/{test_id}/steps", json=[
        {"action": "navigate", "value": "https://new.com"},
    ], headers=headers)

    # Old step should 404
    res = client.get(f"/api/v1/steps/{old_id}", headers=headers)
    assert res.status_code == 404


def test_bulk_replace_with_empty_clears_steps(client, editor_setup):
    headers, test_id = editor_setup
    _create_step(client, headers, test_id, 0, "click", selector="Btn")

    res = client.put(f"/api/v1/tests/{test_id}/steps", json=[], headers=headers)
    assert res.status_code == 200
    assert res.json() == []

    list_res = client.get(f"/api/v1/tests/{test_id}/steps", headers=headers)
    assert list_res.json() == []


def test_bulk_replace_requires_auth(client, editor_setup):
    _, test_id = editor_setup
    res = client.put(f"/api/v1/tests/{test_id}/steps", json=[])
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Duplicate step
# ---------------------------------------------------------------------------

def test_duplicate_step_creates_clone(client, editor_setup):
    headers, test_id = editor_setup
    s = _create_step(client, headers, test_id, 0, "click", selector="Login", value=None)
    step_id = s["id"]

    res = client.post(f"/api/v1/steps/{step_id}/duplicate", headers=headers)
    assert res.status_code == 200, res.text
    clone = res.json()
    assert clone["id"] != step_id
    assert clone["action"] == "click"
    assert clone["selector"] == "Login"
    assert clone["test_id"] == test_id


def test_duplicate_step_inserts_after_original(client, editor_setup):
    headers, test_id = editor_setup
    s0 = _create_step(client, headers, test_id, 0, "navigate", value="https://a.com")
    s1 = _create_step(client, headers, test_id, 1, "click", selector="Btn")

    # Duplicate step at order=0
    client.post(f"/api/v1/steps/{s0['id']}/duplicate", headers=headers)

    steps = client.get(f"/api/v1/tests/{test_id}/steps", headers=headers).json()
    assert len(steps) == 3
    assert steps[0]["order"] == 0
    assert steps[0]["action"] == "navigate"
    assert steps[1]["order"] == 1
    assert steps[1]["action"] == "navigate"   # the clone
    assert steps[2]["order"] == 2
    assert steps[2]["action"] == "click"       # original s1 shifted to 2


def test_duplicate_nonexistent_step_returns_404(client, editor_setup):
    headers, _ = editor_setup
    res = client.post("/api/v1/steps/nonexistent-id/duplicate", headers=headers)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Insert step at position
# ---------------------------------------------------------------------------

def test_insert_step_at_shifts_subsequent(client, editor_setup):
    headers, test_id = editor_setup
    _create_step(client, headers, test_id, 0, "navigate", value="https://a.com")
    _create_step(client, headers, test_id, 1, "click", selector="Submit")

    # Insert at position 1 (between navigate and click)
    res = client.post(f"/api/v1/tests/{test_id}/steps/insert", json={
        "at_order": 1,
        "action": "type",
        "selector": "Email",
        "value": "x@y.com",
    }, headers=headers)
    assert res.status_code == 200, res.text
    inserted = res.json()
    assert inserted["order"] == 1
    assert inserted["action"] == "type"

    steps = client.get(f"/api/v1/tests/{test_id}/steps", headers=headers).json()
    assert len(steps) == 3
    assert steps[0]["action"] == "navigate"  # order 0 unchanged
    assert steps[1]["action"] == "type"      # inserted at 1
    assert steps[2]["action"] == "click"     # shifted from 1 → 2


def test_insert_step_at_beginning(client, editor_setup):
    headers, test_id = editor_setup
    _create_step(client, headers, test_id, 0, "click", selector="Btn")

    res = client.post(f"/api/v1/tests/{test_id}/steps/insert", json={
        "at_order": 0,
        "action": "navigate",
        "value": "https://a.com",
    }, headers=headers)
    assert res.status_code == 200

    steps = client.get(f"/api/v1/tests/{test_id}/steps", headers=headers).json()
    assert steps[0]["action"] == "navigate"
    assert steps[0]["order"] == 0
    assert steps[1]["action"] == "click"
    assert steps[1]["order"] == 1


def test_insert_step_at_end(client, editor_setup):
    headers, test_id = editor_setup
    _create_step(client, headers, test_id, 0, "navigate", value="https://a.com")

    res = client.post(f"/api/v1/tests/{test_id}/steps/insert", json={
        "at_order": 1,
        "action": "click",
        "selector": "Submit",
    }, headers=headers)
    assert res.status_code == 200
    assert res.json()["order"] == 1

    steps = client.get(f"/api/v1/tests/{test_id}/steps", headers=headers).json()
    assert len(steps) == 2
    assert steps[1]["action"] == "click"


def test_insert_step_requires_auth(client, editor_setup):
    _, test_id = editor_setup
    res = client.post(f"/api/v1/tests/{test_id}/steps/insert", json={
        "at_order": 0, "action": "click",
    })
    assert res.status_code == 401
