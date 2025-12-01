"""
Krypton client.

This module talks to the Krypton entropy health source via either:
- the `entropy_health` binary, or
- an HTTP `/health` endpoint.

If anything goes wrong (missing binary, bad JSON, HTTP error), it falls back
to a conservative stub that returns a `Keep` decision, so the orchestrator
remains runnable even before Krypton is wired on this machine.

HTTP mode is tolerant of two shapes:

1) Flat JSON from Rust/Python:

   {
     "samples": ...,
     "mean": ...,
     "variance": ...,
     "jitter": ...,
     "decision": "Keep|Throttle|Kill"
   }

2) Nested JSON from the Go gateway:

   {
     "status": "ok",
     "message": "...",
     "krypton": {
       "samples": ...,
       "mean": ...,
       "variance": ...,
       "jitter": ...,
       "decision": "Keep|Throttle|Kill"
     },
     ...
   }
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Literal, Any

import requests

from .config import OrchestratorConfig, load_config


Decision = Literal["Keep", "Throttle", "Kill"]


@dataclass
class KryptonHealth:
    samples: int
    mean: float
    variance: float
    jitter: float
    decision: Decision


def _stub_health() -> KryptonHealth:
    """Fallback health snapshot used if real Krypton calls fail."""
    return KryptonHealth(
        samples=1024,
        mean=0.5,
        variance=0.25,
        jitter=0.01,
        decision="Keep",
    )


def _from_payload(payload: dict[str, Any]) -> KryptonHealth:
    return KryptonHealth(
        samples=int(payload.get("samples", 0)),
        mean=float(payload.get("mean", 0.0)),
        variance=float(payload.get("variance", 0.0)),
        jitter=float(payload.get("jitter", 0.0)),
        decision=payload.get("decision", "Keep"),  # type: ignore[arg-type]
    )


def _fetch_via_binary(cfg: OrchestratorConfig) -> KryptonHealth:
    """
    Call the entropy_health binary and parse JSON.

    NOTE: We assume the binary prints a single JSON object with:
      { "samples": ..., "mean": ..., "variance": ..., "jitter": ..., "decision": "Keep|Throttle|Kill" }

    If the call fails or output cannot be parsed, this function raises.
    """
    cmd = [cfg.krypton.binary_path]

    proc = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
    )

    stdout = proc.stdout.strip()
    if not stdout:
        raise RuntimeError("entropy_health produced no output")

    try:
        payload = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to decode entropy_health JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("entropy_health did not return a JSON object")

    return _from_payload(payload)


def _fetch_via_http(cfg: OrchestratorConfig) -> KryptonHealth:
    """
    Call an HTTP `/health` endpoint and parse JSON.

    Supported shapes:

    1) Flat JSON:
       { "samples": ..., "mean": ..., "variance": ..., "jitter": ..., "decision": ... }

    2) Nested JSON (Go gateway):
       { "krypton": { "samples": ..., "mean": ..., "variance": ..., "jitter": ..., "decision": ... }, ... }
    """
    resp = requests.get(cfg.krypton.http_url, timeout=1.0)
    resp.raise_for_status()
    payload = resp.json()

    if not isinstance(payload, dict):
        raise RuntimeError("HTTP /health did not return a JSON object")

    # If the Go gateway shape is used, drill into the nested 'krypton' object.
    if "krypton" in payload and isinstance(payload["krypton"], dict):
        inner = payload["krypton"]
        return _from_payload(inner)

    # Otherwise, treat the top-level payload as the health object.
    return _from_payload(payload)


def fetch() -> KryptonHealth:
    """
    Fetch a KryptonHealth snapshot using the configured mode.

    If anything fails, logs a warning to stderr and returns a stub `Keep` snapshot.
    """
    cfg = load_config()

    try:
        if cfg.krypton.mode == "binary":
            return _fetch_via_binary(cfg)
        elif cfg.krypton.mode == "http":
            return _fetch_via_http(cfg)
        else:
            print(
                f"[krypton-client] Unknown mode '{cfg.krypton.mode}', using stub.",
                file=sys.stderr,
            )
            return _stub_health()
    except Exception as exc:  # noqa: BLE001
        print(
            f"[krypton-client] Error talking to Krypton ({exc!r}), using stub.",
            file=sys.stderr,
        )
        return _stub_health()
