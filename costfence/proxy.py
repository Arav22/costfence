"""FastAPI reverse proxy with real-time cost tracking and budget enforcement."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from .budget import BudgetEnforcer, BudgetLimits
from .config import load_config
from .db import UsageDB
from .parser import ParsedResponse, parse_request, parse_response, parse_stream_chunk
from .pricing import get_pricing


_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    _state["config"] = config
    _state["db"] = UsageDB()
    _state["session_id"] = uuid.uuid4().hex[:12]
    _state["enforcer"] = BudgetEnforcer(
        BudgetLimits(
            per_session=config.get("budgets", {}).get("per_session"),
            per_hour=config.get("budgets", {}).get("per_hour"),
            per_day=config.get("budgets", {}).get("per_day"),
            per_project=config.get("budgets", {}).get("per_project"),
        )
    )
    _state["client"] = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
    _state["start_time"] = time.time()
    yield
    await _state["client"].aclose()
    _state["db"].close()


app = FastAPI(title="costfence", lifespan=lifespan)


def _resolve_upstream(provider: str) -> str:
    targets = _state["config"].get("targets", {})
    if provider in targets:
        return targets[provider]
    defaults = {
        "openai": "https://api.openai.com",
        "anthropic": "https://api.anthropic.com",
    }
    return defaults.get(provider, "https://api.openai.com")


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str) -> Response:
    enforcer: BudgetEnforcer = _state["enforcer"]
    db: UsageDB = _state["db"]
    config = _state["config"]

    violation = enforcer.check_budget()
    if violation:
        return Response(
            content=f'{{"error": {{"message": "costfence: {violation}", "type": "budget_exceeded"}}}}',
            status_code=429,
            media_type="application/json",
        )

    body = await request.body()
    headers = dict(request.headers)
    parsed_req = parse_request(body, f"/{path}", headers)

    provider = parsed_req.provider if parsed_req else "openai"
    model = parsed_req.model if parsed_req else "unknown"
    is_stream = parsed_req.stream if parsed_req else False

    upstream = _resolve_upstream(provider)
    url = f"{upstream}/{path}"

    fwd_headers = _forward_headers(headers)

    if is_stream:
        return await _handle_streaming(url, fwd_headers, body, provider, model, enforcer, db, config)

    client: httpx.AsyncClient = _state["client"]
    resp = await client.request(
        method=request.method,
        url=url,
        content=body,
        headers=fwd_headers,
    )

    parsed_resp = parse_response(resp.content, provider)
    _record_usage(provider, model, parsed_resp, enforcer, db, config)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type"),
    )


async def _handle_streaming(
    url: str,
    headers: dict,
    body: bytes,
    provider: str,
    model: str,
    enforcer: BudgetEnforcer,
    db: UsageDB,
    config: dict,
) -> StreamingResponse:
    client: httpx.AsyncClient = _state["client"]
    req = client.build_request("POST", url, content=body, headers=headers)

    accumulated = ParsedResponse()

    async def stream_with_tracking():
        nonlocal accumulated
        resp = await client.send(req, stream=True)
        try:
            async for chunk in resp.aiter_bytes():
                parsed = parse_stream_chunk(chunk, provider)
                if parsed.input_tokens:
                    accumulated.input_tokens = parsed.input_tokens
                if parsed.output_tokens:
                    accumulated.output_tokens = parsed.output_tokens
                yield chunk
        finally:
            await resp.aclose()
            _record_usage(provider, model, accumulated, enforcer, db, config)

    return StreamingResponse(stream_with_tracking(), media_type="text/event-stream")


def _record_usage(
    provider: str,
    model: str,
    parsed: ParsedResponse,
    enforcer: BudgetEnforcer,
    db: UsageDB,
    config: dict,
) -> None:
    if parsed.model:
        model = parsed.model

    pricing = get_pricing(provider, model, config.get("pricing"))
    cost = (
        parsed.input_tokens * pricing.input_per_million / 1_000_000
        + parsed.output_tokens * pricing.output_per_million / 1_000_000
    )

    enforcer.record_spend(cost)
    db.log(
        provider=provider,
        model=model,
        input_tokens=parsed.input_tokens,
        output_tokens=parsed.output_tokens,
        cost=cost,
        project=config.get("project"),
        session_id=_state.get("session_id"),
    )


def _forward_headers(headers: dict[str, str]) -> dict[str, str]:
    skip = {"host", "content-length", "transfer-encoding"}
    return {k: v for k, v in headers.items() if k.lower() not in skip}


@app.get("/costfence/status")
async def status():
    enforcer: BudgetEnforcer = _state["enforcer"]
    db: UsageDB = _state["db"]
    spend = enforcer.get_spend()
    remaining = enforcer.get_remaining()
    tokens = db.get_token_totals(since=_state.get("start_time"))
    return {
        "spend": spend,
        "remaining": remaining,
        "tokens": tokens,
        "session_id": _state.get("session_id"),
        "budgets": _state["config"].get("budgets", {}),
    }


@app.post("/costfence/reset")
async def reset(scope: Optional[str] = "session"):
    enforcer: BudgetEnforcer = _state["enforcer"]
    if scope == "all":
        enforcer.reset_all()
    else:
        enforcer.reset_session()
    return {"status": "ok", "reset": scope}
