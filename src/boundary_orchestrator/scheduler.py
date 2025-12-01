from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Callable, Dict, Tuple

from .config import SchedulerConfig, load_config
from .krypton_client import KryptonHealth, fetch as fetch_krypton


Job = Callable[[], None]


@dataclass
class JobRegistry:
    jobs: Dict[str, Job]

    def get(self, job_id: str) -> Job:
        try:
            return self.jobs[job_id]
        except KeyError as exc:
            raise KeyError(f"unknown job_id {job_id!r}") from exc


def run_once(
    job: Job,
    scheduler_cfg: SchedulerConfig | None = None,
) -> Tuple[KryptonHealth, str]:
    """
    Run a single iteration of the scheduler for a given job.

    Returns (health, action) where action is one of:
      - "run"       -> job executed
      - "throttled" -> job executed, but Krypton suggested throttling
      - "skipped"   -> job skipped due to Kill decision
    """
    if scheduler_cfg is None:
        scheduler_cfg = load_config().scheduler

    health = fetch_krypton()

    if health.decision == "Kill":
        action = "skipped"
        # do not run the job at all
        return health, action

    if health.decision == "Throttle":
        time.sleep(scheduler_cfg.throttle_sleep_seconds)
        job()
        action = "throttled"
    else:
        job()
        action = "run"

    return health, action


def run_registered_once(
    job_id: str,
    registry: JobRegistry,
    scheduler_cfg: SchedulerConfig | None = None,
) -> Tuple[KryptonHealth, str]:
    """
    Look up a job in the registry and run a single iteration with Krypton gating.
    """
    job = registry.get(job_id)
    return run_once(job, scheduler_cfg=scheduler_cfg)


def print_result(health: KryptonHealth, action: str) -> None:
    """
    Utility for CLI: print a JSON summary of the last iteration.
    """
    print(
        json.dumps(
            {
                "samples": health.samples,
                "mean": health.mean,
                "variance": health.variance,
                "jitter": health.jitter,
                "decision": health.decision,
                "action": action,
            },
            indent=2,
            sort_keys=True,
        )
    )
