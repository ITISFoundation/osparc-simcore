---
name: run-python-tests
description: 'Run Python tests and static analysis for any service or package in this monorepo. Use when: running pytest, executing unit tests, running integration tests, test failures, make install-dev, test setup, installing test dependencies, linting with pylint, and type checking with mypy.'
---

# Run Python Tests

## When to Use

- Running tests for any Python project under `services/` or `packages/`
- Setting up a project for the first time before running tests
- Debugging test failures related to missing modules or dependencies

## Setup (first time or after switching projects)

Run these commands before testing this project.

```bash
# 1. Activate the shared workspace venv (create with `make devenv` at repo root if missing)
source .venv/bin/activate

# 2. Navigate to the project
cd services/<service-name>   # e.g. cd services/payments, cd services/web/server
# or
cd packages/<package-name>   # e.g. cd packages/models-library

# 3. Install in editable mode with test dependencies
make install-dev
```

## Running Tests

```bash
# Run all tests:
pytest tests/ -v

# Run a single file:
pytest tests/unit/test_<name>.py -v

# Run a single function:
pytest tests/unit/test_<name>.py::test_function_name -v

# Integration tests (keeps containers alive between runs):
pytest tests/integration -v --keep-docker-up
```

The `--keep-docker-up` flag is a pytest option provided by the `pytest-simcore` plugin. It prevents docker containers from being torn down after the test run, saving startup time on subsequent runs.

> **Command priority**: `pytest` should always be used over `make test*` in this workflow, because `make test*` includes `--pdb` and blocks non-interactive execution on first failure.

### Static analysis (optional)

```bash
make mypy     # type checking
make pylint   # linting
```

## Troubleshooting

If tests fail due to leftover docker state:

```bash
# From the repository root:
make down leave
```

Then re-run from the project directory.

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Skipping `make install-dev` | `ModuleNotFoundError` | Run `make install-dev` in the project directory |
| Running pytest from workspace root | Wrong test discovery or missing conftest | `cd` to the specific project first |
| Venv not activated | `command not found` or wrong Python | `source .venv/bin/activate` (create it first with `make devenv` at repo root if missing) |
| Stale docker containers | Port conflicts, connection errors | `make down leave` from workspace root |

---
*Last updated: 2026-03-24*
