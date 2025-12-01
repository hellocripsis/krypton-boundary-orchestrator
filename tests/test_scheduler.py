from boundary_orchestrator import scheduler
from boundary_orchestrator.config import SchedulerConfig
from boundary_orchestrator.krypton_client import KryptonHealth


def _make_health(decision: str) -> KryptonHealth:
    return KryptonHealth(
        samples=10,
        mean=0.5,
        variance=0.1,
        jitter=0.01,
        decision=decision,  # type: ignore[arg-type]
    )


def test_run_once_keep(monkeypatch):
    calls = []

    def fake_job():
        calls.append("job")

    def fake_fetch():
        return _make_health("Keep")

    monkeypatch.setattr("boundary_orchestrator.scheduler.fetch_krypton", fake_fetch)

    cfg = SchedulerConfig(throttle_sleep_seconds=0.0)
    health, action = scheduler.run_once(fake_job, scheduler_cfg=cfg)

    assert health.decision == "Keep"
    assert action == "run"
    assert calls == ["job"]


def test_run_once_throttle(monkeypatch):
    calls = []

    def fake_job():
        calls.append("job")

    def fake_fetch():
        return _make_health("Throttle")

    monkeypatch.setattr("boundary_orchestrator.scheduler.fetch_krypton", fake_fetch)

    cfg = SchedulerConfig(throttle_sleep_seconds=0.0)
    health, action = scheduler.run_once(fake_job, scheduler_cfg=cfg)

    assert health.decision == "Throttle"
    assert action == "throttled"
    assert calls == ["job"]


def test_run_once_kill(monkeypatch):
    calls = []

    def fake_job():
        calls.append("job")

    def fake_fetch():
        return _make_health("Kill")

    monkeypatch.setattr("boundary_orchestrator.scheduler.fetch_krypton", fake_fetch)

    cfg = SchedulerConfig(throttle_sleep_seconds=0.0)
    health, action = scheduler.run_once(fake_job, scheduler_cfg=cfg)

    assert health.decision == "Kill"
    assert action == "skipped"
    # job must not run
    assert calls == []
