"""Transport failure and confidentiality tests use mocked HTTP only."""

import asyncio
import json
from dataclasses import replace

import httpx
import pytest

from nexus_backend.provider import NebiusProvider, ProviderConfig, ProviderError

CONFIG = ProviderConfig("https://api.tokenfactory.nebius.com/v1/", "private-key-123456",
                        "nvidia/example-nemotron", timeout_seconds=0.1, backoff_seconds=0)


def completion(content='{"answer":1}', **message):
    return {"choices": [{"finish_reason": "stop", "message": {"content": content, **message}}]}


def request(handler, *, config=CONFIG, sleep=asyncio.sleep):
    provider = NebiusProvider(config, transport=httpx.MockTransport(handler), sleep=sleep)
    return asyncio.run(provider.complete([{"role": "user", "content": "diagnose"}],
                                         {"type": "object"}))


def test_structured_request_auth_and_never_returns_reasoning_metadata():
    requests = []

    def handler(req):
        requests.append(req)
        return httpx.Response(200, json=completion(reasoning_content="private internal reasoning"))

    assert request(handler) == '{"answer":1}'
    req = requests[0]
    assert str(req.url) == "https://api.tokenfactory.nebius.com/v1/chat/completions"
    assert req.headers["Authorization"] == f"Bearer {CONFIG.api_key}"
    payload = json.loads(req.content)
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["stream"] is False
    assert CONFIG.api_key not in req.content.decode()
    assert CONFIG.api_key not in repr(CONFIG)


@pytest.mark.parametrize("env", [{}, {"NEXUS_NEBIUS_API_KEY": "secret"}])
def test_missing_configuration_never_invents_provider_defaults(env):
    with pytest.raises(ProviderError, match="not configured") as caught:
        ProviderConfig.from_env(env)
    assert caught.value.code == "not_configured"


@pytest.mark.parametrize("url", [
    "http://api.tokenfactory.nebius.com/v1", "https://attacker.example/v1",
    "https://api.tokenfactory.nebius.com.attacker.example/v1",
    "https://secret@api.tokenfactory.nebius.com/v1",
    "https://api.tokenfactory.nebius.com/v1?key=secret",
    "https://api.tokenfactory.nebius.com/v1#secret",
    "https://api.tokenfactory.nebius.com/v1/chat/completions",
])
def test_configuration_rejects_insecure_or_ambiguous_secret_destinations(url):
    with pytest.raises(ProviderError):
        replace(CONFIG, base_url=url)


@pytest.mark.parametrize("kwargs", [
    {"max_retries": 4}, {"max_retries": True}, {"timeout_seconds": float("nan")},
    {"backoff_seconds": 10}, {"api_key": "line\nbreak"}, {"api_key": "secret\x00"},
    {"model": ""},
])
def test_configuration_bounds_runtime_and_headers(kwargs):
    with pytest.raises(ProviderError):
        replace(CONFIG, **kwargs)


def test_rate_limit_retries_bounded_and_respects_capped_retry_after():
    calls, delays = [], []

    async def sleep(delay):
        delays.append(delay)

    def handler(req):
        calls.append(req)
        return httpx.Response(429, headers={"Retry-After": "9999"},
                              json={"error": CONFIG.api_key})

    with pytest.raises(ProviderError) as caught:
        request(handler, sleep=sleep)
    assert caught.value.code == "rate_limited"
    assert len(calls) == 3 and delays == [2, 2]
    assert CONFIG.api_key not in str(caught.value)


def test_transient_failure_then_success():
    attempts = []

    def handler(req):
        attempts.append(req)
        return httpx.Response(503 if len(attempts) == 1 else 200, json=completion())

    assert request(handler) == '{"answer":1}'
    assert len(attempts) == 2


@pytest.mark.parametrize("status,code", [(401, "authentication_failed"),
                                       (403, "authentication_failed"), (400, "unavailable"),
                                       (302, "unavailable")])
def test_permanent_error_not_retried_and_body_never_exposed(status, code):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(status, text=CONFIG.api_key,
                              headers={"Location": "https://attacker.example"})

    with pytest.raises(ProviderError) as caught:
        request(handler)
    assert caught.value.code == code and len(calls) == 1
    assert CONFIG.api_key not in str(caught.value)


def test_timeout_exhaustion_hides_underlying_request_details():
    calls = []

    def handler(req):
        calls.append(req)
        raise httpx.ReadTimeout(CONFIG.api_key, request=req)

    with pytest.raises(ProviderError) as caught:
        request(handler)
    assert caught.value.code == "timeout" and len(calls) == 3
    assert CONFIG.api_key not in str(caught.value)


def test_wall_clock_timeout_bounds_slow_response():
    async def handler(req):
        await asyncio.sleep(1)
        return httpx.Response(200, json=completion())

    with pytest.raises(ProviderError) as caught:
        request(handler, config=replace(CONFIG, timeout_seconds=0.01, max_retries=0))
    assert caught.value.code == "timeout"


@pytest.mark.parametrize("payload,code", [
    (completion(refusal="Cannot comply"), "refused"),
    ({"choices": []}, "invalid_response"),
    ({"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]},
     "invalid_response"),
    (completion(content=None), "invalid_response"),
    (completion(content=""), "invalid_response"),
    (completion(content=CONFIG.api_key), "invalid_response"),
    (completion(content="x" * 70000), "invalid_response"),
])
def test_malformed_refused_truncated_or_secret_response_is_closed(payload, code):
    with pytest.raises(ProviderError) as caught:
        request(lambda req: httpx.Response(200, json=payload))
    assert caught.value.code == code
    assert CONFIG.api_key not in str(caught.value)


def test_input_cannot_accidentally_send_configured_key_in_prompt():
    requests = []
    provider = NebiusProvider(CONFIG, transport=httpx.MockTransport(lambda req: requests.append(req)))
    with pytest.raises(ProviderError) as caught:
        asyncio.run(provider.complete([{"content": CONFIG.api_key}], {}))
    assert caught.value.code == "invalid_input" and requests == []


def test_input_rejects_secret_even_when_json_serialization_escapes_it():
    config = replace(CONFIG, api_key='private"key\\value')
    requests = []
    provider = NebiusProvider(config, transport=httpx.MockTransport(lambda req: requests.append(req)))
    with pytest.raises(ProviderError) as caught:
        asyncio.run(provider.complete([{"content": config.api_key}], {}))
    assert caught.value.code == "invalid_input" and requests == []
