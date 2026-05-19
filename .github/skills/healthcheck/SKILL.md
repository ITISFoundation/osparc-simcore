---
name: healthcheck
description: 'Single-service guide to add a FastAPI health endpoint and bind Docker HEALTHCHECK to it using common_library.docker_healthcheck. Covers HTTP-mode (standard), heartbeat-mode (workers), HealthCheckError wiring, dependency checks, and tests. Use when: implementing health route behavior (200/503), wiring HealthCheckError handler, updating one target service Dockerfile, adding worker-mode healthchecks, and adding focused health tests.'
argument-hint: target_service=<service-name>
---

# Service Healthcheck

## Input

Required input for this skill:

- `target_service`: one service only (for example `payments`, `catalog`, `dynamic-scheduler`, `web/server`)

## Outcome

For the given `target_service`, produce:

1. A health endpoint that returns `200` when healthy, `503` when unhealthy
2. Error handling that maps `HealthCheckError` → `503 PlainTextResponse`
3. A Dockerfile `HEALTHCHECK` bound to that endpoint via `common_library.docker_healthcheck`
4. If the service has worker containers (no HTTP server): heartbeat-mode healthcheck
5. Tests proving healthcheck behavior works as expected

## Use This Skill When

- Implementing healthcheck for one service end-to-end
- Docker daemon health status should follow the service health endpoint
- Adding a worker-mode (Celery/background) container that needs heartbeat-based healthcheck
- Standardizing an existing service to the `HealthCheckError` pattern

---

## Architecture Reference

### Shared Infrastructure

| Component | Location | Role |
|---|---|---|
| `common_library.docker_healthcheck` | `packages/common-library/src/common_library/docker_healthcheck.py` | Docker HEALTHCHECK CMD entry-point. HTTP GET (default) or heartbeat file check (`HEALTHCHECK_MODE=heartbeat`). |
| `servicelib.fastapi.health` | `packages/service-library/src/servicelib/fastapi/health.py` | `HealthCheckError` exception + `health_check_error_handler` → 503 plain-text response. |
| `servicelib.fastapi.http_error` | `packages/service-library/src/servicelib/fastapi/http_error.py` | `set_app_default_http_error_handlers` — auto-registers `HealthCheckError` handler alongside other defaults. |
| `common_library.heartbeat` | `packages/common-library/src/common_library/heartbeat.py` | File-based heartbeat for worker (non-HTTP) processes: `update_heartbeat()` writes timestamp, `is_healthy()` checks recency. |
| `models_library.errors` | `packages/models-library/src/models_library/errors.py` | Shared error message constants: `RABBITMQ_CLIENT_UNHEALTHY_MSG`, `REDIS_CLIENT_UNHEALTHY_MSG`. |

### Two Healthcheck Modes

1. **HTTP mode** (default): `common_library.docker_healthcheck` does HTTP GET to a URL. Returns healthy if status=200.
2. **Heartbeat mode**: Set `HEALTHCHECK_MODE=heartbeat` in environment. Script checks file-based heartbeat instead of HTTP. Used for worker containers with no HTTP server.

### Standard Dockerfile HEALTHCHECK Parameters

```dockerfile
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=20s \
  --start-interval=1s \
  --retries=5 \
  CMD ["python3", "-m", "common_library.docker_healthcheck", "http://localhost:8000/"]
```

Exceptions to `start-period`: `dynamic-sidecar=64s`, `notifications=90s`, `migration=60s`.

### Dependency Check Patterns

Common dependencies to probe in health endpoints:

| Dependency | Check Method | Error Constant |
|---|---|---|
| RabbitMQ | `get_rabbitmq_client(app).healthy` | `RABBITMQ_CLIENT_UNHEALTHY_MSG` |
| Redis | `get_redis_client(app).is_healthy` | `REDIS_CLIENT_UNHEALTHY_MSG` |
| Postgres | `LivenessResult` via `models_library.healthchecks` | custom message |

---

## Procedure

### Step 0: Determine Service Mode

