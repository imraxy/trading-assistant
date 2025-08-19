"""
LLM Provider Abstraction

Supports multiple providers behind a single interface so we can switch
models without changing business logic. Defaults to OpenAI if configured,
falls back to Gemini when GOOGLE_API_KEY is set and AI_PROVIDER=gemini.
"""

from __future__ import annotations

import os
import json
from typing import Optional, List, Dict
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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json() or {}
        cands = data.get("candidates") or []
        if not cands:
            return ""
        content = cands[0].get("content") or {}
        parts = content.get("parts") or []
        if parts:
            return "".join(p.get("text", "") for p in parts).strip()
        # Fallback fields
        return (content.get("text") or "").strip()


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


def get_llm_clients() -> List[LLMClient]:
    """Return available clients in preference order based on AI_PROVIDER.

    If AI_PROVIDER is set, prefer that provider first, then fall back to the
    other if configured. Otherwise, return all configured providers with OpenAI
    first by default.
    """
    preferred = (os.getenv("AI_PROVIDER") or "openai").lower()
    have_openai = bool(os.getenv("OPENAI_API_KEY"))
    have_gemini = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    order: List[LLMClient] = []
    if preferred == "openai":
        if have_openai:
            order.append(OpenAIClient())
        if have_gemini:
            order.append(GeminiClient())
    elif preferred == "gemini":
        if have_gemini:
            order.append(GeminiClient())
        if have_openai:
            order.append(OpenAIClient())
    else:
        if have_openai:
            order.append(OpenAIClient())
        if have_gemini:
            order.append(GeminiClient())
    return order


# --- Additional providers: Anthropic, Mistral, Groq (OpenAI-compatible) ---

class AnthropicClient(LLMClient):
    def __init__(self) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        self.temperature = float(os.getenv("ANTHROPIC_TEMPERATURE", "0.2"))

    async def chat_complete(self, system: str, user: str, response_json: bool = True) -> str:
        assert self.api_key, "ANTHROPIC_API_KEY required for AnthropicClient"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": 600,
            "temperature": self.temperature,
            "system": system,
            "messages": [
                {"role": "user", "content": user}
            ],
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
        try:
            return "".join(part.get("text", "") for part in (data.get("content") or []))
        except Exception:
            # Older format
            return data.get("content", "")


class MistralClient(LLMClient):
    def __init__(self) -> None:
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.model = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
        self.temperature = float(os.getenv("MISTRAL_TEMPERATURE", "0.2"))

    async def chat_complete(self, system: str, user: str, response_json: bool = True) -> str:
        assert self.api_key, "MISTRAL_API_KEY required for MistralClient"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
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
            r = await client.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()


class GroqClient(LLMClient):
    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
        self.temperature = float(os.getenv("GROQ_TEMPERATURE", "0.2"))

    async def chat_complete(self, system: str, user: str, response_json: bool = True) -> str:
        assert self.api_key, "GROQ_API_KEY required for GroqClient"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": 600,
        }
        # Groq exposes OpenAI-compatible endpoint
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()


def available_providers() -> Dict[str, Dict[str, bool]]:
    """Return a dict of providers -> availability flags and env model used."""
    return {
        "openai": {"available": bool(os.getenv("OPENAI_API_KEY")), "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini")},
        "gemini": {"available": bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")), "model": os.getenv("GEMINI_MODEL", "gemini-1.5-pro")},
        "anthropic": {"available": bool(os.getenv("ANTHROPIC_API_KEY")), "model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")},
        "mistral": {"available": bool(os.getenv("MISTRAL_API_KEY")), "model": os.getenv("MISTRAL_MODEL", "mistral-large-latest")},
        "groq": {"available": bool(os.getenv("GROQ_API_KEY")), "model": os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")},
    }


def get_llm_client_for(provider: Optional[str]) -> Optional[LLMClient]:
    if not provider:
        return get_llm_client()
    p = provider.lower()
    if p == "openai" and os.getenv("OPENAI_API_KEY"):
        return OpenAIClient()
    if p == "gemini" and (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        return GeminiClient()
    if p == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicClient()
    if p == "mistral" and os.getenv("MISTRAL_API_KEY"):
        return MistralClient()
    if p == "groq" and os.getenv("GROQ_API_KEY"):
        return GroqClient()
    return None


