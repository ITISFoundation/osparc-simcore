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

## memory profiling with memray

Every Python service boot script (`<service>/docker/boot.sh`) can wrap its launcher
with [memray](https://bloomberg.github.io/memray/) to hunt memory leaks. It is opt-in
through per-service environment variables and **only works in the development image**
(`local/<service>:development`, where memray is installed from
`requirements/_tools.txt` at boot). The gate takes precedence over `SC_BOOT_MODE=debug`
(debugpy and memray cannot be combined).

Each service defines its own `<PREFIX>_MEMRAY_*` variables (see the per-service
README section for the exact prefix and port):

| Variable | Default | Description |
| --- | --- | --- |
| `<PREFIX>_MEMRAY_ENABLED` | `False` | Master switch: wraps the launcher with `memray run` |
| `<PREFIX>_MEMRAY_MODE` | `live` | `live` streams allocations over a socket, `file` writes a capture file |
| `<PREFIX>_MEMRAY_PORT` | per service | Port of the live tracking server (bound to `127.0.0.1` *inside* the container) |
| `<PREFIX>_MEMRAY_NATIVE` | `True` | Also track native (C/C++) allocations |
| `<PREFIX>_MEMRAY_OUTPUT_DIR` | `/tmp/memray` | Output dir for `file` mode (bind-mounted to `<service>/.ignore/memray/` on the host in devel mode) |

Default live ports (unique per service): webserver 10248, catalog 10249, director-v2
10250, director 10251, clusters-keeper 10252, autoscaling 10253, storage 10254,
invitations 10255, notifications 10256, api-server 10257, payments 10258,
resource-usage-tracker 10259, agent 10260, datcore-adapter 10261, dask-sidecar 10262,
dynamic-scheduler 10263, dynamic-sidecar 10264. The webserver clones get their own
ports in the main compose (`WB_GC_MEMRAY_PORT` 10265, `WB_AUTH_MEMRAY_PORT` 10266,
`WB_DB_EL_MEMRAY_PORT` 10267).

### Live results (`live` mode)

The service waits on the live socket and **the app only starts once a viewer
attaches** (the healthcheck reports *unhealthy* until then):

```
# 1. set <PREFIX>_MEMRAY_ENABLED=true in .env and redeploy (e.g. make up-devel)
# 2. attach a viewer to the live socket:
CONTAINER=$(docker ps --filter name=<service> --format '{{.ID}}' | head -1)
docker exec -it "$CONTAINER" memray live <PORT>
```

### Capture file (`file` mode)

Set `<PREFIX>_MEMRAY_MODE=file` instead: allocations are written to
`<PREFIX>_MEMRAY_OUTPUT_DIR` (in devel mode the capture lands on the host under
`<service>/.ignore/memray/`). Analyze it **inside the same image** so that native
symbols resolve:

```
docker exec -it "$CONTAINER" memray flamegraph --leaks /tmp/memray/<service>.<ts>.<pid>.bin
```

### Forked launchers (webserver, celery workers, dask)

`memray` cannot combine live tracking with `--follow-fork`, so for the gunicorn- and
celery-based launchers (webserver and the `*_worker` clones, api-server/storage/
notifications in `AS_CELERY_WORKER` mode) and the dask-sidecar:

- `file` mode automatically adds `--follow-fork` and every process (master + each
  forked worker) writes its own capture file, `<service>.<ts>.<pid>.bin`;
- `live` mode only tracks the master process (useful for uvicorn/gunicorn master
  bookkeeping, not for the workers) — prefer `file` mode there.

The celery `threads` pool runs in-process, so `live` mode still captures the task
executions there.

Note: clones that share their parent's environment (e.g. `api-worker` with
`api-server`, `sto-worker*` with `storage`) enable profiling too when the master
switch is turned on. Since live mode blocks until a viewer attaches, every clone
waits for its own viewer — prefer `file` mode, or enable one container at a time.

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
