"""Parse API requests and responses to extract token counts and model info."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedRequest:
    provider: str
    model: str
    stream: bool = False


@dataclass
class ParsedResponse:
    input_tokens: int = 0
    output_tokens: int = 0
    model: Optional[str] = None


def detect_provider(path: str, headers: dict[str, str]) -> str:
    if "/anthropic/" in path or "anthropic" in headers.get("host", ""):
        return "anthropic"
    if "bedrock" in headers.get("host", "") or "bedrock-runtime" in path:
        return "bedrock"
    return "openai"


def parse_request(body: bytes, path: str, headers: dict[str, str]) -> Optional[ParsedRequest]:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    provider = detect_provider(path, headers)
    model = data.get("model", "unknown")
    stream = data.get("stream", False)

    if provider == "bedrock":
        model = _extract_bedrock_model(path) or model

    return ParsedRequest(provider=provider, model=model, stream=stream)


def parse_response(body: bytes, provider: str) -> ParsedResponse:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ParsedResponse()

    if provider == "anthropic":
        return _parse_anthropic_response(data)
    elif provider == "bedrock":
        return _parse_bedrock_response(data)
    return _parse_openai_response(data)


def parse_stream_chunk(chunk: bytes, provider: str) -> ParsedResponse:
    text = chunk.decode("utf-8", errors="ignore")
    result = ParsedResponse()

    for line in text.split("\n"):
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue

        if provider == "openai":
            usage = data.get("usage")
            if usage:
                result.input_tokens = usage.get("prompt_tokens", 0)
                result.output_tokens = usage.get("completion_tokens", 0)
        elif provider == "anthropic":
            if data.get("type") == "message_delta":
                usage = data.get("usage", {})
                result.output_tokens = usage.get("output_tokens", 0)
            elif data.get("type") == "message_start":
                msg = data.get("message", {})
                usage = msg.get("usage", {})
                result.input_tokens = usage.get("input_tokens", 0)

    return result


def _parse_openai_response(data: dict) -> ParsedResponse:
    usage = data.get("usage", {})
    return ParsedResponse(
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
        model=data.get("model"),
    )


def _parse_anthropic_response(data: dict) -> ParsedResponse:
    usage = data.get("usage", {})
    return ParsedResponse(
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        model=data.get("model"),
    )


def _parse_bedrock_response(data: dict) -> ParsedResponse:
    usage = data.get("usage", {})
    return ParsedResponse(
        input_tokens=usage.get("inputTokens", usage.get("input_tokens", 0)),
        output_tokens=usage.get("outputTokens", usage.get("output_tokens", 0)),
    )


def _extract_bedrock_model(path: str) -> Optional[str]:
    # /model/{modelId}/invoke or /model/{modelId}/converse
    parts = path.split("/")
    for i, part in enumerate(parts):
        if part == "model" and i + 1 < len(parts):
            return parts[i + 1]
    return None
