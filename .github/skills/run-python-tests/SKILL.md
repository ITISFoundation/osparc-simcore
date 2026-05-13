---
name: run-python-tests
description: 'Run Python tests and static analysis for any service or package in this monorepo. Use when: running pytest, executing unit tests, running integration tests, test failures, make install-dev, test setup, installing test dependencies, linting with pylint, and type checking with mypy.'
---

# Run Python Tests

## When to Use

- Running tests for any Python project under `services/` or `packages/`
- Setting up a project for the first time before running tests
- Debugging test failures related to missing modules or dependencies

## Procedure

Follow these steps **in order**. Do not skip the install step — each project has its own dependencies that must be installed before tests can run.

### Step 1: Activate the workspace virtual environment

```bash
source .venv/bin/activate
```

All projects in this monorepo share a single workspace-level `.venv`, created once via `make devenv` at the repository root. It must be active before any install or test command.

### Step 2: Change to the project directory

Navigate to the root of the specific service or package you want to test:

```bash
# For a service:
cd services/<service-name>
# e.g. cd services/payments, cd services/web/server

# For a package:
cd packages/<package-name>
# e.g. cd packages/models-library, cd packages/pytest-simcore
```

### Step 3: Install in development mode

```bash
make install-dev
```

This installs the package in editable mode along with all test dependencies into the shared `.venv`. This step is **required** before running tests — without it, imports will fail with `ModuleNotFoundError`.

> **Note**: You only need to re-run `make install-dev` when switching to a different project or after dependency changes. If you already installed for this project in the current session, you can skip this step.

### Step 4: Run tests

```bash
# Run all tests under the project's tests folder:
pytest tests/ -v

# Run a single test file under tests/:
pytest tests/unit/test_<name>.py -v

# Run a single test function under tests/:
pytest tests/unit/test_<name>.py::test_function_name -v
```

> **Warning**: Do **NOT** use `make test*` — these targets normally include `--pdb`, which drops into an interactive debugger on failure and will block execution.

Use `--keep-docker-up` flag when running integration tests to keep docker containers up between sessions.

### Step 4b: Static analysis (optional but recommended)

Before or after running tests, verify the project passes static analysis from the project directory:

```bash
# Type checking with mypy:
make mypy

# Linting with pylint:
make pylint
```

These are fast checks that can catch issues without running the full test suite. Run them after making code changes to confirm correctness.

### Step 5: Troubleshooting

If tests fail due to leftover docker state from previous runs:

```bash
# From the repository root:
make down leave
```

Then retry from Step 2.

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Skipping `make install-dev` | `ModuleNotFoundError` | Run `make install-dev` in the project directory |
| Running pytest from workspace root | Wrong test discovery or missing conftest | `cd` to the specific project first |
| Using `make test-unit` / `make test-integration` | Execution blocks on first test failure (`--pdb`) | Use `pytest tests/ -v` directly |
| Venv not activated | `command not found` or wrong Python | `source .venv/bin/activate` (create it first with `make devenv` at repo root if missing) |
| Stale docker containers | Port conflicts, connection errors | `make down leave` from workspace root |

---
*Last updated: 2026-03-24*
