"""
LLM Provider Abstraction

Supports multiple providers behind a single interface so we can switch
models without changing business logic. Defaults to OpenAI if configured,
falls back to Gemini when GOOGLE_API_KEY is set and AI_PROVIDER=gemini.
"""

from __future__ import annotations

import os
import json
from typing import Optional
import httpx


class LLMClient:
    async def chat_complete(self, system: str, user: str, response_json: bool = True) -> str:
        raise NotImplementedError


class OpenAIClient(LLMClient):
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))

    async def chat_complete(self, system: str, user: str, response_json: bool = True) -> str:
        assert self.api_key, "OPENAI_API_KEY required for OpenAIClient"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": 600,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()


class GeminiClient(LLMClient):
    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

    async def chat_complete(self, system: str, user: str, response_json: bool = True) -> str:
        assert self.api_key, "GOOGLE_API_KEY required for GeminiClient"
        # Generative Language API v1beta generateContent
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        # Construct content with system + user instructions
        contents = [
            {"role": "user", "parts": [{"text": f"System: {system}\n\nUser: {user}"}]}
        ]
        req = {"contents": contents}
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=req)
        r.raise_for_status()
        data = r.json()
        # Extract text
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        return text.strip()


def get_llm_client() -> Optional[LLMClient]:
    provider = (os.getenv("AI_PROVIDER") or "openai").lower()
    if provider == "openai" and os.getenv("OPENAI_API_KEY"):
        return OpenAIClient()
    if provider == "gemini" and (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        return GeminiClient()
    # Auto-detect
    if os.getenv("OPENAI_API_KEY"):
        return OpenAIClient()
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        return GeminiClient()
    return None


