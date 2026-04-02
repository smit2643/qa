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


async def analyze_frame(
    frame_bytes: bytes,
    frame_index: int,
    prev_description: str,
    anthropic_api_key: str,
) -> dict | None:
    """
    Send a single frame to Claude Vision.
    Returns an action dict or None if no clear action detected.
    """
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
    img_b64 = base64.standard_b64encode(frame_bytes).decode()

    prompt = (
        f"Frame {frame_index + 1} of a screen recording.\n"
        f"Previous action: {prev_description or 'none'}\n\n"
        "What browser action is the user performing in this frame? "
        "Look for: clicking buttons/links, typing in fields, navigating to URLs, form submissions.\n\n"
        'Respond with JSON only:\n'
        '{"action": "navigate|click|type|assert|wait", '
        '"selector": "element name/label or null", '
        '"value": "URL or text to type or null", '
        '"description": "what is happening"}\n\n'
        "If no clear distinct action from the previous one, respond with: null"
    )

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    text = response.content[0].text.strip()
    if text.lower() == "null" or not text:
        return None

    # Strip markdown code fences if present
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text.rstrip())

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def extract_steps_from_video(
    video_bytes: bytes,
    target_url: str,
    llm,  # LLMProvider (unused here; Claude Vision called directly)
    sample_interval_seconds: float = 2.0,
    anthropic_api_key: str | None = None,
) -> list[dict]:
    """
    1. Write video to a temp file.
    2. Extract frames every sample_interval_seconds using ffmpeg.
    3. For each frame call Claude Vision to describe the action.
    4. Build a steps list from frame descriptions.
    5. Return steps.
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
                "value": action.get("value"),
                "description": action.get("description", ""),
            }
            raw_steps.append(step)
            prev_description = step["description"]

    from modules.extraction.normalizer import normalize_steps
    return normalize_steps(raw_steps)
