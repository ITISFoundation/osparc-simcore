---
name: fastapi-application-configuration
description: 'Use this skill whenever modifying any FastAPI service application.py bootstrap file in this monorepo (for example services/*/src/*/core/application.py). Standardizes lifecycle wiring by migrating legacy startup/shutdown event handlers to LifespanManager, moving core/events.py orchestration into core/application.py, introducing configure_* plugin orchestration, using servicelib.fastapi.lifespan_utils.configure_app_lifespan for ordered app banners/logging lifecycle, privatizing internal lifespan functions, and updating tests after lifecycle refactors.'
argument-hint: 'Target service path (e.g. services/notifications) and migration type (events->lifespan or events.py->application.py)'
user-invocable: true
---

# FastAPI Application Configuration Guidelines

## Outcome
Apply a consistent FastAPI bootstrap pattern across services:
- lifecycle orchestration lives in `core/application.py`
- no legacy startup/shutdown event wiring remains (`@app.on_event`, `add_event_handler`)
- app lifecycle is wrapped with `configure_app_lifespan(...)` from `servicelib.fastapi.lifespan_utils`
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
- For client/rpc integrations, include resource creation/connection checks in the same `try/finally` block as `yield` so cleanup runs even if startup fails before `yield`.
- Do not place setup statements before the `try`: the `try/finally` must wrap initialization and `yield` together.
- Initialize app state slots to `None` before entering setup so partially initialized startup paths can be safely cleaned up.

2.1 Prefer the shared app lifecycle wrapper for service application bootstrap.
- In `create_app`, use `with configure_app_lifespan(...) as app_lifespan:`.
- Pass `logging_lifespan` (if provided by caller), `starting_banner`, `started_banner`, and `shutdown_complete_banner`.
- Create `FastAPI(..., lifespan=app_lifespan)` inside the `with` block.
- Register plugins via `_configure_plugins(...)` inside the `with` block.
- Do not keep local `_banners_lifespan` in service `application.py` once migrated.

3. Move lifecycle orchestration into `core/application.py` when needed.
- If using `configure_app_lifespan`, do not instantiate `LifespanManager` directly in `create_app`.
- Add `_configure_plugins(...)` and call it after app state assignment.
- Keep `_configure_plugins(...)` focused on plugin wiring (do not add logging/banner lifespans there).
- If a module still exposes only a lifespan function, add a public `configure_*` wrapper for it and call that wrapper from `_configure_plugins(...)` instead of registering the lifespan directly.

4. Convert old setup calls to configure APIs.
- Prefer `configure_prometheus_instrumentation(app, app_lifespan)`.
- Prefer `configure_fastapi_app_tracing(app, app_lifespan, tracing_config=...)`.
- Keep existing conditional flags (`*_PROMETHEUS_INSTRUMENTATION_ENABLED`, `tracing_enabled`).

5. Normalize public vs private lifecycle API.
- Keep `configure_*` functions public.
- Rename lifespan implementation functions to private (`_..._lifespan`) when used only through `configure_*`.
- If needed, add missing configure wrappers in client/rpc modules.
- For lifecycle publishers that only map values from lifespan state to `app.state`, use the generic `create_publisher_lifespan(...)` helper from `lifespan_utils.py` instead of module-local duplicated publisher lifespans.
- For integrations backed by optional settings (`... | None`) or disabled-mode flags, guard calls in `_configure_plugins(...)` and invoke `configure_*` only when enabled; avoid registering plugins that only log a "disabled by settings" warning.
- For client/rpc `configure_*` modules, ensure lifespan functions are startup-failure safe:
	- Initialize state slots to `None` before setup.
	- Wrap setup + connectivity checks + `yield` in one `try/finally` (not split across separate blocks).
	- In `finally`, close/shutdown clients when present.
	- Guard cleanup with truthy checks so cleanup itself does not raise when initialization failed early.

