# krypton-boundary-orchestrator

Python boundary orchestrator that uses the public **krypton-entropy-core** project
as an entropy and sentry source.

## What it does (planned)

- Calls the `entropy_health` binary or an HTTP `/health` endpoint exposed by Krypton.
- Parses the returned metrics and `decision` field (`Keep`, `Throttle`, `Kill`).
- Uses that decision to gate jobs:
  - **Keep** → run job normally.
  - **Throttle** → back off / sleep before running.
  - **Kill** → skip job or deny execution.

## Status

Early skeleton:

- `pyproject.toml` with minimal build metadata.
- `boundary_orchestrator.cli` stub so we can run:

  ```bash
  PYTHONPATH=src python -m boundary_orchestrator.cli --version
