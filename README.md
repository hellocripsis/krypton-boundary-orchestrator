# krypton-boundary-orchestrator

[![CI](https://github.com/hellocripsis/krypton-boundary-orchestrator/actions/workflows/ci.yml/badge.svg)](https://github.com/hellocripsis/krypton-boundary-orchestrator/actions/workflows/ci.yml)

Python **boundary orchestrator** that gates jobs using entropy health and `Keep / Throttle / Kill` decisions produced by the Rust project [`krypton-entropy-core`](https://github.com/hellocripsis/krypton-entropy-core). It can talk to Krypton either:

* directly via the `entropy_health` binary, or
* indirectly via the Go HTTP gateway [`gold-dust-go`](https://github.com/hellocripsis/gold-dust-go), which exposes `/health` and `/jobs`.

This repo is **portfolio-safe**: it uses only OS RNG–driven entropy and does not expose any proprietary algorithms.

---

## Architecture

Current baseline:

* **Rust**: `krypton-entropy-core`

  * OS RNG → entropy metrics + `Keep / Throttle / Kill`.
  * Binary: `entropy_health` (JSON output).
* **Go**: `gold-dust-go`

  * HTTP gateway exposing:

    * `GET /health` → Krypton health snapshot.
    * `POST /jobs` → job decision backed by Krypton.
* **Python**: `krypton-boundary-orchestrator`

  * Loads config from `boundary-orchestrator.toml`.
  * Calls Go `/health` or `entropy_health` directly.
  * Uses decisions to **gate jobs** and emit telemetry.

So the flow looks like:

```text
entropy_health (Rust) ──▶ gold-dust-go (Go HTTP /health, /jobs)
                                  ▲
                                  │
                    krypton-boundary-orchestrator (Python CLI)
```

---

## Features

* **Config-driven** via `boundary-orchestrator.toml`:

  * How to reach Krypton (binary vs HTTP).
  * Scheduler behaviour (throttle sleep, iterations, etc.).
* **Krypton client** (`krypton_client.py`):

  * Understands both direct Krypton JSON and Go gateway JSON (`{"krypton": {...}}`).
  * Normalises into a `KryptonHealth` model with:

    * `samples`, `mean`, `variance`, `jitter`, `decision`.
* **Scheduler** (`scheduler.py`):

  * Applies `Keep / Throttle / Kill` to job execution.
  * Supports direct jobs and a job registry.
* **CLI** (`cli.py`):

  * `health` – one-shot Krypton snapshot.
  * `run-once` – single iteration with a dummy job.
  * `run-job` – single iteration for a named job (`dummy`, `gateway`, …).
  * `run-loop` – multiple iterations with aggregated telemetry.
* **Tests + CI**:

  * `pytest` suite around the client and scheduler.
  * GitHub Actions workflow running tests on push.

---

## Quickstart

### 1. Clone and set up Python environment

```bash
cd ~/dev
git clone git@github.com:hellocripsis/krypton-boundary-orchestrator.git
cd krypton-boundary-orchestrator

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Run tests:

```bash
pytest
```

### 2. Start the Go gateway (`gold-dust-go`)

In another terminal, assuming you have:

* `krypton-entropy-core` built, and
* `gold-dust-go` cloned and wired,

you can start the gateway like this:

```bash
cd ~/dev/gold-dust-go
GOLD_DUST_KRYPTON_MODE=binary \
GOLD_DUST_KRYPTON_BIN=/home/cripsislogic/dev/krypton-entropy-core/target/debug/entropy_health \
go run ./cmd/gateway
```

Sanity check:

```bash
curl http://127.0.0.1:8080/health
```

You should see a JSON block with `status`, `message`, and `krypton` fields.

---

## CLI usage

With the Go gateway running and your virtualenv active:

```bash
cd ~/dev/krypton-boundary-orchestrator
source .venv/bin/activate
```

### Health snapshot

```bash
krypton-boundary-orchestrator health
```

Example (shape, not exact numbers):

```json
{
  "samples": 2048,
  "mean": 0.5001,
  "variance": 0.0039,
  "jitter": 0.049,
  "decision": "Keep"
}
```

### Single iteration with dummy job

```bash
krypton-boundary-orchestrator run-once
```

Example:

```text
dummy_job executed
{
  "samples": 2048,
  "mean": 0.5000,
  "variance": 0.0039,
  "jitter": 0.049,
  "decision": "Keep",
  "action": "run"
}
```

### Run a named job from the registry

The CLI exposes a small job registry:

* `dummy` – simple local job.
* `gateway` – posts to the Go `/jobs` endpoint.

```bash
krypton-boundary-orchestrator run-job --job-id dummy
```

```bash
krypton-boundary-orchestrator run-job --job-id gateway
```

`gateway` will:

1. POST to `http://127.0.0.1:8080/jobs` with a payload like:

   ```json
   {
     "job_id": "orchestrated-job",
     "payload": {
       "source": "krypton-boundary-orchestrator"
     }
   }
   ```

2. Print the `/jobs` JSON response.

3. Print a local summary of the Krypton health + action taken.

### Telemetry loop

```bash
krypton-boundary-orchestrator run-loop --job-id dummy --iterations 5
```

Example summary output:

```json
{
  "iterations": 5,
  "decisions": {
    "Keep": 5,
    "Throttle": 0,
    "Kill": 0
  },
  "actions": {
    "run": 5,
    "throttled": 0,
    "skipped": 0
  },
  "last_health": {
    "samples": 2048,
    "mean": 0.4994,
    "variance": 0.0039,
    "jitter": 0.0490,
    "decision": "Keep"
  }
}
```

---

## Development

Run tests:

```bash
cd ~/dev/krypton-boundary-orchestrator
source .venv/bin/activate
pytest
```

Typical workflow when iterating:

1. Update config or scheduler logic.
2. Run `pytest` locally.
3. Use `krypton-boundary-orchestrator health` to confirm wiring to Krypton.
4. Use `run-job --job-id gateway` to exercise the full Rust → Go → Python chain.

---

## What this demonstrates (for reviewers)

This repo is intentionally structured as a **portfolio piece**. It shows that the author:

* Designs and consumes a **Rust entropy/sentry core** from a Python control plane.
* Builds a **config-driven boundary layer** that gates work based on live entropy health and `Keep / Throttle / Kill` decisions.
* Wires a real **Go HTTP gateway** (`gold-dust-go`) into the loop via `/health` and `/jobs`.
* Implements **CLI UX**, job registries, and telemetry loops in Python.
* Maintains **tests + CI** and treats even small services like production software.