6. Update service metadata banners to match the shared lifecycle wrapper.
- In service `_meta.py`, keep service-specific `APP_STARTED_BANNER_MSG` (ascii art, if present).
- Add `APP_STARTING_BANNER_MSG = info.get_starting_banner()` when using `PackageInfo`-based metadata.
- Keep `APP_FINISHED_BANNER_MSG = info.get_finished_banner()` and pass it as `shutdown_complete_banner`.
- In services with mode-dependent started banners (for example worker vs server), compute the selected `started_banner` in `create_app` before calling `configure_app_lifespan(...)`.

7. Remove legacy events module when fully migrated.
- Delete `core/events.py` only after references are gone.
- Ensure `core/application.py` no longer imports `core.events`.

8. Update tests.
- Repoint monkeypatches from old symbols (often in `core.events`) to new `core.application` or module-level `configure_*` symbols.
- For unit tests that should not hit external infra, patch the relevant `configure_*` entry points.

9. Validate behavioral parity and finish.
- Run diagnostics for all touched files.
- Run targeted unit tests for the service, then broader unit suite if practical.
- Fix import ordering and formatting issues (for example with Ruff import rules).
- Confirm there are no remaining startup/shutdown event registrations.
- Confirm startup side effects and shutdown cleanup still happen in the same order.
- Explicitly verify that exceptions during startup of client/rpc lifespans still trigger resource cleanup (no leaked partially initialized clients).
- Add/update focused tests that force an exception during initialization-before-`yield` and assert cleanup still runs.

## Decision Points
- If legacy code uses `add_event_handler` with sync callables: keep callables sync; do not force async conversion.
- If teardown must always run (network clients, background tasks): use `try/finally` around `yield`.
- If setup itself can fail after allocating resources (for example client create + ping retry), put setup inside the same `try/finally` that surrounds `yield`.
- If setup can fail before `yield`, treat this as a required failure mode: the lifespan must still execute cleanup from `finally`.
- If the service has no client/rpc lifespan modules: keep refactor limited to `core/application.py` + `core/events.py` removal.
- If lifecycle helpers are imported outside their module: keep them public until callsites are migrated, then privatize.
- If prometheus enablement is already gated before configure call: avoid redundant settings lifespans that only pass `enabled=True`.

## Completion Criteria
- No remaining references to `@app.on_event("startup")` / `@app.on_event("shutdown")`.
- No remaining references to `add_event_handler("startup"|"shutdown", ...)`.
- No remaining references to `core.events.create_app_lifespan`.
- `create_app` uses `configure_app_lifespan(...)` for app bootstrap lifecycle orchestration.
- Tracing/prometheus use configure APIs.
- Internal lifespan implementation functions are private where applicable.
- `_configure_plugins(...)` only composes `configure_*` entry points, not raw lifespan callables.
- `application.py` does not define service-local banner lifespan helpers when using `configure_app_lifespan(...)`.
- service `_meta.py` exposes `APP_STARTING_BANNER_MSG`, `APP_STARTED_BANNER_MSG`, and `APP_FINISHED_BANNER_MSG` (or equivalent mode-aware started banner selection in `create_app`).
- Optional/disabled integrations are conditionally configured in `_configure_plugins(...)` (no unconditional configure call when settings are `None` or feature mode is off).
- Client/rpc lifespans are startup-failure safe: resources allocated before `yield` are closed in `finally` when startup raises.
- Lifespan `try/finally` wraps initialization and `yield` together; no resource-allocating setup statements are outside that block.
- There is test coverage for initialization-phase failures (before `yield`) validating cleanup behavior.
- Diagnostics are clean on touched files.
- Targeted service tests pass.

## Example Prompts
- `/fastapi-application-configuration services/notifications`
- `/fastapi-application-configuration migrate services/webserver from on_event startup/shutdown to LifespanManager`
- `/fastapi-application-configuration migrate services/invitations to configure_* lifecycle pattern`
- `/fastapi-application-configuration make lifespan internals private and update tests`
