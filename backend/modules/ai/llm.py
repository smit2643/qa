"""LLM Provider Abstraction — unified interface for Claude, GPT-4o, and Gemini."""

import json
import re
from core.config import settings


class LLMProvider:
    """Unified async interface for Claude, OpenAI, and Gemini."""

    def __init__(self, provider: str = None, model: str = None):
        self.provider = provider or settings.llm_provider
        self.model = model  # None means use the default per-provider model

    async def complete(self, messages: list[dict], system: str = "") -> str:
        """Send messages and return the assistant reply string."""
        if self.provider == "claude":
            return await self._complete_claude(messages, system)
        elif self.provider == "openai":
            return await self._complete_openai(messages, system)
        elif self.provider == "gemini":
            return await self._complete_gemini(messages, system)
        elif self.provider == "ollama":
            return await self._complete_ollama(messages, system)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider!r}")

    async def complete_json(self, messages: list[dict], system: str = "") -> dict:
        """Same as complete() but parses and returns the JSON from the response."""
        text = await self.complete(messages, system)
        text = text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text.rstrip())
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM did not return valid JSON: {e}\nResponse was:\n{text}") from e

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    async def _complete_claude(self, messages: list[dict], system: str) -> str:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        model = self.model or "claude-sonnet-4-6"
        response = await client.messages.create(
            model=model,
            max_tokens=8096,
            system=system,
            messages=messages,
        )
        return response.content[0].text

    async def _complete_openai(self, messages: list[dict], system: str) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        model = self.model or "gpt-4o"
        all_messages = ([{"role": "system", "content": system}] + messages) if system else messages
        response = await client.chat.completions.create(
            model=model,
            messages=all_messages,
            max_tokens=8096,
        )
        return response.choices[0].message.content

    async def _complete_ollama(self, messages: list[dict], system: str) -> str:
        import httpx
        import logging
        logger = logging.getLogger(__name__)

        model = self.model or settings.ollama_model
        all_messages = ([{"role": "system", "content": system}] + messages) if system else messages

        # Convert OpenAI-style vision messages to Ollama format
        ollama_messages = []
        for msg in all_messages:
            content = msg.get("content")
            if isinstance(content, list):
                # Vision message — extract text and base64 images
                text_parts = []
                images = []
                for part in content:
                    if part.get("type") == "text":
                        text_parts.append(part["text"])
                    elif part.get("type") == "image_url":
                        url = part["image_url"]["url"]
                        if url.startswith("data:"):
                            # Strip data:image/jpeg;base64, prefix
                            images.append(url.split(",", 1)[1])
                ollama_msg = {"role": msg["role"], "content": " ".join(text_parts)}
                if images:
                    ollama_msg["images"] = images
                ollama_messages.append(ollama_msg)
            else:
                ollama_messages.append(msg)

        # Build correct Ollama API URL:
        # base_url may be "https://api.ollama.com/v1" (OpenAI-compat) or "https://api.ollama.com"
        # Native Ollama chat endpoint is always at /api/chat (no /v1)
        base = settings.ollama_base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]  # strip /v1 — not part of native Ollama API path
        api_url = f"{base}/api/chat"

        payload = {"model": model, "messages": ollama_messages, "stream": False}
        headers = {"Authorization": f"Bearer {settings.ollama_api_key}"}

        print(f"[LLM] Ollama → {api_url}  model={model}  msgs={len(ollama_messages)}")
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(api_url, json=payload, headers=headers)
            if response.status_code != 200:
                body = response.text[:500]
                print(f"[LLM] Ollama HTTP {response.status_code}: {body}")
                raise RuntimeError(f"Ollama API returned HTTP {response.status_code}: {body}")
            result = response.json()["message"]["content"]
            print(f"[LLM] Ollama response ({len(result)} chars): {result[:300]}")
            return result

    async def _complete_gemini(self, messages: list[dict], system: str) -> str:
        from google import genai
        client = genai.Client(api_key=settings.google_api_key)
        model = self.model or "gemini-2.0-flash"

        # Build Gemini contents list from messages
        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": f"[System]: {system}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        for msg in messages:
            gemini_role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": msg["content"]}]})

        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
        )
        return response.text
