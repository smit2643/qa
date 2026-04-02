"""Tests for Phase 5: Jobs API (Task 30) — create, query, worker callbacks."""

import pytest
from unittest.mock import MagicMock, patch


MOCK_TEST_CODE = (
    "async def test_example(page):\n"
    "    await page.goto('https://example.com')\n"
)


@pytest.fixture
def runs_setup(client):
    """Create user → org → project → suite → 2 test cases. Return (headers, suite_id, test_ids)."""
    client.post("/api/v1/auth/signup", json={
        "email": "runs_owner@example.com",
        "name": "Runs Owner",
        "password": "securepass123",
    })
    res = client.post("/api/v1/auth/login", json={
        "email": "runs_owner@example.com",
        "password": "securepass123",
    })
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]

    proj = client.post("/api/v1/projects", json={
        "name": "Runs Project",
        "target_url": "https://example.com",
        "organization_id": org_id,
    }, headers=headers)
    assert proj.status_code == 200

    suite = client.post("/api/v1/suites", json={
        "name": "Runs Suite",
        "project_id": proj.json()["id"],
    }, headers=headers)
    assert suite.status_code == 200
    suite_id = suite.json()["id"]

    test_ids = []
    for i in range(2):
        t = client.post("/api/v1/tests", json={
            "name": f"Test {i}",
            "suite_id": suite_id,
            "code": MOCK_TEST_CODE,
        }, headers=headers)
        assert t.status_code == 200
        test_ids.append(t.json()["id"])

    return headers, suite_id, test_ids


def _mock_celery():
    """Patch Celery send_task so no real Redis needed."""
    return patch("modules.runs.service._dispatch_tasks", return_value=None)


# ---------------------------------------------------------------------------
# POST /runs — create run
# ---------------------------------------------------------------------------

def test_create_run_returns_queued(client, runs_setup):
    headers, suite_id, _ = runs_setup

    with _mock_celery():
        res = client.post("/api/v1/runs", json={
            "suite_id": suite_id,
            "browser": "chromium",
        }, headers=headers)

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["suite_id"] == suite_id
    assert data["status"] == "queued"
    assert data["browser"] == "chromium"
    assert data["trigger"] == "manual"
    assert "id" in data


def test_create_run_creates_result_per_test(client, runs_setup):
    headers, suite_id, test_ids = runs_setup

    with _mock_celery():
        res = client.post("/api/v1/runs", json={
            "suite_id": suite_id,
        }, headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) == 2
    for r in data["results"]:
        assert r["status"] == "pending"
        assert r["test_id"] in test_ids


def test_create_run_specific_test_ids(client, runs_setup):
    headers, suite_id, test_ids = runs_setup

    with _mock_celery():
        res = client.post("/api/v1/runs", json={
            "suite_id": suite_id,
            "test_ids": [test_ids[0]],
        }, headers=headers)

    assert res.status_code == 200
    assert len(res.json()["results"]) == 1
    assert res.json()["results"][0]["test_id"] == test_ids[0]


def test_create_run_invalid_browser_defaults_chromium(client, runs_setup):
    headers, suite_id, _ = runs_setup

    with _mock_celery():
        res = client.post("/api/v1/runs", json={
            "suite_id": suite_id,
            "browser": "netscape",
        }, headers=headers)

    assert res.status_code == 200
    assert res.json()["browser"] == "chromium"


