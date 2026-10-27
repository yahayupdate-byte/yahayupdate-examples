"""Run a small, local AI-to-AI handoff over a measured integration result."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
import sys
import urllib.error
import urllib.request
from pathlib import Path


OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen3:4b"
CALL_METRICS = []
EVIDENCE_KEYS = (
    "environment", "api_processes", "concurrent_requests", "responses_identical",
    "sqlite_reads", "note", "fixture_products", "fixture_order_items", "stack",
    "response_check",
)

ANALYST_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "evidence_keys": {"type": "array", "items": {"type": "string", "enum": list(EVIDENCE_KEYS)}},
        "next_step": {"type": "string"},
    },
    "required": ["summary", "evidence_keys", "next_step"],
    "additionalProperties": False,
}
REVIEWER_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "revise"]},
        "reason": {"type": "string"},
        "required_measurement": {"type": "string"},
    },
    "required": ["verdict", "reason", "required_measurement"],
    "additionalProperties": False,
}
ANALYST_INSTRUCTIONS = (
    "You are an architecture analyst. Use only the supplied measurement. "
    "100 requests and 1 SQLite read measure different things; they are not contradictory. "
    "Say it is a local integration run, not a production benchmark. "
    "Do not claim exactly-once behavior under failures. "
    "Write concise English. Return the requested JSON object only."
)
REVIEWER_INSTRUCTIONS = (
    "You are a second, independent architecture reviewer. Compare the analyst's "
    "claim with the original evidence. 100 requests and 1 SQLite read are compatible: "
    "one is request count, the other is origin-read count. A statement that a test "
    "does NOT prove production behavior is a valid limitation, not a production claim. "
    "Reject only invented affirmative claims or counts. Do not suggest that exactly-once "
    "behavior can be guaranteed by a benchmark. Name one practical measurement needed "
    "before a production decision, such as p95 latency under representative load. "
    "Write concise English."
)


def chat(system: str, user: str, schema: dict) -> dict:
    request_body = {
        "model": MODEL,
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"temperature": 0, "num_predict": 250},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        raw = response.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ValueError("Model response exceeds limit")
        envelope = json.loads(raw)
    if not envelope.get("done"):
        raise RuntimeError("The local model response was incomplete")
    message = json.loads(envelope["message"]["content"])
    validate_contract(message, schema)
    CALL_METRICS.append({key: envelope.get(key) for key in
                         ("total_duration", "prompt_eval_count", "eval_count")})
    return message


def validate_contract(message: dict, schema: dict) -> None:
    if not isinstance(message, dict) or set(message) != set(schema["required"]):
        raise ValueError("The model did not return the required contract")
    for field, definition in schema["properties"].items():
        value = message[field]
        if definition["type"] == "string":
            if not isinstance(value, str) or not value.strip() or len(value) > 6000:
                raise ValueError(f"Invalid string: {field}")
            if "enum" in definition and value not in definition["enum"]:
                raise ValueError(f"Invalid enum: {field}")
        elif definition["type"] == "array":
            allowed = definition["items"]["enum"]
            if not isinstance(value, list) or not value or len(value) > len(allowed):
                raise ValueError(f"Invalid references: {field}")
            if any(not isinstance(item, str) or item not in allowed for item in value):
                raise ValueError(f"Unknown reference: {field}")


def validate_evidence(evidence: dict) -> None:
    if not isinstance(evidence, dict):
        raise ValueError("Evidence must be a JSON object")
    missing = set(EVIDENCE_KEYS) - set(evidence)
    if missing:
        raise ValueError(f"Missing evidence fields: {sorted(missing)}")
    for key in ("api_processes", "concurrent_requests", "sqlite_reads",
                "fixture_products", "fixture_order_items"):
        if type(evidence[key]) is not int or evidence[key] < 0:
            raise ValueError(f"Invalid measured count: {key}")
    if type(evidence["responses_identical"]) is not bool:
        raise ValueError("Invalid response equality flag")
    for key in ("environment", "note", "stack", "response_check"):
        if not isinstance(evidence[key], str) or not evidence[key].strip():
            raise ValueError(f"Invalid evidence text: {key}")
    if len(json.dumps(evidence).encode()) > 16384:
        raise ValueError("Evidence exceeds the local example input limit")


def handoff(evidence: dict) -> dict:
    validate_evidence(evidence)
    CALL_METRICS.clear()
    analyst = chat(
        ANALYST_INSTRUCTIONS,
        json.dumps(evidence, sort_keys=True),
        ANALYST_SCHEMA,
    )
    if not analyst["evidence_keys"] or any(key not in evidence for key in analyst["evidence_keys"]):
        raise ValueError("The analyst cited an unknown evidence key")
    reviewer = chat(
        REVIEWER_INSTRUCTIONS,
        json.dumps({"evidence": evidence, "analyst_handoff": analyst}, sort_keys=True),
        REVIEWER_SCHEMA,
    )
    if reviewer["verdict"] not in {"approve", "revise"}:
        raise ValueError("The reviewer returned an invalid verdict")
    return {"model": MODEL, "evidence": evidence, "analyst": analyst, "reviewer": reviewer,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "evidence_sha256": hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest(),
            "calls": list(CALL_METRICS), "decision": "human_review_required"}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 agent_handoff.py integration-result.json")
    evidence = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        result = handoff(evidence)
    except (urllib.error.URLError, TimeoutError, ValueError, TypeError, KeyError) as exc:
        raise SystemExit(f"Handoff failed: {exc}") from exc
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
