"""Tests for Phase 3: AI Engine — browser-use Agent + Generator."""

import pytest
from unittest.mock import AsyncMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_headers_with_suite(client):
    """Create user → login → org → project → suite. Return (headers, suite_id)."""
    client.post("/api/v1/auth/signup", json={
        "email": "ai_owner@example.com",
        "name": "AI Owner",
        "password": "securepass123",
    })
    res = client.post("/api/v1/auth/login", json={
        "email": "ai_owner@example.com",
        "password": "securepass123",
    })
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]

    proj = client.post("/api/v1/projects", json={
        "name": "AI Test Project",
        "target_url": "https://example.com",
        "organization_id": org_id,
    }, headers=headers)
    assert proj.status_code == 200, proj.text

    suite = client.post("/api/v1/suites", json={
        "name": "AI Suite",
        "project_id": proj.json()["id"],
    }, headers=headers)
    assert suite.status_code == 200, suite.text

    return headers, suite.json()["id"]


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_STEPS = [
    {"order": 0, "action": "navigate", "selector": None, "value": "https://example.com/login", "description": "Go to login"},
    {"order": 1, "action": "type", "selector": "Email", "value": "user@test.com", "description": "Enter email"},
    {"order": 2, "action": "click", "selector": "Login button", "value": None, "description": "Click login"},
]

MOCK_CODE = (
    "async def test_user_login(page):\n"
    "    # Navigate to login page\n"
    "    await page.goto('https://example.com/login')\n"
    "    # Fill email\n"
    "    await page.get_by_label('Email').fill('user@test.com')\n"
    "    # Click login\n"
    "    await page.get_by_role('button', name='Login').click()\n"
)


# ---------------------------------------------------------------------------
# /ai/generate endpoint tests
# ---------------------------------------------------------------------------

def test_generate_endpoint(client, auth_headers_with_suite):
    """Mock browser-use Agent + generator, verify endpoint returns test_id and code."""
    headers, suite_id = auth_headers_with_suite

    with patch("modules.ai.browser.run_agent", new=AsyncMock(return_value=MOCK_STEPS)):
        with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
            res = client.post("/api/v1/ai/generate", json={
                "description": "user logs in",
                "suite_id": suite_id,
            }, headers=headers)

    assert res.status_code == 200, res.text
    data = res.json()
    assert "test_id" in data
    assert data["code"] == MOCK_CODE
    assert data["version"] == 1
    assert len(data["steps"]) == 3


def test_generate_twice_bumps_version(client, auth_headers_with_suite):
    """Calling generate with same test_id increments version."""
    headers, suite_id = auth_headers_with_suite

    with patch("modules.ai.browser.run_agent", new=AsyncMock(return_value=MOCK_STEPS)):
        with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
            res1 = client.post("/api/v1/ai/generate", json={
                "description": "user logs in",
                "suite_id": suite_id,
            }, headers=headers)
            assert res1.status_code == 200
            test_id = res1.json()["test_id"]
            assert res1.json()["version"] == 1

            res2 = client.post("/api/v1/ai/generate", json={
                "description": "user logs in v2",
                "suite_id": suite_id,
                "test_id": test_id,
            }, headers=headers)
            assert res2.status_code == 200
            assert res2.json()["version"] == 2
            assert res2.json()["test_id"] == test_id


def test_generate_requires_auth(client, auth_headers_with_suite):
    _, suite_id = auth_headers_with_suite
    res = client.post("/api/v1/ai/generate", json={"description": "test", "suite_id": suite_id})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# /ai/generate-from-steps endpoint tests
# ---------------------------------------------------------------------------

def test_generate_from_steps_endpoint(client, auth_headers_with_suite):
    """Generate code from pre-built steps (recording/video pipeline)."""
    headers, suite_id = auth_headers_with_suite

    with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
        res = client.post("/api/v1/ai/generate-from-steps", json={
            "suite_id": suite_id,
            "test_name": "User login flow",
            "input_method": "video",
            "steps": MOCK_STEPS,
        }, headers=headers)

    assert res.status_code == 200, res.text
    data = res.json()
    assert "test_id" in data
    assert data["code"] == MOCK_CODE
    assert data["version"] == 1


def test_generate_from_steps_requires_auth(client, auth_headers_with_suite):
    _, suite_id = auth_headers_with_suite
    res = client.post("/api/v1/ai/generate-from-steps", json={
        "suite_id": suite_id,
        "test_name": "test",
        "steps": MOCK_STEPS,
    })
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# extract_steps_from_history unit tests
# ---------------------------------------------------------------------------

def test_extract_steps_navigate():
    from modules.ai.browser import extract_steps_from_history

    class FakeHistory:
        def model_actions(self):
            return [{"go_to_url": {"url": "https://example.com"}, "interacted_element": None}]

    steps = extract_steps_from_history(FakeHistory())
    assert len(steps) == 1
    assert steps[0]["action"] == "navigate"
    assert steps[0]["value"] == "https://example.com"


