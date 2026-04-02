"""Tests for Phase 4, Task 16: Screen recording upload API."""

import io
import pytest
from unittest.mock import AsyncMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def recording_setup(client):
    """Create user → org → project → suite. Return (headers, suite_id, target_url)."""
    client.post("/api/v1/auth/signup", json={
        "email": "rec_owner@example.com",
        "name": "Rec Owner",
        "password": "securepass123",
    })
    res = client.post("/api/v1/auth/login", json={
        "email": "rec_owner@example.com",
        "password": "securepass123",
    })
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]

    target_url = "https://example.com"
    proj = client.post("/api/v1/projects", json={
        "name": "Recording Test Project",
        "target_url": target_url,
        "organization_id": org_id,
    }, headers=headers)
    assert proj.status_code == 200, proj.text

    suite = client.post("/api/v1/suites", json={
        "name": "Recording Suite",
        "project_id": proj.json()["id"],
    }, headers=headers)
    assert suite.status_code == 200, suite.text

    return headers, suite.json()["id"], target_url


MOCK_STEPS = [
    {
        "order": 0,
        "action": "navigate",
        "selector": None,
        "value": "https://example.com",
        "description": "Navigate to example.com",
    },
    {
        "order": 1,
        "action": "click",
        "selector": "Login button",
        "value": None,
        "description": "Click Login button",
    },
    {
        "order": 2,
        "action": "type",
        "selector": "Email field",
        "value": "user@test.com",
        "description": "Type email address",
    },
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_upload_recording_returns_steps_and_test_id(client, recording_setup):
    """Upload a fake WebM → 200, returns extracted steps and test_id."""
    headers, suite_id, _ = recording_setup

    with patch(
        "modules.recordings.extractor.extract_steps_from_video",
        new=AsyncMock(return_value=MOCK_STEPS),
    ):
        res = client.post(
            "/api/v1/recordings/upload",
            headers=headers,
            data={"suite_id": suite_id, "test_name": "My Screen Recording"},
            files={"file": ("test.webm", io.BytesIO(b"WEBM_FAKE_CONTENT"), "video/webm")},
        )

    assert res.status_code == 200, res.text
    data = res.json()
    assert "test_id" in data
    assert data["suite_id"] == suite_id
    assert data["test_name"] == "My Screen Recording"
    assert len(data["steps"]) == 3
    assert "steps extracted" in data["message"]


def test_upload_recording_steps_saved_to_db(client, recording_setup):
    """Steps extracted from recording are persisted and retrievable via /tests/{id}/steps."""
    headers, suite_id, _ = recording_setup

    with patch(
        "modules.recordings.extractor.extract_steps_from_video",
        new=AsyncMock(return_value=MOCK_STEPS),
    ):
        res = client.post(
            "/api/v1/recordings/upload",
            headers=headers,
            data={"suite_id": suite_id},
            files={"file": ("rec.webm", io.BytesIO(b"WEBM_FAKE_CONTENT"), "video/webm")},
        )

    assert res.status_code == 200, res.text
    test_id = res.json()["test_id"]

    steps_res = client.get(f"/api/v1/tests/{test_id}/steps", headers=headers)
    assert steps_res.status_code == 200, steps_res.text
    db_steps = steps_res.json()
    assert len(db_steps) == 3
    assert db_steps[0]["action"] == "navigate"
    assert db_steps[1]["action"] == "click"
    assert db_steps[2]["action"] == "type"


def test_upload_recording_missing_suite_id_returns_422(client, recording_setup):
    """Missing suite_id form field → 422."""
    headers, _, _ = recording_setup

    with patch(
        "modules.recordings.extractor.extract_steps_from_video",
        new=AsyncMock(return_value=MOCK_STEPS),
    ):
        res = client.post(
            "/api/v1/recordings/upload",
            headers=headers,
            # no suite_id in data
            files={"file": ("rec.webm", io.BytesIO(b"WEBM_FAKE_CONTENT"), "video/webm")},
        )

    assert res.status_code == 422


def test_upload_recording_unauthenticated_returns_401(client, recording_setup):
    """No auth token → 401."""
    _, suite_id, _ = recording_setup

    res = client.post(
        "/api/v1/recordings/upload",
        data={"suite_id": suite_id},
        files={"file": ("rec.webm", io.BytesIO(b"WEBM_FAKE_CONTENT"), "video/webm")},
    )

    assert res.status_code == 401


def test_upload_recording_uses_default_test_name(client, recording_setup):
    """test_name defaults to 'Screen Recording' when not provided."""
    headers, suite_id, _ = recording_setup

    with patch(
        "modules.recordings.extractor.extract_steps_from_video",
        new=AsyncMock(return_value=MOCK_STEPS),
    ):
        res = client.post(
            "/api/v1/recordings/upload",
            headers=headers,
            data={"suite_id": suite_id},
            files={"file": ("rec.webm", io.BytesIO(b"WEBM_FAKE_CONTENT"), "video/webm")},
        )

    assert res.status_code == 200, res.text
    assert res.json()["test_name"] == "Screen Recording"
