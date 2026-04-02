"""Tests for Phase 4 Task 20: /ai/generate-from-steps endpoint.

Covers the full visual editor flow:
  upload (video/recording) → steps extracted → user edits steps → generate code
"""

import pytest
from unittest.mock import AsyncMock, patch

MOCK_CODE = (
    "async def test_login(page):\n"
    "    await page.goto('https://example.com/login')\n"
    "    await page.get_by_label('Email').fill('user@test.com')\n"
    "    await page.get_by_role('button', name='Login').click()\n"
)

MOCK_STEPS = [
    {"order": 0, "action": "navigate", "selector": None, "value": "https://example.com/login", "description": "Go to login"},
    {"order": 1, "action": "type", "selector": "Email", "value": "user@test.com", "description": "Enter email"},
    {"order": 2, "action": "click", "selector": "Login button", "value": None, "description": "Click login"},
]


@pytest.fixture
def gfs_setup(client):
    """Create user → org → project → suite. Return (headers, suite_id)."""
    client.post("/api/v1/auth/signup", json={
        "email": "gfs_owner@example.com",
        "name": "GFS Owner",
        "password": "securepass123",
    })
    res = client.post("/api/v1/auth/login", json={
        "email": "gfs_owner@example.com",
        "password": "securepass123",
    })
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]

    proj = client.post("/api/v1/projects", json={
        "name": "GFS Project",
        "target_url": "https://example.com",
        "organization_id": org_id,
    }, headers=headers)
    assert proj.status_code == 200

    suite = client.post("/api/v1/suites", json={
        "name": "GFS Suite",
        "project_id": proj.json()["id"],
    }, headers=headers)
    assert suite.status_code == 200

    return headers, suite.json()["id"]


# ---------------------------------------------------------------------------
# Basic response shape
# ---------------------------------------------------------------------------

def test_generate_from_steps_returns_code_and_test_id(client, gfs_setup):
    headers, suite_id = gfs_setup

    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
        res = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "Login flow",
            "steps": MOCK_STEPS,
        }, headers=headers)

    assert res.status_code == 200, res.text
    data = res.json()
    assert "test_id" in data
    assert data["code"] == MOCK_CODE
    assert data["version"] == 1
    assert isinstance(data["steps"], list)


def test_generate_from_steps_steps_in_response(client, gfs_setup):
    headers, suite_id = gfs_setup

    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
        res = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "Login flow",
            "steps": MOCK_STEPS,
        }, headers=headers)

    assert len(res.json()["steps"]) == 3


# ---------------------------------------------------------------------------
# input_method preserved
# ---------------------------------------------------------------------------

def test_input_method_recording_saved(client, gfs_setup):
    headers, suite_id = gfs_setup

    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
        res = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "Recording test",
            "input_method": "recording",
            "steps": MOCK_STEPS,
        }, headers=headers)

    assert res.status_code == 200
    test_id = res.json()["test_id"]

    test_res = client.get(f"/api/v1/tests/{test_id}", headers=headers)
    assert test_res.status_code == 200
    assert test_res.json()["input_method"] == "recording"


def test_input_method_video_saved(client, gfs_setup):
    headers, suite_id = gfs_setup

    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
        res = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "Video test",
            "input_method": "video",
            "steps": MOCK_STEPS,
        }, headers=headers)

    assert res.status_code == 200
    test_id = res.json()["test_id"]

    test_res = client.get(f"/api/v1/tests/{test_id}", headers=headers)
    assert test_res.json()["input_method"] == "video"


def test_invalid_input_method_falls_back_to_text(client, gfs_setup):
    headers, suite_id = gfs_setup

    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
        res = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "Unknown input",
            "input_method": "magic_wand",
            "steps": MOCK_STEPS,
        }, headers=headers)

    assert res.status_code == 200
    test_id = res.json()["test_id"]
    test_res = client.get(f"/api/v1/tests/{test_id}", headers=headers)
    assert test_res.json()["input_method"] == "text"


# ---------------------------------------------------------------------------
# Steps persisted to DB
# ---------------------------------------------------------------------------

def test_steps_persisted_after_generate(client, gfs_setup):
    headers, suite_id = gfs_setup

    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
        res = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "Persisted steps",
            "steps": MOCK_STEPS,
        }, headers=headers)

    test_id = res.json()["test_id"]
    steps_res = client.get(f"/api/v1/tests/{test_id}/steps", headers=headers)
    assert steps_res.status_code == 200
    db_steps = steps_res.json()
    assert len(db_steps) == 3
    assert db_steps[0]["action"] == "navigate"
    assert db_steps[1]["action"] == "type"
    assert db_steps[2]["action"] == "click"


# ---------------------------------------------------------------------------
# Version bumping (update flow)
# ---------------------------------------------------------------------------

