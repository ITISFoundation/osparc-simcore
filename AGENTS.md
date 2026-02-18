# AGENTS.md — Running pytest reliably in `osparc-simcore`

This guide is for LLM/code agents that need to run tests exactly like GitHub Actions.

## 1) CI truth: what works in GitHub Actions

CI unit/integration jobs use these building blocks:

1. `actions/setup-python` with Python `3.13` (minor version, not a pinned patch).
2. `astral-sh/setup-uv`.
3. `make devenv` from repo root.
4. `source .venv/bin/activate`.
5. Run one of the scripts under `ci/github/unit-testing/*.bash` or `ci/github/integration-testing/*.bash`.

When reproducing locally, prefer running the same scripts instead of inventing custom pytest commands.

---

## 2) Prerequisites (local/non-GHA)

- `uv` available in PATH (or let `make devenv` install/upgrade it).
- A working Docker engine/daemon (`docker` CLI + running daemon).
- For tests that spin containers via fixtures (`pytest-simcore`), Docker must be reachable from the shell running pytest.
- Linux/macOS/WSL only.

Some tests also rely on docker-compose-compatible behavior via `docker compose`.

---

## 3) Python/.venv model in this repository

- The canonical venv location is repo-root: `.venv`.
- Root `make devenv` creates `.venv` and installs `requirements/devenv.txt`.
- Service/package-specific dependencies are then synced by running `make install-ci` in each service/package folder (typically via CI helper scripts).
- Always activate `.venv` before invoking service `make` test targets.

Recommended local bootstrap:

```bash
make devenv
source .venv/bin/activate
```

If `make devenv` fails, read caveats below before changing workflow commands.

---

## 4) Canonical commands for each microservice/package (unit tests)

From repo root, run the CI helper script for the component.

General pattern:

```bash
./ci/github/unit-testing/<component>.bash install
./ci/github/unit-testing/<component>.bash typecheck   # if defined
./ci/github/unit-testing/<component>.bash test        # or component-specific test fn
```

Available unit-testing drivers:

- `agent.bash`
- `api-server.bash` (also has `openapi-diff`)
- `api.bash`
- `autoscaling.bash`
- `aws-library.bash`
- `catalog.bash`
- `celery-library.bash`
- `common-library.bash`
- `dask-sidecar.bash`
- `dask-task-models-library.bash`
- `datcore-adapter.bash`
- `director.bash`
- `director-v2.bash`
- `dynamic-scheduler.bash`
- `dynamic-sidecar.bash`
- `invitations.bash`
- `models-library.bash`
- `notifications.bash`
- `notifications-library.bash`
- `payments.bash`
- `postgres-database.bash`
- `service-integration.bash`
- `service-library.bash` (uses `install_all`/`test_all` instead of install/test)
- `settings-library.bash`
- `simcore-sdk.bash`
- `storage.bash`
- `webserver.bash` (uses `test_isolated` and `test_with_db <bucket>`)

Examples:

```bash
# director-v2 unit tests (CI-equivalent)
./ci/github/unit-testing/director-v2.bash install
./ci/github/unit-testing/director-v2.bash typecheck
./ci/github/unit-testing/director-v2.bash test

# webserver split test execution
./ci/github/unit-testing/webserver.bash install
./ci/github/unit-testing/webserver.bash test_isolated
./ci/github/unit-testing/webserver.bash test_with_db 01
./ci/github/unit-testing/webserver.bash test_with_db 02
./ci/github/unit-testing/webserver.bash test_with_db 03
./ci/github/unit-testing/webserver.bash test_with_db 04
```

---

## 5) Integration/system pytest entrypoints

Integration scripts:

- `ci/github/integration-testing/director-v2.bash`
- `ci/github/integration-testing/docker-api-proxy.bash`
- `ci/github/integration-testing/dynamic-sidecar.bash`
- `ci/github/integration-testing/simcore-sdk.bash`
- `ci/github/integration-testing/webserver.bash`

System scripts:

- `ci/github/system-testing/environment-setup.bash`
- `ci/github/system-testing/swarm-deploy.bash`
- `ci/github/system-testing/public-api.bash`
- `ci/github/system-testing/e2e-playwright.bash`

These are also `install`/`test`-style bash entrypoints.

---

## 6) Direct pytest invocation details (if you must debug)

Service `make test-ci-unit` comes from `scripts/common-service.Makefile` and runs pytest with:

- `--asyncio-mode=auto`
- coverage enabled
- junit xml output
- marker filter `-m "not heavy_load"`
- `--keep-docker-up`
- optional `test-path=...` and `pytest-parameters=...`

