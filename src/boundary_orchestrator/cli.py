"""
krypton-boundary-orchestrator CLI entrypoint.

Subcommands (MVP):
- health    -> show a single Krypton health snapshot
- run-once  -> run one scheduler iteration around a dummy job
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from . import krypton_client
from . import scheduler


def cmd_health(args: argparse.Namespace) -> int:
    health = krypton_client.fetch()
    payload: dict[str, Any] = {
        "samples": health.samples,
        "mean": health.mean,
        "variance": health.variance,
        "jitter": health.jitter,
        "decision": health.decision,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def cmd_run_once(args: argparse.Namespace) -> int:
    health, action = scheduler.run_once(scheduler.dummy_job)
    payload: dict[str, Any] = {
        "samples": health.samples,
        "mean": health.mean,
        "variance": health.variance,
        "jitter": health.jitter,
        "decision": health.decision,
        "action": action,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="krypton-boundary-orchestrator",
        description="Python boundary orchestrator using Krypton entropy decisions.",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version info and exit.",
    )

    subparsers = parser.add_subparsers(dest="command")

    # krypton-boundary-orchestrator health
    health_parser = subparsers.add_parser(
        "health",
        help="Fetch a single Krypton health snapshot.",
    )
    health_parser.set_defaults(func=cmd_health)

    # krypton-boundary-orchestrator run-once
    run_once_parser = subparsers.add_parser(
        "run-once",
        help="Run one scheduler iteration around a dummy job.",
    )
    run_once_parser.set_defaults(func=cmd_run_once)

    args = parser.parse_args(argv)

    if args.version and args.command is None:
        print("krypton-boundary-orchestrator v0.1.0")
        return 0

    if hasattr(args, "func"):
        return args.func(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
