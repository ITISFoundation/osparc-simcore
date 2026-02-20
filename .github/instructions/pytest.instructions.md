# AGENTS.md — Running pytest reliably in `osparc-simcore`

Guide for LLM/code agents to run tests exactly like GitHub Actions.

---

## 1) Quick start

```bash
cd /path/to/osparc-simcore

# Setup (once per session)
UV_VENV_CLEAR=1 make devenv
source .venv/bin/activate

# Unit tests
./ci/github/unit-testing/<component>.bash install
./ci/github/unit-testing/<component>.bash test

# Integration tests (must build images first — see §5)
./ci/github/integration-testing/<component>.bash install
./ci/github/integration-testing/<component>.bash test <subdir>
```

If failing, inspect the matching CI script/workflow and reproduce step-by-step — don't guess dependencies.

---

## 2) Prerequisites

- **Python 3.13**
- **`uv`** in PATH (or let `make devenv` install it).
- **Docker** engine running and reachable (`docker` CLI + daemon). Many test suites fail early without it (`docker.errors.DockerException`).
- **Docker Swarm** initialized (`docker swarm init`) — required for integration tests.
- **Linux/WSL** only.

---

## 3) Python / venv setup

- Canonical venv: repo-root `.venv`, created by `make devenv`.
- Service dependencies are installed via `make install-ci` in each service folder (CI scripts do this automatically).
- Always activate `.venv` before running tests.

**Common issues:**

| Problem | Fix |
|---|---|
| `.venv` exists, `uv` refuses to recreate | `UV_VENV_CLEAR=1 make devenv` |
| `.python-version` pin unavailable locally | Use any valid 3.13 interpreter; CI uses `3.13` not a patch version |
| VS Code templates block `make devenv` | `cp .vscode/settings.template.json .vscode/settings.json && cp .vscode/launch.template.json .vscode/launch.json` |
| `uv` self-upgrade warnings | Non-fatal — ignore unless `make devenv` actually exits early |

---

## 4) Unit tests

Run from repo root using CI helper scripts under `ci/github/unit-testing/`:

```bash
./ci/github/unit-testing/<component>.bash install
./ci/github/unit-testing/<component>.bash typecheck   # if available
./ci/github/unit-testing/<component>.bash test
```

<details>
<summary>Available unit-testing scripts</summary>

`agent`, `api-server` (also `openapi-diff`), `api`, `autoscaling`, `aws-library`, `catalog`, `celery-library`, `common-library`, `dask-sidecar`, `dask-task-models-library`, `datcore-adapter`, `director`, `director-v2`, `dynamic-scheduler`, `dynamic-sidecar`, `invitations`, `models-library`, `notifications`, `notifications-library`, `payments`, `postgres-database`, `service-integration`, `service-library` (uses `install_all`/`test_all`), `settings-library`, `simcore-sdk`, `storage`, `webserver` (uses `test_isolated` and `test_with_db <bucket>`)

</details>

**Webserver example** (split test execution):
```bash
./ci/github/unit-testing/webserver.bash install
./ci/github/unit-testing/webserver.bash test_isolated
./ci/github/unit-testing/webserver.bash test_with_db 01  # buckets 01–04
```

**Direct pytest** (for debugging):
```bash
cd services/<service-name>
make test-ci-unit [test-path=...] [pytest-parameters="..."]
```
This runs pytest with `--asyncio-mode=auto`, coverage, `-m "not heavy_load"`, and `--keep-docker-up`.

---

## 5) Integration tests

Integration tests deploy a full Docker Swarm stack and **require locally-built images** tagged `local/<service>:production`.

Available scripts: `ci/github/integration-testing/{director-v2,docker-api-proxy,dynamic-sidecar,simcore-sdk,webserver}.bash`

### Building images

Without images, swarm services are "rejected" (`No such image: local/<service>:production`) and the `docker_stack` fixture times out (~8 min).

```bash
# Build all commonly needed images at once:
make build target="migration catalog director dask-sidecar storage agent dynamic-sidecar"
```

### Director-v2 integration tests (full workflow)

```bash
# 1) Build images
make build target="migration catalog director dask-sidecar storage agent dynamic-sidecar"

# 2) Setup and install
UV_VENV_CLEAR=1 make devenv
source .venv/bin/activate
./ci/github/integration-testing/director-v2.bash install

# 3) Run tests — 01 and 02 are separate subdirectories
./ci/github/integration-testing/director-v2.bash test 01

# Clean up between subdirectories
docker stack rm pytest-simcore pytest-ops 2>/dev/null; sleep 5; docker network prune -f

./ci/github/integration-testing/director-v2.bash test 02
```

> **Note:** `director-v2.bash test` requires a path argument (`01` or `02`). Without it: `$1: unbound variable`.

**Direct pytest alternative:**
```bash
cd services/director-v2
python -m pytest tests/integration/01/ --asyncio-mode=auto -v --keep-docker-up --tb=short
```

---

## 6) Docker cleanup

Integration tests leave Docker Swarm stacks and containers behind, especially after failures. Always clean up before re-running:

```bash
# Remove test stacks
docker stack rm pytest-simcore pytest-ops 2>/dev/null
sleep 5
docker network prune -f

# Remove leftover containers
docker ps -aq --filter name=pytest | xargs -r docker rm -f
```

---

## 7) Known issues and tips

### Environment

- **Host port conflicts** — test docker-compose files may bind fixed host ports (e.g. `15672`, `18080`, `18081`). If already in use, docker compose fails. Fix: use ephemeral ports (container-port only, no host binding).

### Performance

- **`--keep-docker-up`** keeps the Swarm stack running between tests. First test takes ~8 min (stack startup); subsequent tests ~45–60s.
- **xdist parallelism** can be flaky locally. CI uses `--numprocesses=auto --ignore-glob=**/with_dbs/**` then runs `with_dbs` serially. Retry with `--numprocesses=0` to diagnose crashes.
