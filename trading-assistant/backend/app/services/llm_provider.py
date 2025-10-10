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


async def _request_with_retries(
    method: str,
    url: str,
    *,
    headers: Optional[dict] = None,
    json: Optional[dict] = None,
    retry_max: Optional[int] = None,
    retry_base_ms: Optional[int] = None,
) -> httpx.Response:
    """HTTP request with pacing + retries for transient provider errors.

    - Retries on 429/5xx with exponential backoff + jitter
    - Honors Retry-After header when present
    - Emits concise diagnostics when APP_DEBUG is true
    """
    max_attempts = int(retry_max or _LLM_RETRY_MAX)
    backoff_ms = int(retry_base_ms or _LLM_RETRY_BASE_MS)
    debug_mode = str(os.getenv("APP_DEBUG", "true")).lower() in ("1", "true", "yes", "on")
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                r = await _paced_request(method, url, client=client, headers=headers, json=json)
                if r.status_code in (429, 500, 502, 503, 504):
                    if debug_mode:
                        try:
                            body = r.json()
                            body_str = json.dumps(body)[:300]
                        except Exception:
                            body_str = (r.text or "")[:300]
                        print(f"[LLM] retryable status={r.status_code} attempt={attempt}/{max_attempts} url={url} body={body_str}")
                    raise httpx.HTTPStatusError("retryable status", request=r.request, response=r)
                return r
            except httpx.HTTPStatusError as e:
                code = getattr(e.response, "status_code", 0)
                if code in (429, 500, 502, 503, 504) and attempt < max_attempts:
                    # Respect provider Retry-After if present
                    retry_after = 0.0
                    try:
                        ra = e.response.headers.get("Retry-After")  # type: ignore[attr-defined]
                        if ra:
                            if ra.isdigit():
                                retry_after = float(ra)
                            else:
                                # HTTP date format; default small wait if parsing fails
                                retry_after = 1.0
                    except Exception:
                        retry_after = 0.0
                    # Exponential backoff with jitter, plus any Retry-After
                    sleep_s = retry_after + (backoff_ms / 1000.0) * (1.0 + random.random() * 0.25)
                    await asyncio.sleep(max(sleep_s, 0.1))
                    backoff_ms = int(backoff_ms * 2)
                    continue
                if debug_mode:
                    try:
                        err_body = e.response.json()  # type: ignore[attr-defined]
                        err_str = json.dumps(err_body)[:300]
                    except Exception:
                        err_str = (getattr(e.response, "text", "") or "")[:300]
                    print(f"[LLM] giving up url={url} status={code} after attempt={attempt}: {err_str}")
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
        chosen_model = (model or self.model)
        
        # Determine temperature based on model
        if chosen_model.startswith("gpt-5-nano"):
            temperature = 1.0  # gpt-5-nano only supports temperature=1 (default)
        else:
            temperature = self.temperature
            
        payload = {
            "model": chosen_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        
        # Use max_completion_tokens for newer models like gpt-5-nano
        if chosen_model.startswith("gpt-5") or chosen_model.startswith("o4"):
            payload["max_completion_tokens"] = 600
        else:
            payload["max_tokens"] = 600
        # 1st attempt with configured model
        r = await _request_with_retries(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            retry_base_ms=max(_LLM_RETRY_BASE_MS, 1000),
        )
        if r.status_code >= 400:
            # If configured model is invalid or uses the Responses API only, retry with a safe chat-completions model
            fallback_model = "gpt-4o-mini"
            try:
                err_json = r.json()
            except Exception:
                err_json = {"error": r.text}
            err = (err_json or {}).get("error") or {}
            err_code = err.get("code")
            err_type = err.get("type") or (err_json or {}).get("type")
            err_msg = (err.get("message") or "").lower()
            requires_responses_api = ("responses api" in err_msg) or ("does not support" in err_msg and "chat" in err_msg)
            if (err_code == "model_not_found" or requires_responses_api) and chosen_model != fallback_model:
                payload["model"] = fallback_model
                
                # Update temperature for fallback model
                if fallback_model.startswith("gpt-5-nano"):
                    payload["temperature"] = 1.0
                else:
                    payload["temperature"] = self.temperature
                
                # Update token parameter for fallback model
                if fallback_model.startswith("gpt-5") or fallback_model.startswith("o4"):
                    payload["max_completion_tokens"] = 600
                    payload.pop("max_tokens", None)
                else:
                    payload["max_tokens"] = 600
                    payload.pop("max_completion_tokens", None)
                r2 = await _request_with_retries(
                    "POST",
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    retry_base_ms=max(_LLM_RETRY_BASE_MS, 1000),
                )
                if r2.status_code >= 400:
                    try:
                        err_json2 = r2.json()
                    except Exception:
                        err_json2 = {"error": r2.text}
                    raise RuntimeError(f"openai_error: status={r2.status_code} model={payload['model']} details={err_json2}")
                data2 = r2.json()
                return data2["choices"][0]["message"]["content"].strip()
            # Otherwise, surface the original error for visibility
            raise RuntimeError(f"openai_error: status={r.status_code} model={chosen_model} details={err_json}")
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()


class GeminiClient(LLMClient):
    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

    async def chat_complete(self, system: str, user: str, response_json: bool = True, model: Optional[str] = None) -> str:
        assert self.api_key, "GOOGLE_API_KEY required for GeminiClient"
        url_model = (model or self.model)
        # Gemini 2.x families are available under v1; earlier ones under v1beta
        api_ver = "v1" if url_model.startswith("gemini-2") else "v1beta"
        url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{url_model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600},
        }
        r = await _request_with_retries("POST", url, json=payload)
        if r.status_code >= 400:
            try:
                err_json = r.json()
            except Exception:
                err_json = {"error": r.text}
            raise RuntimeError(f"gemini_error: status={r.status_code} model={url_model} details={err_json}")
        data = r.json() or {}
        cands = data.get("candidates") or []
        if not cands:
            return ""
        content = cands[0].get("content") or {}
        parts = content.get("parts") or []
        if parts:
            return "".join(p.get("text", "") for p in parts).strip()
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
    """Return a curated list of commonly available, recent models per provider.

    Order matters: first item is considered the recommended default for general reasoning + JSON output.
    """
    return {
        # Quality/cost balanced reasoning + JSON. Keep chat-completions compatible model first.
        "openai": ["gpt-4o-mini", "gpt-4o", "o4-mini"],
        # Gemini: Pro for quality, Flash for speed
        "gemini": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.5-pro"],
        # Anthropic: Sonnet (latest) best general model
        "anthropic": ["claude-3-5-sonnet-latest", "claude-3-opus-latest", "claude-3-haiku-latest"],
        # Mistral: Large for quality, Minstral for speed
        "mistral": ["mistral-large-latest", "ministral-8b-latest"],
        # Groq: latest Llama recommended first, then others
        "groq": [
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        ],
    }

