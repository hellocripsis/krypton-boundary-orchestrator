from boundary_orchestrator import krypton_client
from boundary_orchestrator.krypton_client import KryptonHealth


def test_fetch_returns_krypton_health():
    health = krypton_client.fetch()
    assert isinstance(health, KryptonHealth)

    # Basic sanity checks; we don't care whether it came from real Krypton
    # or the stub, only that the fields look reasonable.
    assert isinstance(health.samples, int)
    assert health.samples >= 0

    assert isinstance(health.mean, float)
    assert 0.0 <= health.mean <= 1.0 or health.mean == 0.0

    assert isinstance(health.variance, float)
    assert health.variance >= 0.0

    assert isinstance(health.jitter, float)
    assert health.jitter >= 0.0

    assert health.decision in ("Keep", "Throttle", "Kill")
