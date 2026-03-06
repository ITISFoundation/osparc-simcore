---
applyTo: '**/test*.py,**/conftest.py, **/pytest_simcore/**/*.py'
---

## 🛠️Coding Instructions for Python Tests in This Repository

- Use `pytest` for writing tests.
- `@pytest.fixture(autouse=True)` is not allowed, use explicit fixtures instead.
- Do annotate types all fixtures inputs and outputs with full type annotations.
- Do not add return type annotations in `test_*` functions.
- Be minimalistic with test and reuse as much as possible existing fixtures and helper functions, including those in `packages/pytest-simcore`.

## How to Run Tests

- Make sure you have workspaces .venv activated `source .venv/bin/activate`
- cd to the package or service you want to test i.e. `cd services/web/server`
- Install the package in editable mode using `make install-dev`. This will also install the test dependencies.
- Run you can run tests using `pytest` command or various `make test-*` targets defined in the `Makefile` of each package or service. For example, `make test-unit` to run unit tests or `make test-integration` to run integration tests.
- Troubleshooting:
  - sometimes the previous tests may have left some docker containers running; Go to the workspace directory and call `make down leave` to leave swarm or `docker rm -rf $(docker ps -a -q)` to remove all containers launched with docker-compose and try again.
