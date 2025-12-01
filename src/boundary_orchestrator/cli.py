from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

from .config import load_config
from .krypton_client import fetch as fetch_krypton
from .scheduler import (
    JobRegistry,
    print_result,
    run_once,
    run_registered_once,
)

# Simple version constant for CLI reporting.
VERSION = "0.1.0"


def _print_json(obj: Dict[str, Any]) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


# ---- Jobs used by the CLI -------------------------------------------------


def _dummy_job() -> None:
    print("dummy_job executed")


def _gateway_job() -> None:
    """
    Example "real" job that talks to the Go gateway's /jobs endpoint.

    This is intentionally simple: it assumes the gateway is listening on
    http://127.0.0.1:8080 and that POST /jobs is available.
    """
    import requests  # local import to avoid hard dependency at import time

    url = "http://127.0.0.1:8080/jobs"
    payload = {
        "job_id": "orchestrated-job",
        "payload": {"source": "krypton-boundary-orchestrator"},
    }

    try:
        resp = requests.post(url, json=payload, timeout=1.0)
        resp.raise_for_status()
        data = resp.json()
        print("[gateway-job] /jobs response:")
        _print_json(data)
    except Exception as exc:  # noqa: BLE001
        print(f"[gateway-job] error calling {url!r}: {exc!r}", file=sys.stderr)


def _build_registry() -> JobRegistry:
    """
    Build a small registry of named jobs exposed via the CLI.
    """
    return JobRegistry(
        jobs={
            "dummy": _dummy_job,
            "gateway": _gateway_job,
        }
    )


# ---- Command implementations ----------------------------------------------


def cmd_health(_args: argparse.Namespace) -> int:
    """
    Print a single Krypton health snapshot as JSON.
    """
    health = fetch_krypton()
    _print_json(
        {
            "samples": health.samples,
            "mean": health.mean,
            "variance": health.variance,
            "jitter": health.jitter,
            "decision": health.decision,
        }
    )
    return 0


def cmd_run_once(_args: argparse.Namespace) -> int:
    """
    Run a single iteration of the scheduler with the dummy job.
    """
    cfg = load_config().scheduler
    health, action = run_once(_dummy_job, scheduler_cfg=cfg)
    print_result(health, action)
    return 0


def cmd_run_job(args: argparse.Namespace) -> int:
    """
    Run a single iteration using a job from the registry.

    Example:
      krypton-boundary-orchestrator run-job --job-id gateway
      krypton-boundary-orchestrator run-job --job-id dummy
    """
    registry = _build_registry()
    cfg = load_config().scheduler

    try:
        health, action = run_registered_once(
            args.job_id,
            registry,
            scheduler_cfg=cfg,
        )
    except KeyError as exc:
        print(f"[run-job] {exc}", file=sys.stderr)
        return 1

    print_result(health, action)
    return 0


def cmd_run_loop(args: argparse.Namespace) -> int:
    """
    Run multiple iterations and emit basic telemetry.

    Example:
      krypton-boundary-orchestrator run-loop --job-id gateway --iterations 10
    """
    registry = _build_registry()
    cfg = load_config().scheduler

    try:
        job = registry.get(args.job_id)
    except KeyError as exc:
        print(f"[run-loop] {exc}", file=sys.stderr)
        return 1

    iterations = args.iterations

    decision_counts: Dict[str, int] = {"Keep": 0, "Throttle": 0, "Kill": 0}
    action_counts: Dict[str, int] = {"run": 0, "throttled": 0, "skipped": 0}

    last_health = None

    for _ in range(iterations):
        from .krypton_client import fetch as fetch_k  # local import for clarity

        health = fetch_k()
        last_health = health

        if health.decision == "Kill":
            action = "skipped"
        elif health.decision == "Throttle":
            action = "throttled"
            job()
        else:
            action = "run"
            job()

        decision_counts[health.decision] = decision_counts.get(
            health.decision,
            0,
        ) + 1
        action_counts[action] = action_counts.get(action, 0) + 1

    summary: Dict[str, Any] = {
        "iterations": iterations,
        "decisions": decision_counts,
        "actions": action_counts,
    }

    if last_health is not None:
        summary["last_health"] = {
            "samples": last_health.samples,
            "mean": last_health.mean,
            "variance": last_health.variance,
            "jitter": last_health.jitter,
            "decision": last_health.decision,
        }

    _print_json(summary)
    return 0


# ---- Argument parsing / entrypoint ----------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="krypton-boundary-orchestrator",
        description="Python boundary orchestrator around Krypton entropy decisions.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"krypton-boundary-orchestrator {VERSION}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # health
    p_health = subparsers.add_parser("health", help="Show a single Krypton health snapshot.")
    p_health.set_defaults(func=cmd_health)

    # run-once
    p_run_once = subparsers.add_parser(
        "run-once",
        help="Run a single iteration with the dummy job.",
    )
    p_run_once.set_defaults(func=cmd_run_once)

    # run-job
    p_run_job = subparsers.add_parser(
        "run-job",
        help="Run a single iteration using a job from the registry.",
    )
    p_run_job.add_argument(
        "--job-id",
        required=True,
        help="Job identifier to execute (e.g. 'dummy', 'gateway').",
    )
    p_run_job.set_defaults(func=cmd_run_job)

    # run-loop
    p_run_loop = subparsers.add_parser(
        "run-loop",
        help="Run multiple iterations and emit basic telemetry.",
    )
    p_run_loop.add_argument(
        "--job-id",
        required=True,
        help="Job identifier to execute on Keep/Throttle (e.g. 'gateway').",
    )
    p_run_loop.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of iterations to run (default: 10).",
    )
    p_run_loop.set_defaults(func=cmd_run_loop)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1
    return func(args)


def app() -> None:
    """
    Entry wrapper for console_scripts that might point at `app`.
    """
    sys.exit(main())


if __name__ == "__main__":
    raise SystemExit(main())