For most debugging, prefer:

```bash
cd services/<service-name>
make test-ci-unit [test-path=...] [pytest-parameters="..."]
```

with `.venv` activated.

---

## 7) Caveats discovered during trial run (important)

1. **Pinned `.python-version` mismatch can break `make devenv`.**
   - In this environment, `.python-version` requested `3.13.9`, but that patch version was unavailable in both `pyenv` and `uv` downloads.
   - CI works because it asks for `3.13` via `actions/setup-python`, not an unavailable local patch pin.
   - If this happens locally, use a valid 3.13 interpreter and ensure `uv` can resolve it.

2. **Docker availability is mandatory for many pytest suites.**
   - Without a working Docker daemon/CLI, director-v2 unit tests fail very early in fixtures/plugins (`pytest-simcore` docker helpers).
   - Errors typically appear as `docker.errors.DockerException` / cannot connect to Docker socket.

3. **director-v2 parallel run can be flaky in constrained local environments.**
   - CI command uses `--numprocesses=auto --ignore-glob=**/with_dbs/**` then runs `with_dbs` serially.
   - In this trial, xdist worker crashes occurred around dask/distributed cleanup; retry with lower parallelism for diagnosis.

4. **Local VS Code settings templates can block `make devenv`.**
   - `make devenv` fails if `.vscode/settings.template.json` or `.vscode/launch.template.json` are newer than their `.json` counterparts.
   - Fix by copying templates into place before rerunning: `cp .vscode/settings.template.json .vscode/settings.json` and `cp .vscode/launch.template.json .vscode/launch.json`.

5. **Existing `.venv` can cause `make devenv` to stop.**
   - If `.venv` exists, `uv` may prompt and then fail in non-interactive runs.
   - Use `UV_VENV_CLEAR=1 make devenv` to recreate the venv non-interactively.
   - Prefer exporting `UV_VENV_CLEAR=1` for the whole session so nested CI scripts that call `make devenv` stay non-interactive.

6. **`uv` self-upgrade warnings are non-fatal.**
   - When `uv` is installed via a system package manager, `make devenv` logs a self-upgrade error but continues.
   - Ignore this unless `make devenv` exits early for another reason.

7. **director-v2 has a flaky test under xdist.**
   - `tests/unit/test_api_route_dynamic_scheduler.py::test_409_response[DELETE-docker-resources-_task_cleanup_service_docker_resources]` can fail under `--numprocesses=auto` (returns 400 instead of 202).
   - Re-run the test serially to confirm: `make test-ci-unit test-path=tests/unit/test_api_route_dynamic_scheduler.py::test_409_response[DELETE-docker-resources-_task_cleanup_service_docker_resources] pytest-parameters="--numprocesses=0"`.

---

## 8) Minimal reliable workflow for agents

From repo root:

```bash
# 1) setup venv exactly as repo expects (non-interactive)
UV_VENV_CLEAR=1 make devenv
source .venv/bin/activate

# 2) run target component's CI wrapper
./ci/github/unit-testing/<component>.bash install
./ci/github/unit-testing/<component>.bash test
```

If you need the full director-v2 sequence including typecheck:

```bash
UV_VENV_CLEAR=1 make devenv
source .venv/bin/activate
./ci/github/unit-testing/director-v2.bash install
./ci/github/unit-testing/director-v2.bash typecheck
./ci/github/unit-testing/director-v2.bash test
```

If failing, do not guess dependencies first; inspect matching CI script/workflow and reproduce it step-by-step.

---

## 9) Recent learnings (webserver with_dbs)

1. **Host port conflicts can break `test_with_db`.**
   - `services/web/server/tests/unit/with_dbs/docker-compose-devel.yml` originally bound fixed host ports for RabbitMQ management, Adminer, and Redis Commander.
   - On this machine, host ports `15672`, `18080`, and `18081` were already in use, causing docker compose failures.
   - Fix by using ephemeral host ports (e.g., `15672`, `8080`, `8081` instead of `15672:15672`, `18080:8080`, `18081:8081`).

2. **`test_with_db 01` succeeded after port changes.**
   - Command: `./ci/github/unit-testing/webserver.bash test_with_db 01` (with `.venv` activated).
   - Result: 343 passed, 2 xpassed, 1 xfailed, 1 skipped.

3. **Quick cleanup of pytest docker containers.**
   - Command: `docker ps -aq --filter name=pytest | xargs -r docker rm -f`
