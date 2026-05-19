---
name: healthcheck-entrypoints
description: 'Single-service guide to add a FastAPI health endpoint and bind Docker HEALTHCHECK to it using servicelib.docker_healthcheck. Use when: implementing health route behavior (200/503), wiring HealthCheckError handler, updating one target service Dockerfile, and adding focused health tests.'
argument-hint: target_service=<service-name>
---

# Healthcheck Entrypoints

## Input

Required input for this skill:

- `target_service`: one service only (for example `payments`, `catalog`, `dynamic-scheduler`, `web/server`)

## Outcome

For the given `target_service`, produce:

1. A FastAPI health endpoint that returns `200` when healthy
2. FastAPI error handling that returns `503` when dependencies are unhealthy
3. A Dockerfile `HEALTHCHECK` command bound to that endpoint using existing `servicelib.docker_healthcheck`
4. Tests proving healthcheck behavior works as expected

## Use This Skill When

- You want to implement healthcheck for one FastAPI service end-to-end
- You want Docker daemon health status to follow the service health endpoint
- You need `200` healthy and `503` unhealthy semantics enforced by tests

## Procedure

### Step 0: Establish Service Invariants

For `target_service`, enforce these invariants:

1. Health endpoint returns `200` when dependencies are healthy.
2. Health endpoint returns `503` with a minimal plain-text message when unhealthy.
3. Docker `HEALTHCHECK` returns success only for HTTP `200`.

### Step 1: Inventory Current Healthcheck Setup (Service First)

1. Locate REST health route implementation for `target_service`.
2. Locate exception handler setup used by `target_service`.
3. Locate Dockerfile `HEALTHCHECK CMD` and current target URL.
4. Confirm service runtime includes `servicelib`.

### Step 2: Build/Update FastAPI Health Endpoint

In the target service health route module:

1. Return plain-text success response for healthy state.
2. Raise `HealthCheckError` when critical dependencies are unhealthy.

Reference shape:

```python
@router.get("/", response_class=PlainTextResponse)
async def health_check(app: Annotated[FastAPI, Depends(get_app)]):
    if not get_rabbitmq_client(app).healthy:
        raise HealthCheckError("RabbitMQ cannot be reached")
    return f"{__name__}@{datetime.datetime.now(datetime.UTC).isoformat()}"
```

### Step 3: Wire FastAPI Error Handling (`HealthCheckError` -> 503)

Use shared handler from `servicelib.fastapi.health` and register it before generic catch-all handlers.

```python
app.add_exception_handler(HealthCheckError, health_check_error_handler)
```

Ordering rule: this registration must happen before `Exception`/catch-all handlers.

### Step 4: Bind Docker HEALTHCHECK to Shared Script

In `target_service` Dockerfile, set healthcheck command to:

```dockerfile
CMD ["python3", "-m", "servicelib.docker_healthcheck", "<url>"]
```

Keep the service-specific URL unchanged. The script runtime changes, endpoint target should not.

### Step 5: Add Tests For `target_service`

Add or update unit tests to cover:

1. Healthy path -> endpoint returns `200`.
2. Unhealthy dependency path -> endpoint returns `503`.
3. Optional: assert no generic 500-handler error logs for expected unhealthy state.

### Step 6: Validate End-to-End

Run these checks:

1. Run `target_service` health tests.
2. Confirm unhealthy path returns `503` (not `500`).
3. Confirm Dockerfile uses `servicelib.docker_healthcheck` with correct endpoint URL.
4. Build verification is mandatory: run `make build` (or equivalent service-targeted build).

## Completion Criteria

Implementation for `target_service` is complete when all are true:

1. Health endpoint returns `200` when healthy.
2. Health endpoint returns `503` when dependency checks fail.
3. `HealthCheckError` is mapped to `503` in `target_service`.
4. Dockerfile `HEALTHCHECK` is bound to `python -m servicelib.docker_healthcheck`.
5. Tests for healthy/unhealthy health endpoint behavior pass.
6. Build verification succeeds for the touched service.

## Common Pitfalls

- Wiring `HealthCheckError` but forgetting to register its handler before catch-all `Exception`
- Keeping health route logic but returning `500` from generic exception path
- Changing Dockerfile command but pointing to wrong endpoint URL
- Assuming test output from truncated terminal buffers is final; verify with explicit exit status
- Returning JSON or generic `HTTPException(500)` from health endpoints when plain-text `503` is expected
