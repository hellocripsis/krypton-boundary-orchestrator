"""
Simple scheduler stub that uses Krypton decisions to gate a dummy job.

MVP behavior:
- Call krypton_client.fetch() to get a KryptonHealth snapshot.
- Based on `decision`, choose what to do:
  - Keep     -> run the job immediately.
  - Throttle -> sleep/back off before running.
  - Kill     -> skip the job.
"""

from __future__ import annotations

import time
from typing import Callable

from .config import SchedulerConfig
from .krypton_client import KryptonHealth, Decision, fetch as fetch_krypton


def run_once(
    job: Callable[[], None],
    scheduler_cfg: SchedulerConfig | None = None,
) -> tuple[KryptonHealth, str]:
    """
    Run a single scheduler iteration around a job.

    Returns a tuple of (KryptonHealth, action_taken) where action_taken is one of:
    - "run"
    - "throttled"
    - "skipped"
    """
    if scheduler_cfg is None:
        # Lazy import to avoid circular imports at module import time.
        from .config import _get_default_config  # type: ignore[attr-defined]

        scheduler_cfg = _get_default_config().scheduler

    health = fetch_krypton()
    decision: Decision = health.decision  # type: ignore[assignment]

    if decision == "Kill":
        action = "skipped"
    elif decision == "Throttle":
        time.sleep(scheduler_cfg.throttle_sleep_seconds)
        job()
        action = "throttled"
    else:
        job()
        action = "run"

    return health, action


def dummy_job() -> None:
    """Placeholder job for early testing."""
    print("dummy_job executed")
