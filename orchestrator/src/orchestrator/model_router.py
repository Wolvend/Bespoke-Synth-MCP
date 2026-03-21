from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings


class ProviderError(RuntimeError):
    pass


@dataclass
class ProviderResponse:
    provider: str
    text: str
    raw: dict[str, Any]


class ModelRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(self, provider: str, system_prompt: str, user_prompt: str) -> ProviderResponse:
        if provider == "mock":
            return self._mock_response(user_prompt)
        if provider == "openai":
            return await self._openai_response(system_prompt, user_prompt)
        if provider == "anthropic":
            return await self._anthropic_response(system_prompt, user_prompt)
        if provider == "gemini":
            return await self._gemini_response(system_prompt, user_prompt)
        if provider == "ollama":
            return await self._ollama_response(system_prompt, user_prompt)
        if provider == "llama_cpp":
            return await self._llama_cpp_response(system_prompt, user_prompt)
        raise ProviderError(f"unsupported provider: {provider}")

    def _mock_response(self, user_prompt: str) -> ProviderResponse:
        payload: dict[str, Any] = {
            "goal": "Apply a safe parameter update inferred from the request",
            "requires_user_confirmation": False,
            "steps": [
                {
                    "tool": "bespoke.safe.set_param",
                    "arguments": {
                        "path": "filter~cutoff",
                        "value": 0.25,
                        "idempotency_key": "mock-plan-key",
                    },
                    "why": "default mock planning action",
                }
            ],
            "rollback": [
                {
                    "tool": "bespoke.safe.set_param",
                    "arguments": {
                        "path": "filter~cutoff",
                        "value": 0.10,
                        "idempotency_key": "mock-plan-rollback",
                    },
                }
            ],
        }
        if "snapshot" in user_prompt.lower():
            payload["steps"][0]["tool"] = "bespoke.safe.snapshot_load"
            payload["steps"][0]["arguments"] = {"name": "VerseA", "idempotency_key": "mock-snapshot"}
            payload["rollback"] = []
        return ProviderResponse(provider="mock", text=json.dumps(payload), raw=payload)

    async def _openai_response(self, system_prompt: str, user_prompt: str) -> ProviderResponse:
        if not self.settings.openai_api_key:
            raise ProviderError("OPENAI_API_KEY is not configured")
        url = f"{self.settings.openai_base_url.rstrip('/')}/responses"
        body = {
            "model": self.settings.openai_model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        text = payload.get("output_text")
        if not text:
            text = json.dumps(payload)
        return ProviderResponse(provider="openai", text=text, raw=payload)

    async def _anthropic_response(self, system_prompt: str, user_prompt: str) -> ProviderResponse:
        if not self.settings.anthropic_api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not configured")
        url = f"{self.settings.anthropic_base_url.rstrip('/')}/messages"
        headers = {
            "x-api-key": self.settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self.settings.anthropic_model,
            "max_tokens": 1200,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        text = "".join(part.get("text", "") for part in payload.get("content", []) if part.get("type") == "text")
        return ProviderResponse(provider="anthropic", text=text, raw=payload)

    async def _gemini_response(self, system_prompt: str, user_prompt: str) -> ProviderResponse:
        if not self.settings.gemini_api_key:
            raise ProviderError("GEMINI_API_KEY is not configured")
        model = self.settings.gemini_model
        url = (
            f"{self.settings.gemini_base_url.rstrip('/')}/models/{model}:generateContent"
            f"?key={self.settings.gemini_api_key}"
        )
        body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
            payload = response.json()
        candidates = payload.get("candidates", [])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts)
        return ProviderResponse(provider="gemini", text=text, raw=payload)

    async def _ollama_response(self, system_prompt: str, user_prompt: str) -> ProviderResponse:
        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/chat"
        body = {
            "model": self.settings.ollama_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
            payload = response.json()
        text = payload.get("message", {}).get("content", "")
        return ProviderResponse(provider="ollama", text=text, raw=payload)

    async def _llama_cpp_response(self, system_prompt: str, user_prompt: str) -> ProviderResponse:
        url = f"{self.settings.llama_cpp_base_url.rstrip('/')}/chat/completions"
        body = {
            "model": self.settings.llama_cpp_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=body, headers={"Authorization": "Bearer no-key"})
            response.raise_for_status()
            payload = response.json()
        choices = payload.get("choices", [])
        text = ""
        if choices:
            text = choices[0].get("message", {}).get("content", "")
        return ProviderResponse(provider="llama_cpp", text=text, raw=payload)
