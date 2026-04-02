"""Browser module — visits a URL and returns the accessibility tree as text."""

import json
import os
import tempfile


def _format_tree(node: dict, indent: int) -> str:
    if not node:
        return ""
    prefix = "  " * indent
    role = node.get("role", "")
    name = node.get("name", "")
    line = f"{prefix}{role}: {name}".strip()
    parts = [line]
    for child in node.get("children", []):
        parts.append(_format_tree(child, indent + 1))
    return "\n".join(p for p in parts if p)


async def get_accessibility_tree(url: str, storage_state_json: str | None = None) -> str:
    """
    Visit url, return accessibility tree as text string.
    If storage_state_json is provided, inject it so authenticated pages work.
    """
    storage_file = None
    try:
        from playwright.async_api import async_playwright

        kwargs: dict = {}
        if storage_state_json:
            storage_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            )
            storage_file.write(storage_state_json)
            storage_file.close()
            kwargs["storage_state"] = storage_file.name

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(**kwargs)
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1000)
            tree = await page.accessibility.snapshot()
            await browser.close()
            return _format_tree(tree or {}, indent=0)
    finally:
        if storage_file and os.path.exists(storage_file.name):
            os.unlink(storage_file.name)
