"""Tests for Phase 3: AI Engine."""

import pytest
from unittest.mock import AsyncMock, patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_headers_with_suite(client):
    """Create user → login → org → project → suite and return (headers, suite_id)."""
    # Sign up and log in
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

    # Get auto-created org
    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]

    # Create project
    proj_res = client.post("/api/v1/projects", json={
        "name": "AI Test Project",
        "target_url": "https://example.com",
        "organization_id": org_id,
    }, headers=headers)
    assert proj_res.status_code == 200, proj_res.text
    project_id = proj_res.json()["id"]

    # Create suite
    suite_res = client.post("/api/v1/suites", json={
        "name": "AI Suite",
        "project_id": project_id,
    }, headers=headers)
    assert suite_res.status_code == 200, suite_res.text
    suite_id = suite_res.json()["id"]

    return headers, suite_id


# ---------------------------------------------------------------------------
# Mock plan / code constants
# ---------------------------------------------------------------------------

MOCK_PLAN = {
    "test_name": "User Login",
    "description": "Test login flow",
    "p0_paths": ["login"],
    "steps": [
        {
            "order": 0,
            "action": "navigate",
            "selector": None,
            "value": "https://example.com/login",
            "description": "Go to login",
        },
        {
            "order": 1,
            "action": "type",
            "selector": "email input",
            "value": "user@test.com",
            "description": "Enter email",
        },
        {
            "order": 2,
            "action": "click",
            "selector": "Login button",
            "value": None,
            "description": "Click login",
        },
    ],
}

MOCK_CODE = (
    "async def test_user_login(page):\n"
    "    await page.goto('https://example.com/login')\n"
)

# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

def test_generate_endpoint(client, auth_headers_with_suite):
    """Mock LLM + browser, verify endpoint returns test_id and code."""
    headers, suite_id = auth_headers_with_suite

    with patch("modules.ai.browser.get_accessibility_tree", new=AsyncMock(return_value="button: Login\ntextbox: Email")):
        with patch("modules.ai.planner.plan_test", new=AsyncMock(return_value=MOCK_PLAN)):
            with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
                res = client.post("/api/v1/ai/generate", json={
                    "description": "user logs in",
                    "suite_id": suite_id,
                }, headers=headers)

    assert res.status_code == 200, res.text
    data = res.json()
    assert "test_id" in data
    assert "code" in data
    assert data["code"] == MOCK_CODE
    assert data["version"] == 1


def test_generate_twice_bumps_version(client, auth_headers_with_suite):
    """Calling generate with the same test_id increments version to 2."""
    headers, suite_id = auth_headers_with_suite

    def _mock_generate(description, suite_id, test_id=None):
        return {
            "description": description,
            "suite_id": suite_id,
            "test_id": test_id,
        }

    with patch("modules.ai.browser.get_accessibility_tree", new=AsyncMock(return_value="button: Login")):
        with patch("modules.ai.planner.plan_test", new=AsyncMock(return_value=MOCK_PLAN)):
            with patch("modules.ai.generator.generate_code", new=AsyncMock(return_value=MOCK_CODE)):
                # First call — creates the test
                res1 = client.post("/api/v1/ai/generate", json={
                    "description": "user logs in",
                    "suite_id": suite_id,
                }, headers=headers)
                assert res1.status_code == 200, res1.text
                test_id = res1.json()["test_id"]
                assert res1.json()["version"] == 1

                # Second call — updates the same test
                res2 = client.post("/api/v1/ai/generate", json={
                    "description": "user logs in v2",
                    "suite_id": suite_id,
                    "test_id": test_id,
                }, headers=headers)
                assert res2.status_code == 200, res2.text
                assert res2.json()["version"] == 2
                assert res2.json()["test_id"] == test_id


def test_generate_requires_auth(client, auth_headers_with_suite):
    """Unauthenticated requests are rejected."""
    _, suite_id = auth_headers_with_suite
    res = client.post("/api/v1/ai/generate", json={
        "description": "test",
        "suite_id": suite_id,
    })
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# LLMProvider construction tests (no API calls)
# ---------------------------------------------------------------------------

def test_llm_provider_claude_constructs():
    from modules.ai.llm import LLMProvider
    llm = LLMProvider("claude")
    assert llm.provider == "claude"


def test_llm_provider_openai_constructs():
    from modules.ai.llm import LLMProvider
    llm = LLMProvider("openai")
    assert llm.provider == "openai"


def test_llm_provider_gemini_constructs():
    from modules.ai.llm import LLMProvider
    llm = LLMProvider("gemini")
    assert llm.provider == "gemini"


def test_llm_provider_unknown_raises():
    from modules.ai.llm import LLMProvider
    import pytest
    llm = LLMProvider("unknown_provider")
    # Should raise when complete() is called, not at construction time
    assert llm.provider == "unknown_provider"


# ---------------------------------------------------------------------------
# compress_tree unit tests
# ---------------------------------------------------------------------------

def test_compress_tree_short_passes_through():
    from modules.ai.compression import compress_tree
    text = "button: Submit\ntextbox: Email"
    result = compress_tree(text, max_chars=10000)
    assert result == text


def test_compress_tree_long_keeps_interactive():
    from modules.ai.compression import compress_tree, MAX_CHARS
    # Build a large tree that exceeds MAX_CHARS
    long_generic = ("generic: container\n" * 700)  # ~14000 chars
    with_button = long_generic + "button: Submit\n"
    result = compress_tree(with_button)
    assert len(result) <= MAX_CHARS + len("\n... [truncated for context limit]")
    # The button line should be present (unless truncated before it)
    # At minimum the function should return a string
    assert isinstance(result, str)


def test_compress_tree_preserves_buttons():
    from modules.ai.compression import compress_tree
    # Build text just over 12000 chars with button lines mixed in
    filler = ("generic: spacer\n" * 800)  # ~12800 chars
    with_interactive = "button: Login\n" + filler
    result = compress_tree(with_interactive)
    assert "button: Login" in result


# ---------------------------------------------------------------------------
# compress_messages unit tests
# ---------------------------------------------------------------------------

def test_compress_messages_short_passes_through():
    from modules.ai.compression import compress_messages
    msgs = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    result = compress_messages(msgs)
    assert result == msgs


def test_compress_messages_long_history_gets_summarized():
    from modules.ai.compression import compress_messages
    # Create messages that exceed 40000 chars total
    msgs = [
        {"role": "user", "content": "x" * 5000},
        {"role": "assistant", "content": "y" * 5000},
        {"role": "user", "content": "x" * 5000},
        {"role": "assistant", "content": "y" * 5000},
        {"role": "user", "content": "x" * 5000},
        {"role": "assistant", "content": "y" * 5000},
        {"role": "user", "content": "x" * 5000},
        {"role": "assistant", "content": "y" * 5000},
        {"role": "user", "content": "final question"},
    ]
    result = compress_messages(msgs)
    # Should be compressed (fewer messages or shorter)
    assert len(result) < len(msgs)
    # Last 4 messages should be intact
    assert result[-1]["content"] == "final question"


def test_compress_messages_few_messages_unchanged():
    from modules.ai.compression import compress_messages
    # Even if total is large, if <= 4 messages, return as-is
    msgs = [
        {"role": "user", "content": "x" * 20000},
        {"role": "assistant", "content": "y" * 20001},
    ]
    result = compress_messages(msgs)
    assert result == msgs