def test_create_run_with_branch_and_commit(client, runs_setup):
    headers, suite_id, _ = runs_setup

    with _mock_celery():
        res = client.post("/api/v1/runs", json={
            "suite_id": suite_id,
            "branch": "feature/login",
            "commit_sha": "abc1234",
        }, headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["branch"] == "feature/login"
    assert data["commit_sha"] == "abc1234"


def test_create_run_requires_auth(client, runs_setup):
    _, suite_id, _ = runs_setup
    res = client.post("/api/v1/runs", json={"suite_id": suite_id})
    assert res.status_code == 401


def test_create_run_non_member_returns_403(client, runs_setup):
    _, suite_id, _ = runs_setup

    client.post("/api/v1/auth/signup", json={
        "email": "outsider_runs@example.com",
        "name": "Outsider",
        "password": "securepass123",
    })
    token = client.post("/api/v1/auth/login", json={
        "email": "outsider_runs@example.com",
        "password": "securepass123",
    }).json()["access_token"]

    with _mock_celery():
        res = client.post("/api/v1/runs", json={"suite_id": suite_id},
                          headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_create_run_unknown_suite_returns_404(client, runs_setup):
    headers, _, _ = runs_setup
    with _mock_celery():
        res = client.post("/api/v1/runs", json={"suite_id": "nonexistent"},
                          headers=headers)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# GET /runs/{id}
# ---------------------------------------------------------------------------

def test_get_run_by_id(client, runs_setup):
    headers, suite_id, _ = runs_setup

    with _mock_celery():
        run_id = client.post("/api/v1/runs", json={"suite_id": suite_id},
                             headers=headers).json()["id"]

    res = client.get(f"/api/v1/runs/{run_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["id"] == run_id


def test_get_run_requires_auth(client, runs_setup):
    headers, suite_id, _ = runs_setup
    with _mock_celery():
        run_id = client.post("/api/v1/runs", json={"suite_id": suite_id},
                             headers=headers).json()["id"]
    res = client.get(f"/api/v1/runs/{run_id}")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# GET /suites/{suite_id}/runs
# ---------------------------------------------------------------------------

def test_list_suite_runs(client, runs_setup):
    headers, suite_id, _ = runs_setup

    with _mock_celery():
        client.post("/api/v1/runs", json={"suite_id": suite_id}, headers=headers)
        client.post("/api/v1/runs", json={"suite_id": suite_id}, headers=headers)

    res = client.get(f"/api/v1/suites/{suite_id}/runs", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 2


# ---------------------------------------------------------------------------
# PATCH /runs/{run_id}/results/{result_id} — worker callback
# ---------------------------------------------------------------------------

def test_worker_callback_updates_result(client, runs_setup):
    headers, suite_id, _ = runs_setup

    with _mock_celery():
        run = client.post("/api/v1/runs", json={"suite_id": suite_id},
                          headers=headers).json()
    run_id = run["id"]
    result_id = run["results"][0]["id"]

    res = client.patch(f"/api/v1/runs/{run_id}/results/{result_id}", json={
        "status": "passed",
        "duration_ms": 1234,
        "video_url": "http://minio/runs/vid.webm",
        "log_url": "http://minio/runs/console.log",
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "passed"
    assert data["duration_ms"] == 1234
    assert data["video_url"] == "http://minio/runs/vid.webm"


def test_worker_callback_failed_result(client, runs_setup):
    headers, suite_id, _ = runs_setup

    with _mock_celery():
        run = client.post("/api/v1/runs", json={"suite_id": suite_id},
                          headers=headers).json()
    run_id = run["id"]
    result_id = run["results"][0]["id"]

    res = client.patch(f"/api/v1/runs/{run_id}/results/{result_id}", json={
        "status": "failed",
        "error_message": "TimeoutError: Locator not found",
        "duration_ms": 5000,
    })
    assert res.status_code == 200
    assert res.json()["status"] == "failed"
    assert "TimeoutError" in res.json()["error_message"]


def test_all_results_done_marks_run_passed(client, runs_setup):
    """When all results are passed, run auto-transitions to passed."""
    headers, suite_id, _ = runs_setup

    with _mock_celery():
        run = client.post("/api/v1/runs", json={"suite_id": suite_id},
                          headers=headers).json()
    run_id = run["id"]

    for r in run["results"]:
        client.patch(f"/api/v1/runs/{run_id}/results/{r['id']}", json={"status": "passed"})

    final = client.get(f"/api/v1/runs/{run_id}", headers=headers).json()
    assert final["status"] == "passed"
    assert final["finished_at"] is not None


def test_any_failed_result_marks_run_failed(client, runs_setup):
    headers, suite_id, _ = runs_setup

    with _mock_celery():
        run = client.post("/api/v1/runs", json={"suite_id": suite_id},
                          headers=headers).json()
    run_id = run["id"]
    results = run["results"]

    client.patch(f"/api/v1/runs/{run_id}/results/{results[0]['id']}", json={"status": "passed"})
    client.patch(f"/api/v1/runs/{run_id}/results/{results[1]['id']}", json={"status": "failed"})

    final = client.get(f"/api/v1/runs/{run_id}", headers=headers).json()
    assert final["status"] == "failed"


# ---------------------------------------------------------------------------
# PATCH /runs/{run_id}/finish — explicit finish
# ---------------------------------------------------------------------------

def test_finish_run_endpoint(client, runs_setup):
    headers, suite_id, _ = runs_setup

    with _mock_celery():
        run_id = client.post("/api/v1/runs", json={"suite_id": suite_id},
                             headers=headers).json()["id"]

    res = client.patch(f"/api/v1/runs/{run_id}/finish", json={"status": "cancelled"})
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"
