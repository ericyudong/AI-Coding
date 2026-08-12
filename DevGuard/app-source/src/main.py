"""FastAPI runtime that enforces policy-as-code guardrails."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field
from starlette.responses import Response

# Reuse the same engine as CI eval so offline gates match runtime.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from guardrail_engine import decide  # noqa: E402

REQUESTS = Counter("guardrail_requests_total", "Total guardrail decisions")
FALSE_POSITIVE = Counter(
    "guardrail_false_positive_total",
    "Counted when allowlisted traffic is blocked (ops-labeled)",
)
JAILBREAK_BYPASS = Counter(
    "guardrail_jailbreak_bypass_total",
    "Counted when known-attack traffic is allowed (ops-labeled)",
)
BLOCKS = Counter("guardrail_blocks_total", "Blocked or denied requests", ["reason"])

app = FastAPI(title="AI Guardrails", version="0.1.0")

POLICY_PATH = Path(os.getenv("GUARDRAIL_POLICY_PATH", "/etc/guardrails/policy.yaml"))
_LOCAL_FALLBACK = Path(__file__).resolve().parents[1] / "guardrails" / "policy.yaml"


def load_policy() -> dict[str, Any]:
    path = POLICY_PATH if POLICY_PATH.is_file() else _LOCAL_FALLBACK
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class GuardRequest(BaseModel):
    text: str = Field(..., min_length=1)
    tool: str | None = None
    is_output: bool = False
    # Optional labels for SLO metrics (used by canary analysis demos)
    label: str | None = Field(
        default=None, description="false_positive | jailbreak_bypass | None"
    )


class GuardResponse(BaseModel):
    decision: str
    policy_version: str | None
    latency_ms: float


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    load_policy()
    return {"status": "ready"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/guard", response_model=GuardResponse)
def guard(req: GuardRequest) -> GuardResponse:
    started = time.perf_counter()
    try:
        policy = load_policy()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"policy load failed: {exc}") from exc

    decision = decide(policy, text=req.text, tool=req.tool, is_output=req.is_output)
    REQUESTS.inc()

    if req.label == "false_positive" and decision != "allow":
        FALSE_POSITIVE.inc()
    if req.label == "jailbreak_bypass" and decision == "allow":
        JAILBREAK_BYPASS.inc()
    if decision in ("block", "deny", "redact"):
        BLOCKS.labels(reason=decision).inc()

    return GuardResponse(
        decision=decision,
        policy_version=str(policy.get("version")),
        latency_ms=round((time.perf_counter() - started) * 1000, 3),
    )


@app.get("/v1/policy/version")
def policy_version() -> dict[str, str | None]:
    policy = load_policy()
    return {"version": str(policy.get("version"))}