# --- Live model discovery (for "latest models" selection) ---

_LATEST_MODELS_CACHE: Dict[str, List[str]] = {}
_LATEST_MODELS_TS: float = 0.0


def _unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in items:
        if v not in seen:
            out.append(v)
            seen.add(v)
    return out


async def _fetch_openai_models() -> List[str]:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return []
    headers = {"Authorization": f"Bearer {key}"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get("https://api.openai.com/v1/models", headers=headers)
        r.raise_for_status()
        data = r.json() or {}
        ids = [str(m.get("id")) for m in (data.get("data") or []) if isinstance(m, dict)]
        # Keep only relevant chat-completions models
        ids = [i for i in ids if i.startswith(("gpt-4", "gpt-4o", "o4"))]
        # Prefer small/fast first
        pref = ["o4-mini", "gpt-4o-mini", "gpt-4o", "o4"]
        ids_sorted = sorted(ids, key=lambda x: (pref.index(x) if x in pref else 999, x))
        return _unique_keep_order(ids_sorted)
    except Exception:
        return []


async def _fetch_gemini_models() -> List[str]:
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        return []
    out: List[str] = []
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            for base in ("v1", "v1beta"):
                try:
                    r = await client.get(f"https://generativelanguage.googleapis.com/{base}/models?key={key}")
                    if r.status_code != 200:
                        continue
                    data = r.json() or {}
                    names = [str(m.get("name")) for m in (data.get("models") or []) if isinstance(m, dict)]
                    # 'name' comes like 'models/gemini-1.5-pro'; normalize to the id segment
                    for n in names:
                        if "/" in n:
                            n = n.split("/")[-1]
                        if n.startswith("gemini-"):
                            out.append(n)
                except Exception:
                    continue
    except Exception:
        return []
    # Prioritize newest flash/pro families
    pref = ["gemini-2.0-flash", "gemini-2.5-pro", "gemini-1.5-pro", "gemini-1.5-flash"]
    out_sorted = sorted(out, key=lambda x: (pref.index(x) if x in pref else 999, x))
    return _unique_keep_order(out_sorted)


async def _fetch_groq_models() -> List[str]:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return []
    headers = {"Authorization": f"Bearer {key}"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get("https://api.groq.com/openai/v1/models", headers=headers)
        r.raise_for_status()
        data = r.json() or {}
        ids = [str(m.get("id")) for m in (data.get("data") or []) if isinstance(m, dict)]
        ids = [i for i in ids if i.startswith(("llama-", "mixtral"))]
        # Prefer the 3.3 70B variant when present
        pref = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
        ids_sorted = sorted(ids, key=lambda x: (pref.index(x) if x in pref else 999, x))
        return _unique_keep_order(ids_sorted)
    except Exception:
        return []


async def _fetch_mistral_models() -> List[str]:
    key = os.getenv("MISTRAL_API_KEY")
    if not key:
        return []
    headers = {"Authorization": f"Bearer {key}"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get("https://api.mistral.ai/v1/models", headers=headers)
        r.raise_for_status()
        data = r.json() or {}
        ids = [str(m.get("id")) for m in (data.get("data") or []) if isinstance(m, dict)]
        ids = [i for i in ids if i.startswith(("mistral", "ministral"))]
        pref = ["mistral-large-latest", "ministral-8b-latest"]
        ids_sorted = sorted(ids, key=lambda x: (pref.index(x) if x in pref else 999, x))
        return _unique_keep_order(ids_sorted)
    except Exception:
        return []


async def get_models_map(prefer_live: bool = True) -> Dict[str, List[str]]:
    """Return latest models for each configured provider.

    - If prefer_live is True, query provider listing endpoints when keys are present.
    - Always fall back to curated suggested_models() to ensure non-empty lists.
    """
    global _LATEST_MODELS_CACHE, _LATEST_MODELS_TS
    base = suggested_models()
    if not prefer_live:
        _LATEST_MODELS_CACHE = base
        _LATEST_MODELS_TS = time.time()
        return base

    # Try live discovery concurrently
    tasks = []
    results: Dict[str, List[str]] = {}

    # Schedule tasks only when API keys exist
    if os.getenv("OPENAI_API_KEY"):
        tasks.append(("openai", _fetch_openai_models()))
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        tasks.append(("gemini", _fetch_gemini_models()))
    if os.getenv("GROQ_API_KEY"):
        tasks.append(("groq", _fetch_groq_models()))
    if os.getenv("MISTRAL_API_KEY"):
        tasks.append(("mistral", _fetch_mistral_models()))
    # Anthropic has no public list endpoint – keep curated
    results.update({"anthropic": base.get("anthropic", [])})

    if tasks:
        done = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
        for (name, _), vals in zip(tasks, done):
            if isinstance(vals, Exception):
                results[name] = base.get(name, [])
            else:
                results[name] = vals or base.get(name, [])

    # Ensure all providers exist
    for prov, models in base.items():
        if prov not in results or not results[prov]:
            results[prov] = models

    _LATEST_MODELS_CACHE = results
    _LATEST_MODELS_TS = time.time()
    return results


def is_valid_model_for_provider(provider: Optional[str], model: Optional[str]) -> bool:
    if not provider or not model:
        return False
    prov = provider.lower()
    # Prefer live-discovered models when available
    models = (_LATEST_MODELS_CACHE.get(prov) or suggested_models().get(prov) or [])
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


