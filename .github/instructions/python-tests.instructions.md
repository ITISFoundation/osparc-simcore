---
applyTo: '**/test*.py,**/conftest.py,**/pytest_simcore/**/*.py'
---

## Coding Instructions for Python Tests in This Repository

- Use `pytest` for writing tests.
- Usage of `@pytest.fixture(autouse=True)`
  - usage is banned in `conftest.py` and in `pytest_simcore` plugins.
  - usage is allowed ONLY when defined and used within the same test module file, to keep side effects local and traceable.
    - Add a comment above the fixture definition explaining why autouse is necessary and how it is scoped to avoid unintended side effects.
- When copy pasting a fixture from another test, prefer moving it to conftest.py or even pytest-simcore if that already exist for another package/service
- Do not add return type annotations to `test_*` functions. Non-test helpers should be fully annotated.
- Prefer reusing existing fixtures and helpers (including those in `packages/pytest-simcore`) over creating new ones.

## How to Run Tests

- Make sure the workspace's venv is activated: `source .venv/bin/activate`
- Change to the package or service you want to test, e.g. `cd services/web/server`
- Install the package in editable mode using `make install-dev` (also installs test dependencies)
- Run tests using `pytest` or `make test-*` targets from the package/service `Makefile` (e.g. `make test-unit`, `make test-integration`)
- Troubleshooting: previous tests may have left docker containers running; from the workspace directory, run `make down leave` to leave the swarm
