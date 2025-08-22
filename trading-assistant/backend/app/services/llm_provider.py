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
import asyncio
import time
import random


class LLMClient:
    async def chat_complete(self, system: str, user: str, response_json: bool = True, model: Optional[str] = None) -> str:
        raise NotImplementedError


# Global throttling and retries to mitigate provider 429s
_LLM_MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "2"))
_LLM_MIN_INTERVAL_MS = int(os.getenv("LLM_MIN_INTERVAL_MS", "250"))  # pacing between calls
_LLM_RETRY_MAX = int(os.getenv("LLM_RETRY_MAX", "3"))
_LLM_RETRY_BASE_MS = int(os.getenv("LLM_RETRY_BASE_MS", "500"))

_llm_semaphore = asyncio.Semaphore(_LLM_MAX_CONCURRENCY)
_llm_last_call_at = 0.0
_llm_lock = asyncio.Lock()


async def _paced_request(method: str, url: str, *, client: httpx.AsyncClient, **kwargs) -> httpx.Response:
    global _llm_last_call_at
    async with _llm_semaphore:
        # Ensure minimal pacing between outbound LLM calls
        async with _llm_lock:
            now = time.time()
            wait_s = max(0.0, (_llm_last_call_at + (_LLM_MIN_INTERVAL_MS / 1000.0)) - now)
            if wait_s > 0:
                await asyncio.sleep(wait_s)
            _llm_last_call_at = time.time()
        return await client.request(method, url, **kwargs)


async def _request_with_retries(method: str, url: str, *, headers: Optional[dict] = None, json: Optional[dict] = None) -> httpx.Response:
    backoff_ms = _LLM_RETRY_BASE_MS
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(1, _LLM_RETRY_MAX + 1):
            try:
                r = await _paced_request(method, url, client=client, headers=headers, json=json)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError("retryable status", request=r.request, response=r)
                return r
            except httpx.HTTPStatusError as e:
                code = getattr(e.response, "status_code", 0)
                if code in (429, 500, 502, 503, 504) and attempt < _LLM_RETRY_MAX:
                    # Exponential backoff with jitter
                    sleep_s = (backoff_ms / 1000.0) * (1.0 + random.random()*0.25)
                    await asyncio.sleep(sleep_s)
                    backoff_ms *= 2
                    continue
                raise


class OpenAIClient(LLMClient):
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))

    async def chat_complete(self, system: str, user: str, response_json: bool = True, model: Optional[str] = None) -> str:
        assert self.api_key, "OPENAI_API_KEY required for OpenAIClient"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": (model or self.model),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": 600,
        }
        r = await _request_with_retries("POST", "https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()


class GeminiClient(LLMClient):
    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

    async def chat_complete(self, system: str, user: str, response_json: bool = True, model: Optional[str] = None) -> str:
        assert self.api_key, "GOOGLE_API_KEY required for GeminiClient"
        url_model = (model or self.model)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{url_model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600},
        }
        r = await _request_with_retries("POST", url, json=payload)
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

    async def chat_complete(self, system: str, user: str, response_json: bool = True, model: Optional[str] = None) -> str:
        assert self.api_key, "ANTHROPIC_API_KEY required for AnthropicClient"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": (model or self.model),
            "max_tokens": 600,
            "temperature": self.temperature,
            "system": system,
            "messages": [
                {"role": "user", "content": user}
            ],
        }
        r = await _request_with_retries("POST", "https://api.anthropic.com/v1/messages", headers=headers, json=body)
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

    async def chat_complete(self, system: str, user: str, response_json: bool = True, model: Optional[str] = None) -> str:
        assert self.api_key, "MISTRAL_API_KEY required for MistralClient"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        headers["Accept"] = "application/json"
        payload = {
            "model": (model or self.model),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": 600,
        }
        r = await _request_with_retries("POST", "https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()


class GroqClient(LLMClient):
    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
        self.temperature = float(os.getenv("GROQ_TEMPERATURE", "0.2"))

    async def chat_complete(self, system: str, user: str, response_json: bool = True, model: Optional[str] = None) -> str:
        assert self.api_key, "GROQ_API_KEY required for GroqClient"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        headers["Accept"] = "application/json"
        payload = {
            "model": (model or self.model),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": 600,
        }
        # Groq exposes OpenAI-compatible endpoint
        r = await _request_with_retries("POST", "https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        if r.status_code >= 400:
            # Surface Groq error body for easier debugging (often 'model_not_found' or validation errors)
            try:
                err_json = r.json()
            except Exception:
                err_json = {"error": r.text}
            raise RuntimeError(f"groq_error: status={r.status_code} model={(model or self.model)} details={err_json}")
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


def suggested_models() -> Dict[str, List[str]]:
    """Return a curated list of commonly available, recent models per provider."""
    return {
        "openai": ["gpt-4o", "gpt-4o-mini", "o4-mini"],
        "gemini": ["gemini-2.5-pro", "gemini-1.5-pro", "gemini-1.5-flash"],
        "anthropic": ["claude-3-5-sonnet-latest", "claude-3-opus-latest", "claude-3-haiku-latest"],
        "mistral": ["mistral-large-latest", "ministral-8b-latest"],
        # Keep Groq list fresh; add commonly available current models
        "groq": [
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        ],
    }


def is_valid_model_for_provider(provider: Optional[str], model: Optional[str]) -> bool:
    if not provider or not model:
        return False
    prov = provider.lower()
    models = suggested_models().get(prov) or []
    if model in models:
        return True
    # Allow some flexible prefixes for providers where models evolve quickly
    if prov == "groq" and (model.startswith("llama-") or model.startswith("mixtral")):
        return True
    if prov == "gemini" and model.startswith("gemini-"):
        return True
    if prov == "openai" and (model.startswith("gpt-") or model.startswith("o4")):
        return True
    if prov == "anthropic" and model.startswith("claude-"):
        return True
    if prov == "mistral" and (model.startswith("mistral") or model.startswith("ministral")):
        return True
    return False


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


