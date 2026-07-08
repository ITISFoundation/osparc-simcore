# services

Each folder contains a service that is part of the platform's main stack. There is a separate repository https://github.com/ITISFoundation/osparc-ops/ with extra stacks for operations (e.g. monitoring, logging, ...).


## Development Workflow

To build images for development

```bash
make build-devel
make up-devel
```

To build images for production

```bash
make build tag-version
make up-version
```

## Deploying Services

To build and tag these images:

```bash
make build tag-version tag-latest
```

To deploy the application in a single-node swarm

```bash
make up-latest
```

---

## Docker Swarm Healthcheck Review

### Shared Infrastructure

| Component                       | Location                                                        | Role                                                                                                           |
| ------------------------------- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `docker_healthcheck.py` | `scripts/docker/docker_healthcheck.py` | Docker HEALTHCHECK CMD entry-point. HTTP GET (default) or heartbeat file check (`HEALTHCHECK_MODE=heartbeat`). |
| `servicelib.fastapi.health`     | `packages/service-library/src/servicelib/fastapi/health.py`     | `HealthCheckError` exception + `health_check_error_handler` → 503 plain-text response.                         |
| `common_library.heartbeat`      | `packages/common-library/src/common_library/heartbeat.py`       | File-based heartbeat for worker (non-HTTP) processes.                                                          |
| `models_library.healthchecks`   | `packages/models-library/src/models_library/healthchecks.py`    | `LivenessResult = IsResponsive \| IsNonResponsive` type alias.                                                 |

### Per-Service Healthcheck Table

| Service                | Healthcheck Source | CMD                                         | interval | timeout | retries | start_period | Health Endpoint            | Deps Checked                      | HealthCheckError Wired                          | Notes                                                                     |
| ---------------------- | ------------------ | ------------------------------------------- | -------- | ------- | ------- | ------------ | -------------------------- | --------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------- |
| agent                  | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/health`                  | RabbitMQ                          | yes                                             | —                                                                         |
| api-server             | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/`                        | RabbitMQ                          | yes                                             | Worker uses `HEALTHCHECK_MODE=heartbeat`                                  |
| autoscaling            | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/`                        | RabbitMQ, Redis                   | yes                                             | —                                                                         |
| catalog                | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/`                        | RabbitMQ                          | yes                                             | —                                                                         |
| clusters-keeper        | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/`                        | RabbitMQ, Redis                   | yes                                             | —                                                                         |
| dask-sidecar           | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/health` (dask dashboard) | —                                 | no                                              | Shared image for scheduler+worker; SIGTERM graceful killer                |
| datcore-adapter        | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/v0/live`                 | —                                 | no                                              | Also has `/v0/ready` (Pennsieve check)                                    |
| director               | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/v0/`                     | —                                 | yes (via `set_app_default_http_error_handlers`) | No backend deps to check (stateless passthrough)                          |
| director-v2            | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/`                        | RabbitMQ, Redis                   | yes                                             | —                                                                         |
| docker-api-proxy       | Dockerfile         | `curl --fail-with-body`                     | 10s      | 5s      | 5       | 20s          | `/version` (Caddy→Docker)  | —                                 | N/A (non-Python)                                | Basic auth required; cannot use servicelib                                |
| dynamic-scheduler      | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/health`                  | Docker-API-Proxy, RabbitMQ, Redis | yes                                             | —                                                                         |
| dynamic-sidecar        | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | **64s**      | `/health`                  | App state, RabbitMQ               | no (returns JSON 503)                           | Intentional: `ApplicationHealth` JSON consumed by dynamic-scheduler       |
| efs-guardian           | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/`                        | RabbitMQ, Redis                   | yes                                             | —                                                                         |
| invitations            | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/`                        | —                                 | no                                              | Stateless service; no deps to check                                       |
| migration              | Dockerfile         | shell script (`test -f $SC_DONE_MARK_FILE`) | 10s      | 5s      | 5       | **60s**      | N/A                        | —                                 | N/A                                             | One-shot job; healthy = migration completed                               |
| notifications          | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | **90s**      | `/`                        | Redis, RabbitMQ, Postgres         | yes                                             | Worker uses `HEALTHCHECK_MODE=heartbeat`; long start_period for Celery    |
| payments               | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/`                        | RabbitMQ                          | yes                                             | Also has `LivenessResult` readiness report                                |
| resource-usage-tracker | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/`                        | RabbitMQ, Redis                   | yes                                             | —                                                                         |
| storage                | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/v0/`                     | Redis                             | yes (via HTTPException)                         | Worker uses `HEALTHCHECK_MODE=heartbeat`; also has `/v0/status` readiness |
| web                    | Dockerfile         | `docker_healthcheck.py`             | 10s      | 5s      | 5       | 20s          | `/v0/health`               | Event-loop latency, plugins       | yes (aiohttp HealthCheck)                       | Liveness + readiness (`/v0/`) split; most complex probe logic             |

### Infrastructure Services (compose-only)

| Service  | Source  | CMD                              | interval | timeout | retries | start_period |
| -------- | ------- | -------------------------------- | -------- | ------- | ------- | ------------ |
| postgres | compose | `pg_isready`                     | 5s       | —       | 5       | —            |
| redis    | compose | `redis-cli ping`                 | 5s       | 30s     | 50      | —            |
| rabbit   | compose | `rabbitmq-diagnostics -q status` | 5s       | 30s     | 5       | 5s           |
| traefik  | compose | `traefik healthcheck --ping`     | 10s      | 5s      | 5       | 10s          |

### Pattern Notes

1. **Standard pattern**: 17/20 Python services use `docker_healthcheck.py` (HTTP GET to health endpoint).
2. **Worker-mode**: Services with Celery workers (`api-server`, `notifications`, `storage`) use `HEALTHCHECK_MODE=heartbeat` env to switch to file-based heartbeat check.
3. **Exception flow**: `HealthCheckError` → 503 plain-text. Registered via `set_app_default_http_error_handlers` or explicitly.
4. **Intentional deviations**:
   - `dynamic-sidecar` (start_period=64s, JSON response) — container launch delays.
   - `notifications` (start_period=90s) — Celery broker connection warmup.
   - `migration` (start_period=60s, shell script) — one-shot job, not a long-running service.
   - `docker-api-proxy` (curl + basic auth) — Caddy proxy with no Python runtime for healthchecks.