def test_generate_from_steps_with_test_id_bumps_version(client, gfs_setup):
    headers, suite_id = gfs_setup

    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
        res1 = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "Flow v1",
            "steps": MOCK_STEPS,
        }, headers=headers)
    assert res1.status_code == 200
    test_id = res1.json()["test_id"]
    assert res1.json()["version"] == 1

    updated_steps = MOCK_STEPS + [{
        "order": 3, "action": "assert", "selector": "Dashboard",
        "value": None, "description": "Verify dashboard visible",
    }]
    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
        res2 = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "Flow v2",
            "test_id": test_id,
            "steps": updated_steps,
        }, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["version"] == 2
    assert res2.json()["test_id"] == test_id


def test_generate_from_steps_update_replaces_steps_in_db(client, gfs_setup):
    """After updating with test_id, old steps are replaced by new ones."""
    headers, suite_id = gfs_setup

    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
        res1 = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "Replace test",
            "steps": MOCK_STEPS,
        }, headers=headers)
    test_id = res1.json()["test_id"]

    new_steps = [
        {"order": 0, "action": "navigate", "value": "https://new.com", "description": "New URL"},
    ]
    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
        client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "Replace test",
            "test_id": test_id,
            "steps": new_steps,
        }, headers=headers)

    steps_res = client.get(f"/api/v1/tests/{test_id}/steps", headers=headers).json()
    assert len(steps_res) == 1
    assert steps_res[0]["action"] == "navigate"
    assert steps_res[0]["value"] == "https://new.com"


# ---------------------------------------------------------------------------
# Step normalization applied before code generation
# ---------------------------------------------------------------------------

def test_unknown_actions_normalized_before_generate(client, gfs_setup):
    """Steps with unknown actions are normalized to 'wait' before code gen."""
    headers, suite_id = gfs_setup

    dirty_steps = [
        {"order": 0, "action": "hover", "selector": "Menu", "value": None, "description": "hover"},
        {"order": 1, "action": "click", "selector": "Submit", "value": None, "description": "click"},
    ]

    captured = {}

    async def capture_code(steps, llm, **kwargs):
        captured["steps"] = steps
        return MOCK_CODE

    with patch("modules.ai.generator.generate_code", new=capture_code):
        res = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "Normalization test",
            "steps": dirty_steps,
        }, headers=headers)

    assert res.status_code == 200
    assert captured["steps"][0]["action"] == "wait"  # hover → wait
    assert captured["steps"][1]["action"] == "click"


def test_consecutive_duplicate_steps_deduplicated_before_generate(client, gfs_setup):
    """Consecutive duplicate steps are removed before code generation."""
    headers, suite_id = gfs_setup

    dup_steps = [
        {"order": 0, "action": "click", "selector": "Btn", "value": None, "description": "click 1"},
        {"order": 1, "action": "click", "selector": "Btn", "value": None, "description": "click 2"},
        {"order": 2, "action": "navigate", "selector": None, "value": "https://a.com", "description": "go"},
    ]

    captured = {}

    async def capture_code(steps, llm, **kwargs):
        captured["steps"] = steps
        return MOCK_CODE

    with patch("modules.ai.generator.generate_code", new=capture_code):
        res = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "Dedup test",
            "steps": dup_steps,
        }, headers=headers)

    assert res.status_code == 200
    assert len(captured["steps"]) == 2  # duplicate click collapsed


# ---------------------------------------------------------------------------
# Auth and access control
# ---------------------------------------------------------------------------

def test_generate_from_steps_requires_auth(client, gfs_setup):
    _, suite_id = gfs_setup
    res = client.post("/api/v1/ai/generate-from-steps", json={
        "suite_id": suite_id,
        "test_name": "No auth",
        "steps": MOCK_STEPS,
    })
    assert res.status_code == 401


def test_generate_from_steps_non_member_returns_403(client, gfs_setup):
    _, suite_id = gfs_setup

    client.post("/api/v1/auth/signup", json={
        "email": "outsider_gfs@example.com",
        "name": "Outsider",
        "password": "securepass123",
    })
    token = client.post("/api/v1/auth/login", json={
        "email": "outsider_gfs@example.com",
        "password": "securepass123",
    }).json()["access_token"]
    outsider = {"Authorization": f"Bearer {token}"}

    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
        res = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "Should fail",
            "steps": MOCK_STEPS,
        }, headers=outsider)

    assert res.status_code == 403


def test_generate_from_steps_unknown_suite_returns_404(client, gfs_setup):
    headers, _ = gfs_setup

    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
        res = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": "nonexistent-suite-id",
            "test_name": "Bad suite",
            "steps": MOCK_STEPS,
        }, headers=headers)

    assert res.status_code == 404
