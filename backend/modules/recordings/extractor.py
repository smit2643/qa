"""Frame extraction + Claude Vision analysis for screen recordings."""

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def extract_frames(video_path: str, interval: float = 2.0) -> list[bytes]:
    """Extract frames from video every `interval` seconds. Returns list of PNG bytes."""
    output_dir = tempfile.mkdtemp()
    try:
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vf", f"fps=1/{interval}",
            "-f", "image2",
            f"{output_dir}/frame_%04d.png",
            "-y", "-loglevel", "error",
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        frames = []
        for f in sorted(Path(output_dir).glob("frame_*.png")):
            frames.append(f.read_bytes())
        return frames
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


_FRAME_SYSTEM = """You are a browser action extractor. You receive a screenshot from a screen recording and must identify what browser action is visible.

RULES:
- Always respond with a JSON object. Never respond with null or plain text.
- If nothing changed from the previous frame, output a wait action.
- action must be one of: navigate, click, type, wait
- selector: the visible label, button text, field name, or null for navigate/wait
- value: the URL for navigate, typed text for type, wait duration in ms for wait, null for click
- description: one sentence describing what is happening

JSON format (respond with this exact structure):
{"action": "navigate|click|type|wait", "selector": "text or null", "value": "text or null", "description": "what is happening"}"""


async def analyze_frame(
    frame_bytes: bytes,
    frame_index: int,
    prev_description: str,
    anthropic_api_key: str,
) -> dict | None:
    """
    Send a single frame to the configured LLM vision provider.
    Returns an action dict or None if no clear action detected.
    """
    from core.config import settings
    from modules.ai.llm import LLMProvider

    img_b64 = base64.standard_b64encode(frame_bytes).decode()

    prompt = (
        f"Frame {frame_index + 1} of a screen recording.\n"
        f"Previous frame: {prev_description or 'start of recording'}\n\n"
        "Look at the screenshot. What action is the user performing or what page is shown?\n"
        "- If URL bar shows a page load → action=navigate, value=that URL\n"
        "- If a button or link was clicked → action=click, selector=button/link text\n"
        "- If text was typed in a field → action=type, selector=field label, value=text typed\n"
        "- If page is loading or nothing changed → action=wait, value=2000\n\n"
        "Respond with ONE JSON object only. No markdown, no explanation."
    )

    provider = settings.llm_provider
    if provider == "claude":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                {"type": "text", "text": prompt},
            ]}],
        )
        text = response.content[0].text.strip()
    else:
        # OpenAI-compatible vision format (Ollama with vision model)
        llm = LLMProvider()
        messages = [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            {"type": "text", "text": prompt},
        ]}]
        text = await llm.complete(messages, system=_FRAME_SYSTEM)

    if not text or text.strip().lower() == "null":
        # Fallback: emit a wait step rather than dropping the frame entirely
        return {"action": "wait", "selector": None, "value": "2000", "description": f"Frame {frame_index + 1}: no distinct action"}

    # Strip thinking tokens (qwen/deepseek)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip markdown code fences
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text.rstrip())
    # Extract first JSON object
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)

    try:
        result = json.loads(text)
        if not isinstance(result, dict):
            return None
        return result
    except json.JSONDecodeError:
        return None


async def extract_steps_from_video(
    video_bytes: bytes,
    target_url: str,
    llm,  # LLMProvider (unused here; Claude Vision called directly)
    sample_interval_seconds: float = 2.0,
    anthropic_api_key: str | None = None,
    login_email: str | None = None,
    login_password: str | None = None,
    login_url: str | None = None,
) -> list[dict]:
    """
    1. Write video to a temp file.
    2. Extract frames every sample_interval_seconds using ffmpeg.
    3. For each frame call LLM vision to describe the action.
    4. Build a steps list from frame descriptions.
    5. If suite has login config and video doesn't show login, prepend login steps.
    6. Return steps.
    """
    from core.config import settings

    api_key = anthropic_api_key or settings.anthropic_api_key

    # Write video bytes to a temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
    try:
        tmp.write(video_bytes)
        tmp.close()

        frames = extract_frames(tmp.name, interval=sample_interval_seconds)
    finally:
        os.unlink(tmp.name)

    raw_steps: list[dict] = []
    prev_description = f"Starting at {target_url}"

    for i, frame_bytes in enumerate(frames):
        action = await analyze_frame(frame_bytes, i, prev_description, api_key)
        if action:
            step = {
                "order": len(raw_steps),
                "action": action.get("action", "wait"),
                "selector": action.get("selector"),
                "value": str(action.get("value")) if action.get("value") is not None else None,
                "description": action.get("description", ""),
            }
            # Skip consecutive wait steps — only keep the last in a run
            if step["action"] == "wait" and raw_steps and raw_steps[-1]["action"] == "wait":
                raw_steps[-1] = {**raw_steps[-1], "description": step["description"]}
                continue
            raw_steps.append(step)
            prev_description = step["description"]

    # If suite has login credentials and the video doesn't show a login step,
    # prepend login steps so the generated Playwright code handles login itself.
    # (The runner will also inject session state, but having login in code is a safety net.)
    video_has_login = any(
        s.get("action") == "type" and any(
            kw in (s.get("selector") or "").lower()
            for kw in ("email", "password", "username", "passwd")
        )
        for s in raw_steps
    )

    if login_email and login_password and not video_has_login:
        login_steps = [
            {
                "order": 0,
                "action": "navigate",
                "selector": None,
                "value": login_url or target_url,
                "description": f"Navigate to login page",
            },
            {
                "order": 1,
                "action": "type",
                "selector": "Email",
                "value": login_email,
                "description": "Enter login email",
            },
            {
                "order": 2,
                "action": "type",
                "selector": "Password",
                "value": login_password,
                "description": "Enter login password",
            },
            {
                "order": 3,
                "action": "click",
                "selector": "Sign in",
                "description": "Click sign in button",
                "value": None,
            },
            {
                "order": 4,
                "action": "wait",
                "selector": None,
                "value": "2000",
                "description": "Wait for login to complete",
            },
        ]
        # Re-number video steps after login steps
        for s in raw_steps:
            s["order"] = s["order"] + len(login_steps)
        raw_steps = login_steps + raw_steps

    from modules.extraction.normalizer import normalize_steps
    return normalize_steps(raw_steps)
