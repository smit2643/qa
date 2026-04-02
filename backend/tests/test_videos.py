"""Tests for Phase 4 Task 17: Video upload API."""

import io
import pytest
from unittest.mock import AsyncMock, patch

MOCK_STEPS = [
    {"order": 0, "action": "navigate", "selector": None, "value": "https://example.com", "description": "Navigate to app"},
    {"order": 1, "action": "click", "selector": "Login button", "value": None, "description": "Click login"},
    {"order": 2, "action": "type", "selector": "Email", "value": "user@test.com", "description": "Enter email"},
]


@pytest.fixture
def video_setup(client):
    """Create user → org → project → suite. Return (headers, suite_id)."""
    client.post("/api/v1/auth/signup", json={
        "email": "video_owner@example.com",
        "name": "Video Owner",
        "password": "securepass123",
    })
    res = client.post("/api/v1/auth/login", json={
        "email": "video_owner@example.com",
        "password": "securepass123",
    })
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]

    proj = client.post("/api/v1/projects", json={
        "name": "Video Test Project",
        "target_url": "https://example.com",
        "organization_id": org_id,
    }, headers=headers)
    assert proj.status_code == 200

    suite = client.post("/api/v1/suites", json={
        "name": "Video Suite",
        "project_id": proj.json()["id"],
    }, headers=headers)
    assert suite.status_code == 200

    return headers, suite.json()["id"]


def test_upload_video_returns_steps(client, video_setup):
    """Upload a fake mp4 → returns extracted steps and test_id."""
    headers, suite_id = video_setup

    with patch("modules.videos.service.extract_steps_from_video", new=AsyncMock(return_value=MOCK_STEPS)):
        res = client.post(
            "/api/v1/videos/upload",
            data={"suite_id": suite_id, "test_name": "My video test"},
            files={"file": ("test.mp4", io.BytesIO(b"FAKE_MP4_CONTENT"), "video/mp4")},
            headers=headers,
        )

    assert res.status_code == 200, res.text
    data = res.json()
    assert "test_id" in data
    assert data["suite_id"] == suite_id
    assert data["test_name"] == "My video test"
    assert len(data["steps"]) == 3
    assert data["frame_count"] == 3
    assert "extracted" in data["message"]


def test_upload_video_steps_saved_to_db(client, video_setup):
    """Steps from video are persisted and fetchable via /tests/{id}/steps."""
    headers, suite_id = video_setup

    with patch("modules.videos.service.extract_steps_from_video", new=AsyncMock(return_value=MOCK_STEPS)):
        upload_res = client.post(
            "/api/v1/videos/upload",
            data={"suite_id": suite_id, "test_name": "DB persistence test"},
            files={"file": ("test.webm", io.BytesIO(b"FAKE_WEBM"), "video/webm")},
            headers=headers,
        )
    assert upload_res.status_code == 200
    test_id = upload_res.json()["test_id"]

    steps_res = client.get(f"/api/v1/tests/{test_id}/steps", headers=headers)
    assert steps_res.status_code == 200
    steps = steps_res.json()
    assert len(steps) == 3
    assert steps[0]["action"] == "navigate"
    assert steps[1]["action"] == "click"
    assert steps[2]["action"] == "type"


def test_upload_video_default_test_name(client, video_setup):
    """Test name defaults to 'Video Upload Test' when not provided."""
    headers, suite_id = video_setup

    with patch("modules.videos.service.extract_steps_from_video", new=AsyncMock(return_value=MOCK_STEPS)):
        res = client.post(
            "/api/v1/videos/upload",
            data={"suite_id": suite_id},
            files={"file": ("test.mp4", io.BytesIO(b"FAKE_MP4"), "video/mp4")},
            headers=headers,
        )
    assert res.status_code == 200
    assert res.json()["test_name"] == "Video Upload Test"


def test_upload_video_invalid_content_type(client, video_setup):
    """Non-video file type returns 422."""
    headers, suite_id = video_setup

    res = client.post(
        "/api/v1/videos/upload",
        data={"suite_id": suite_id},
        files={"file": ("test.txt", io.BytesIO(b"not a video"), "text/plain")},
        headers=headers,
    )
    assert res.status_code == 422


def test_upload_video_requires_auth(client, video_setup):
    """Unauthenticated request returns 401."""
    _, suite_id = video_setup
    res = client.post(
        "/api/v1/videos/upload",
        data={"suite_id": suite_id},
        files={"file": ("test.mp4", io.BytesIO(b"FAKE"), "video/mp4")},
    )
    assert res.status_code == 401


def test_upload_video_input_method_is_video(client, video_setup):
    """TestCase created with input_method=video."""
    headers, suite_id = video_setup

    with patch("modules.videos.service.extract_steps_from_video", new=AsyncMock(return_value=MOCK_STEPS)):
        res = client.post(
            "/api/v1/videos/upload",
            data={"suite_id": suite_id, "test_name": "Input method check"},
            files={"file": ("test.mp4", io.BytesIO(b"FAKE_MP4"), "video/mp4")},
            headers=headers,
        )
    assert res.status_code == 200
    test_id = res.json()["test_id"]

    test_res = client.get(f"/api/v1/tests/{test_id}", headers=headers)
    assert test_res.status_code == 200
    assert test_res.json()["input_method"] == "video"