Identify which mode applies to `target_service`:

| Mode | When | Health Source |
|---|---|---|
| **HTTP-mode** (standard) | Service runs an HTTP server | Health endpoint returns `200`/`503` |
| **Worker-mode** (heartbeat) | Service runs as Celery/background worker (no HTTP server) | `common_library.heartbeat.update_heartbeat()` in task loop; `HEALTHCHECK_MODE=heartbeat` env in compose |
| **Both** | Same image serves HTTP + worker (e.g. api-server, storage, notifications) | Dockerfile uses HTTP-mode; compose overrides worker containers with `HEALTHCHECK_MODE=heartbeat` |

### Step 1: Inventory Current Healthcheck Setup

1. Locate REST health route implementation for `target_service` (typically `api/rest/_health.py`).
2. Locate exception handler setup (look for `set_app_default_http_error_handlers` or explicit `app.add_exception_handler`).
3. Locate Dockerfile `HEALTHCHECK CMD` and current target URL.
4. Check if service has worker containers in `services/docker-compose.yml`.
5. Confirm `common_library` is in the service's dependency chain.

### Step 2: Build/Update Health Endpoint (HTTP-mode)

In the target service health route module:

1. Return plain-text success response for healthy state.
2. Raise `HealthCheckError` when critical dependencies are unhealthy.
3. Use dependency injection to get clients for probing.

Reference implementation (`resource-usage-tracker`):

```python
import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG, REDIS_CLIENT_UNHEALTHY_MSG
from servicelib.fastapi.health import HealthCheckError
from servicelib.rabbitmq import RabbitMQClient
from servicelib.redis import RedisClientSDK

router = APIRouter()


@router.get("/", response_class=PlainTextResponse, response_model=None)
async def healthcheck(
    rabbitmq_client: Annotated[RabbitMQClient, Depends(get_rabbitmq_client_from_request)],
    redis_client: Annotated[RedisClientSDK, Depends(get_redis_client_from_request)],
) -> str:
    if not rabbitmq_client.healthy:
        raise HealthCheckError(RABBITMQ_CLIENT_UNHEALTHY_MSG)

    if not redis_client.is_healthy:
        raise HealthCheckError(REDIS_CLIENT_UNHEALTHY_MSG)

    return f"{__name__}@{datetime.datetime.now(datetime.UTC).isoformat()}"
```

### Step 3: Wire Error Handling (`HealthCheckError` → 503)

Two approaches (pick one):

**Option A** — Use `set_app_default_http_error_handlers` (preferred when available):
```python
from servicelib.fastapi.http_error import set_app_default_http_error_handlers

set_app_default_http_error_handlers(app)
# HealthCheckError handler is registered automatically
```

**Option B** — Register explicitly (when service has custom handler setup):
```python
from servicelib.fastapi.health import HealthCheckError, health_check_error_handler

def setup_exception_handlers(app: FastAPI) -> None:
    # MUST come before catch-all Exception handler
    app.add_exception_handler(HealthCheckError, health_check_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(Exception, make_generic_500_handler())
```

**Ordering rule**: `HealthCheckError` handler MUST be registered before any catch-all `Exception` handler.

### Step 4: Worker-Mode Healthcheck (if applicable)

If `target_service` has worker containers that share the same Docker image but don't run an HTTP server:

1. **In the worker's task loop**, call `update_heartbeat()` periodically:
```python
from common_library.heartbeat import update_heartbeat

# Inside task execution or periodic callback
update_heartbeat()
```

2. **In `services/docker-compose.yml`**, add env var to worker service:
```yaml
  <service>-worker:
    image: <same-image-as-http-service>
    environment:
      HEALTHCHECK_MODE: heartbeat
```

The Dockerfile `HEALTHCHECK` CMD stays unchanged — `common_library.docker_healthcheck` reads `HEALTHCHECK_MODE` at runtime and switches to heartbeat file check.

### Step 5: Bind Docker HEALTHCHECK to Shared Script

In `target_service` Dockerfile production stage:

```dockerfile
# https://docs.docker.com/reference/dockerfile/#healthcheck
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=20s \
  --start-interval=1s \
  --retries=5 \
  CMD ["python3", "-m", "common_library.docker_healthcheck", "http://localhost:8000/"]
```

Rules:
- Port and path must match the service's actual health endpoint.
- Most FastAPI services use port `8000` with path `/`.
- Exceptions: `storage` (8080, `/v0/`), `web` (8080, `/v0/health`), `director` (8000, `/v0/`), `dask-sidecar` (8787, `/health`).
- Adjust `start-period` only if the service has known slow startup (Celery broker warmup, large model loading, etc.).

### Step 6: Add Tests

Add or update unit tests to cover:

1. **Healthy path** → endpoint returns `200` with plain-text body.
2. **Unhealthy dependency path** → endpoint returns `503` with error message body.
3. **No 500 leakage** → assert unhealthy state does NOT trigger generic 500 error logging.

Example test shape:
```python
async def test_healthcheck_healthy(client: httpx.AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert "@" in response.text


async def test_healthcheck_unhealthy_rabbitmq(
    client: httpx.AsyncClient,
    mock_unhealthy_rabbitmq: None,
):
    response = await client.get("/")
    assert response.status_code == 503
    assert "RabbitMQ" in response.text
```

### Step 7: Validate End-to-End

1. Run `target_service` health tests: `pytest tests/unit -k health`
2. Confirm unhealthy path returns `503` (not `500`).
3. Confirm Dockerfile uses `common_library.docker_healthcheck` with correct endpoint URL.
4. If worker-mode: verify `HEALTHCHECK_MODE: heartbeat` is set in compose for worker services.

---

## Completion Criteria

Implementation for `target_service` is complete when all are true:

1. Health endpoint returns `200` when healthy.
2. Health endpoint returns `503` when dependency checks fail.
3. `HealthCheckError` is mapped to `503` via handler (explicit or via `set_app_default_http_error_handlers`).
4. Dockerfile `HEALTHCHECK` is bound to `python3 -m common_library.docker_healthcheck`.
5. If worker containers exist: `HEALTHCHECK_MODE=heartbeat` set in compose + `update_heartbeat()` called in task loop.
6. Tests for healthy/unhealthy health endpoint behavior pass.

---

## Common Pitfalls

- Registering `HealthCheckError` handler AFTER a catch-all `Exception` handler — the catch-all swallows it and returns `500` instead of `503`
- Returning JSON body from health endpoint — Docker healthcheck and monitoring tools expect plain-text
- Using `HTTPException(503)` instead of raising `HealthCheckError` — bypasses the standardized handler and may produce different response format
- Changing Dockerfile CMD URL without verifying the actual endpoint path matches
- Forgetting to set `HEALTHCHECK_MODE=heartbeat` in compose for worker services — the Dockerfile HEALTHCHECK will try HTTP GET against a non-existent server
- Using `response_model=str` instead of `response_model=None` on the health route — causes FastAPI to double-serialize the response
- Not calling `update_heartbeat()` frequently enough in worker tasks — heartbeat file becomes stale and container is marked unhealthy (default threshold: 10 seconds)

---

## Intentional Deviations (Do Not "Fix")

These services intentionally deviate from the standard pattern:

| Service | Deviation | Reason |
|---|---|---|
| `dynamic-sidecar` | Returns JSON `ApplicationHealth` body on 503 | `dynamic-scheduler` inspects the JSON body to determine container state |
| `dynamic-sidecar` | `start-period=64s` | Container launch involves pulling/starting user containers |
| `notifications` | `start-period=90s` | Celery broker connection warmup |
| `docker-api-proxy` | Uses `curl --fail-with-body` with basic auth | Non-Python Caddy service; no Python runtime available |
| `migration` | Shell script checking done-file | One-shot job, not a long-running service |
| `datcore-adapter` | Separate `/v0/live` + `/v0/ready` endpoints | Kubernetes-style split liveness/readiness (Pennsieve dependency) |
