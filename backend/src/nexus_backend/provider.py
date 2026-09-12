"""Bounded, secret-safe Nebius chat transport; constructing it never calls the API."""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import ClassVar
from urllib.parse import urlsplit

import httpx

MAX_RESPONSE_BYTES = 65_536
MAX_REQUEST_BYTES = 131_072


def generation_schema(value: object) -> object:
    """Project constraints supported by Nebius's grammar compiler.

    Its live endpoint rejects uniqueItems. Keep that constraint in PLAN_SCHEMA
    for local validation; removing it here does not authorize invalid plans.
    """
    if isinstance(value, dict):
        return {key: generation_schema(item) for key, item in value.items()
                if key != "uniqueItems"}
    if isinstance(value, list):
        return [generation_schema(item) for item in value]
    return value


class ProviderError(Exception):
    """Only fixed public messages cross the transport boundary."""

    MESSAGES: ClassVar[dict[str, str]] = {
        "not_configured": "The live model is not configured.",
        "invalid_config": "The live model configuration is invalid.",
        "invalid_input": "The model input is invalid or too large.",
        "authentication_failed": "The model service rejected its credentials.",
        "rate_limited": "The model service is temporarily rate limited.",
        "timeout": "The model service did not respond before the deadline.",
        "unavailable": "The model service is temporarily unavailable.",
        "refused": "The model declined this diagnosis request.",
        "invalid_response": "The model returned an unusable diagnosis response.",
    }

    def __init__(self, code: str):
        self.code = code if code in self.MESSAGES else "unavailable"
        super().__init__(self.MESSAGES[self.code])


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    api_key: str = field(repr=False)
    model: str
    timeout_seconds: float = 20
    max_retries: int = 2
    backoff_seconds: float = 0.25
    enable_thinking: bool | None = None
    max_output_tokens: int = 2048

    def __post_init__(self):
        try:
            url = urlsplit(self.base_url)
            valid_url = (
                url.scheme == "https" and url.hostname
                and (url.hostname == "nebius.com" or url.hostname.endswith(".nebius.com"))
                and not url.username and not url.password and not url.query and not url.fragment
                and url.path.rstrip("/") == "/v1" and url.port in (None, 443)
            )
            valid_values = (
                isinstance(self.api_key, str) and 1 <= len(self.api_key) <= 4096
                and all(33 <= ord(c) <= 126 for c in self.api_key)
                and isinstance(self.model, str) and 1 <= len(self.model) <= 256
                and all(33 <= ord(c) <= 126 for c in self.model)
                and type(self.max_retries) is int and 0 <= self.max_retries <= 3
                and type(self.timeout_seconds) in (int, float)
                and math.isfinite(self.timeout_seconds) and 0 < self.timeout_seconds <= 60
                and type(self.backoff_seconds) in (int, float)
                and math.isfinite(self.backoff_seconds) and 0 <= self.backoff_seconds <= 2
                and (self.enable_thinking is None or type(self.enable_thinking) is bool)
                and type(self.max_output_tokens) is int and 256 <= self.max_output_tokens <= 8192
            )
        except (TypeError, ValueError, AttributeError):
            raise ProviderError("invalid_config") from None
        if not valid_url or not valid_values:
            raise ProviderError("invalid_config")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> ProviderConfig:
        env = os.environ if environ is None else environ
        values = [env.get(name, "") for name in (
            "NEXUS_NEBIUS_BASE_URL", "NEXUS_NEBIUS_API_KEY", "NEXUS_NVIDIA_MODEL",
        )]
        if not all(values):
            raise ProviderError("not_configured")
        thinking = env.get("NEXUS_NEBIUS_ENABLE_THINKING") or ""
        if not isinstance(thinking, str):
            raise ProviderError("invalid_config")
        thinking = thinking.lower()
        if thinking not in ("", "true", "false"):
            raise ProviderError("invalid_config")
        try:
            max_tokens = int(env.get("NEXUS_NEBIUS_MAX_OUTPUT_TOKENS") or "2048")
        except (TypeError, ValueError):
            raise ProviderError("invalid_config") from None
        return cls(*values, enable_thinking=None if not thinking else thinking == "true",
                   max_output_tokens=max_tokens)


