---
name: fastapi-application-configuration
description: 'Use this skill whenever modifying any FastAPI service application.py bootstrap file in this monorepo (for example services/*/src/*/core/application.py). Standardizes lifecycle wiring by migrating legacy startup/shutdown event handlers to LifespanManager, moving core/events.py orchestration into core/application.py, introducing configure_* plugin orchestration, privatizing internal lifespan functions, and updating tests after lifecycle refactors.'
argument-hint: 'Target service path (e.g. services/notifications) and migration type (events->lifespan or events.py->application.py)'
user-invocable: true
---

# FastAPI Application Configuration Guidelines

## Outcome
Apply a consistent FastAPI bootstrap pattern across services:
- lifecycle orchestration lives in `core/application.py`
- no legacy startup/shutdown event wiring remains (`@app.on_event`, `add_event_handler`)
- `configure_*` functions are the public integration surface
- internal lifespan functions are private (`_...`)
- tracing and prometheus use `configure_*` APIs
- tests remain stable after symbol moves

## When To Use
Use this skill when a service:
- is changing `application.py` in a FastAPI-based service bootstrap path (for example `services/*/src/*/core/application.py`)
- is changing lifecycle/plugin orchestration in `application.py` even if no explicit migration was requested
- still uses `@app.on_event("startup"|"shutdown")`
- still uses `app.add_event_handler("startup"|"shutdown", ...)`
- still wires app lifecycle through `core/events.py`
- mixes old init-style setup (`setup_tracing`, `initialize_*`) with new configure APIs
- exposes lifespan helpers that should be private
- has failing tests after lifecycle refactors due to stale monkeypatch targets

## Inputs
- Target service folder (for example: `services/invitations`)
- Migration mode:
	- `legacy-events-to-lifespan-manager`
	- `events-module-to-application`
- Whether the service has client/rpc lifecycle modules that need configure wrappers

## Procedure
1. Inventory lifecycle wiring and build an execution map.
- Read `core/application.py`, `core/events.py` (if present), `main.py`, and service tests.
- Search for: `@app.on_event`, `add_event_handler`, `create_app_lifespan`, `setup_tracing`, `initialize_prometheus_instrumentation`, `initialize_fastapi_app_tracing`, and monkeypatches of moved symbols.
- Write down startup and shutdown ordering before edits. Preserve this order during migration.

2. Replace legacy startup/shutdown handlers with lifespan-managed flows.
- For each startup/shutdown pair, create a single lifespan function that guarantees teardown in `finally`.
- For startup-only behavior, use lifespan that yields immediately after setup.
- For shutdown-only behavior, keep setup as no-op and run cleanup after `yield`.
- If code currently mutates `app.state`, keep that behavior identical.

3. Move lifecycle orchestration into `core/application.py` when needed.
- Create a local `LifespanManager` in `create_app`.
- Add `_configure_plugins(...)` and call it after app state assignment.
- Add banner lifespan (`_banners_lifespan`) in application module.

4. Convert old setup calls to configure APIs.
- Prefer `configure_prometheus_instrumentation(app, app_lifespan)`.
- Prefer `configure_fastapi_app_tracing(app, app_lifespan, tracing_config=...)`.
- Keep existing conditional flags (`*_PROMETHEUS_INSTRUMENTATION_ENABLED`, `tracing_enabled`).

5. Normalize public vs private lifecycle API.
- Keep `configure_*` functions public.
- Rename lifespan implementation functions to private (`_..._lifespan`) when used only through `configure_*`.
- If needed, add missing configure wrappers in client/rpc modules.

6. Remove legacy events module when fully migrated.
- Delete `core/events.py` only after references are gone.
- Ensure `core/application.py` no longer imports `core.events`.

7. Update tests.
- Repoint monkeypatches from old symbols (often in `core.events`) to new `core.application` or module-level `configure_*` symbols.
- For unit tests that should not hit external infra, patch the relevant `configure_*` entry points.

8. Validate behavioral parity and finish.
- Run diagnostics for all touched files.
- Run targeted unit tests for the service, then broader unit suite if practical.
- Fix import ordering and formatting issues (for example with Ruff import rules).
- Confirm there are no remaining startup/shutdown event registrations.
- Confirm startup side effects and shutdown cleanup still happen in the same order.

## Decision Points
- If legacy code uses `add_event_handler` with sync callables: keep callables sync; do not force async conversion.
- If teardown must always run (network clients, background tasks): use `try/finally` around `yield`.
- If the service has no client/rpc lifespan modules: keep refactor limited to `core/application.py` + `core/events.py` removal.
- If lifecycle helpers are imported outside their module: keep them public until callsites are migrated, then privatize.
- If prometheus enablement is already gated before configure call: avoid redundant settings lifespans that only pass `enabled=True`.

## Completion Criteria
- No remaining references to `@app.on_event("startup")` / `@app.on_event("shutdown")`.
- No remaining references to `add_event_handler("startup"|"shutdown", ...)`.
- No remaining references to `core.events.create_app_lifespan`.
- `create_app` uses `LifespanManager` directly.
- Tracing/prometheus use configure APIs.
- Internal lifespan implementation functions are private where applicable.
- Diagnostics are clean on touched files.
- Targeted service tests pass.

## Example Prompts
- `/fastapi-application-configuration services/notifications`
- `/fastapi-application-configuration migrate services/webserver from on_event startup/shutdown to LifespanManager`
- `/fastapi-application-configuration migrate services/invitations to configure_* lifecycle pattern`
- `/fastapi-application-configuration make lifespan internals private and update tests`
