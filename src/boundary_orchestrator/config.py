"""
Configuration handling for the boundary orchestrator.

Config file (TOML), e.g. `boundary-orchestrator.toml`:

    [krypton]
    mode = "binary"                  # "binary" | "http"
    binary_path = "entropy_health"   # path to the Krypton health binary
    http_url = "http://127.0.0.1:3000/health"  # optional HTTP health endpoint

    [scheduler]
    throttle_sleep_seconds = 0.5
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Any

try:  # Python < 3.11
    import tomli as toml
except ModuleNotFoundError:  # pragma: no cover - Python >= 3.11
    import tomllib as toml  # type: ignore[no-redef]


KryptonMode = Literal["binary", "http"]


@dataclass
class KryptonConfig:
    mode: KryptonMode
    binary_path: str
    http_url: str


@dataclass
class SchedulerConfig:
    throttle_sleep_seconds: float


@dataclass
class OrchestratorConfig:
    krypton: KryptonConfig
    scheduler: SchedulerConfig


def _get_default_config() -> OrchestratorConfig:
    return OrchestratorConfig(
        krypton=KryptonConfig(
            mode="binary",
            binary_path="entropy_health",
            http_url="http://127.0.0.1:3000/health",
        ),
        scheduler=SchedulerConfig(
            throttle_sleep_seconds=0.5,
        ),
    )


def load_config(path: str | Path | None = None) -> OrchestratorConfig:
    """
    Load config from the given TOML file, or fall back to safe defaults.

    If the file does not exist or cannot be parsed, returns a default config.
    """
    if path is None:
        path = "boundary-orchestrator.toml"

    cfg_path = Path(path)

    if not cfg_path.exists():
        return _get_default_config()

    data: dict[str, Any]
    with cfg_path.open("rb") as f:
        data = toml.load(f)

    krypton_raw = data.get("krypton", {}) or {}
    scheduler_raw = data.get("scheduler", {}) or {}

    krypton = KryptonConfig(
        mode=krypton_raw.get("mode", "binary"),
        binary_path=krypton_raw.get("binary_path", "entropy_health"),
        http_url=krypton_raw.get("http_url", "http://127.0.0.1:3000/health"),
    )

    scheduler = SchedulerConfig(
        throttle_sleep_seconds=float(
            scheduler_raw.get("throttle_sleep_seconds", 0.5)
        ),
    )

    return OrchestratorConfig(krypton=krypton, scheduler=scheduler)