class NebiusProvider:
    """Non-streaming structured-output client with injectable mock HTTP transport."""

    def __init__(
        self, config: ProviderConfig, *, transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.config = config
        self._transport = transport
        self._sleep = sleep
        self.last_completion: dict | None = None

    def reject_secret_echo(self, value: object, *, code: str = "invalid_response") -> None:
        """Inspect decoded JSON strings so escaping cannot hide an echoed credential."""
        pending = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, str) and self.config.api_key in item:
                raise ProviderError(code)
            if isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)

    async def complete(self, messages: list[dict], schema: dict) -> str:
        self.last_completion = None
        started = time.monotonic()
        body = {
            "model": self.config.model, "messages": messages, "temperature": 0,
            "max_tokens": self.config.max_output_tokens, "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "nexus_diagnosis_v1", "strict": True,
                                "schema": generation_schema(schema)},
            },
        }
        if self.config.enable_thinking is not None:
            body["chat_template_kwargs"] = {"enable_thinking": self.config.enable_thinking}
        try:
            encoded = json.dumps(body, allow_nan=False).encode()
        except (TypeError, ValueError, RecursionError):
            raise ProviderError("invalid_input") from None
        if len(encoded) > MAX_REQUEST_BYTES or self.config.api_key.encode() in encoded:
            raise ProviderError("invalid_input")
        self.reject_secret_echo(body, code="invalid_input")
        last_code = "unavailable"
        async with httpx.AsyncClient(
            transport=self._transport, timeout=self.config.timeout_seconds,
            follow_redirects=False, trust_env=False,
        ) as client:
            for attempt in range(self.config.max_retries + 1):
                retry_after = 0.0
                try:
                    # HTTP phase timeouts alone do not bound a server sending endless chunks.
                    async with asyncio.timeout(self.config.timeout_seconds):
                        async with client.stream(
                            "POST", self.config.base_url.rstrip("/") + "/chat/completions",
                            headers={"Authorization": f"Bearer {self.config.api_key}",
                                     "Content-Type": "application/json"},
                            content=encoded,
                        ) as response:
                            if response.status_code in (401, 403):
                                raise ProviderError("authentication_failed")
                            if response.status_code == 429 or response.status_code >= 500:
                                last_code = ("rate_limited" if response.status_code == 429
                                             else "unavailable")
                                try:
                                    retry_after = min(2.0, max(0.0, float(
                                        response.headers.get("retry-after", "0")
                                    )))
                                except ValueError:
                                    retry_after = 0.0
                            elif response.status_code != 200:
                                raise ProviderError("unavailable")
                            else:
                                chunks = bytearray()
                                async for chunk in response.aiter_bytes():
                                    chunks.extend(chunk)
                                    if len(chunks) > MAX_RESPONSE_BYTES:
                                        raise ProviderError("invalid_response")
                                content = self._content(bytes(chunks))
                                self.last_completion["elapsed_ms"] = round(
                                    (time.monotonic() - started) * 1000
                                )
                                self.last_completion["attempts"] = attempt + 1
                                return content
                except (httpx.TimeoutException, TimeoutError):
                    last_code = "timeout"
                except httpx.RequestError:
                    last_code = "unavailable"
                if attempt < self.config.max_retries:
                    await self._sleep(max(retry_after, self.config.backoff_seconds * 2 ** attempt))
        raise ProviderError(last_code)

    def _content(self, raw: bytes) -> str:
        try:
            payload = json.loads(raw)
            choices = payload["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError
            choice = choices[0]
            message = choice["message"]
            if message.get("refusal") or choice.get("finish_reason") == "content_filter":
                raise ProviderError("refused")
            if choice.get("finish_reason") != "stop":
                raise ValueError
            content = message["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError
            if self.config.api_key in content or len(content.encode()) > 32_768:
                raise ValueError
            # Evidence records are an allowlisted projection, never a raw response.
            metadata = {"requested_model": self.config.model, "finish_reason": "stop"}
            for source, target in (("model", "response_model"), ("id", "response_id")):
                value = payload.get(source)
                if (isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_./:-]{1,256}", value)
                        and self.config.api_key not in value):
                    metadata[target] = value
            usage = payload.get("usage")
            if isinstance(usage, dict):
                metadata["usage"] = {key: usage[key] for key in
                                     ("prompt_tokens", "completion_tokens", "total_tokens")
                                     if type(usage.get(key)) is int and usage[key] >= 0}
            self.last_completion = metadata
            return content
        except (ValueError, KeyError, IndexError, TypeError, AttributeError, RecursionError):
            raise ProviderError("invalid_response") from None