def test_extract_steps_click():
    from modules.ai.browser import extract_steps_from_history

    class FakeHistory:
        def model_actions(self):
            return [{"click_element": {"element_description": "Login button"}, "interacted_element": None}]

    steps = extract_steps_from_history(FakeHistory())
    assert steps[0]["action"] == "click"
    assert steps[0]["selector"] == "Login button"


def test_extract_steps_type():
    from modules.ai.browser import extract_steps_from_history

    class FakeHistory:
        def model_actions(self):
            return [{"input_text": {"selector": "Email", "text": "user@test.com"}, "interacted_element": None}]

    steps = extract_steps_from_history(FakeHistory())
    assert steps[0]["action"] == "type"
    assert steps[0]["value"] == "user@test.com"


def test_extract_steps_skips_done():
    from modules.ai.browser import extract_steps_from_history

    class FakeHistory:
        def model_actions(self):
            return [
                {"go_to_url": {"url": "https://example.com"}, "interacted_element": None},
                {"done": {"success": True}, "interacted_element": None},
            ]

    steps = extract_steps_from_history(FakeHistory())
    assert len(steps) == 1  # done is skipped


# ---------------------------------------------------------------------------
# LLMProvider construction tests
# ---------------------------------------------------------------------------

def test_llm_provider_claude():
    from modules.ai.llm import LLMProvider
    assert LLMProvider("claude").provider == "claude"


def test_llm_provider_openai():
    from modules.ai.llm import LLMProvider
    assert LLMProvider("openai").provider == "openai"


def test_llm_provider_gemini():
    from modules.ai.llm import LLMProvider
    assert LLMProvider("gemini").provider == "gemini"


# ---------------------------------------------------------------------------
# compress_tree unit tests
# ---------------------------------------------------------------------------

def test_compress_tree_short_passes_through():
    from modules.ai.compression import compress_tree
    text = "button: Submit\ntextbox: Email"
    assert compress_tree(text, max_chars=10000) == text


def test_compress_tree_long_keeps_interactive():
    from modules.ai.compression import compress_tree, MAX_CHARS
    long_generic = "generic: container\n" * 700
    result = compress_tree(long_generic + "button: Submit\n")
    assert len(result) <= MAX_CHARS + len("\n... [truncated for context limit]")
    assert isinstance(result, str)


def test_compress_tree_preserves_buttons():
    from modules.ai.compression import compress_tree
    filler = "generic: spacer\n" * 800
    result = compress_tree("button: Login\n" + filler)
    assert "button: Login" in result


# ---------------------------------------------------------------------------
# compress_messages unit tests
# ---------------------------------------------------------------------------

def test_compress_messages_short_passes_through():
    from modules.ai.compression import compress_messages
    msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
    assert compress_messages(msgs) == msgs


def test_compress_messages_long_gets_summarized():
    from modules.ai.compression import compress_messages
    msgs = [{"role": "user", "content": "x" * 5000}, {"role": "assistant", "content": "y" * 5000}] * 4
    msgs.append({"role": "user", "content": "final question"})
    result = compress_messages(msgs)
    assert len(result) < len(msgs)
    assert result[-1]["content"] == "final question"


def test_compress_messages_few_unchanged():
    from modules.ai.compression import compress_messages
    msgs = [{"role": "user", "content": "x" * 20000}, {"role": "assistant", "content": "y" * 20001}]
    assert compress_messages(msgs) == msgs


# ---------------------------------------------------------------------------
# _execute_action unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_action_navigate():
    from unittest.mock import AsyncMock, MagicMock
    from modules.ai.browser import _execute_action

    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()

    success, err = await _execute_action(page, {
        "action": "navigate",
        "selector": None,
        "value": "https://example.com",
        "description": "Go to example",
    })

    assert success is True
    assert err is None
    page.goto.assert_called_once_with("https://example.com", timeout=15000)


@pytest.mark.asyncio
async def test_execute_action_done():
    from unittest.mock import MagicMock
    from modules.ai.browser import _execute_action

    page = MagicMock()
    success, err = await _execute_action(page, {"action": "done", "selector": None, "value": None, "description": "done"})
    assert success is True
    assert err is None


@pytest.mark.asyncio
async def test_execute_action_click_fallback():
    from unittest.mock import AsyncMock, MagicMock
    from modules.ai.browser import _execute_action

    page = MagicMock()
    mock_locator_fail = MagicMock()
    mock_locator_fail.click = AsyncMock(side_effect=Exception("not found"))
    mock_locator_ok = MagicMock()
    mock_locator_ok.first = MagicMock()
    mock_locator_ok.first.click = AsyncMock()

    page.get_by_role = MagicMock(return_value=mock_locator_fail)
    page.get_by_text = MagicMock(return_value=mock_locator_ok)
    page.wait_for_load_state = AsyncMock()

    success, err = await _execute_action(page, {
        "action": "click",
        "selector": "Login",
        "value": None,
        "description": "Click login",
    })

    assert success is True
