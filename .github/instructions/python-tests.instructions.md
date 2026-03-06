---
applyTo: '**/test*.py,**/conftest.py,**/pytest_simcore/**/*.py'
---

## Coding Instructions for Python Tests in This Repository

- Use `pytest` for writing tests.
- `@pytest.fixture(autouse=True)` is banned in `conftest.py` and in `pytest_simcore` plugins. It is allowed only when defined and used within the same test module file, to keep side effects local and traceable.
- Annotate all fixture inputs and outputs with full type hints, including pytest-provided fixtures such as `monkeypatch`, `caplog`, and `tmp_path`.
- Do not add return type annotations to `test_*` functions. Non-test helpers should be fully annotated.
- Prefer reusing existing fixtures and helpers (including those in `packages/pytest-simcore`) over creating new ones.

## How to Run Tests

- Make sure the workspace's venv is activated: `source .venv/bin/activate`
- Change to the package or service you want to test, e.g. `cd services/web/server`
- Install the package in editable mode using `make install-dev` (also installs test dependencies)
- Run tests using `pytest` or `make test-*` targets from the package/service `Makefile` (e.g. `make test-unit`, `make test-integration`)
- Troubleshooting: previous tests may have left docker containers running; from the workspace directory, run `make down leave` to leave the swarm
