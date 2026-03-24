---
applyTo: '**/test*.py,**/conftest.py,**/pytest_simcore/**/*.py'
---


## Coding Instructions for Python Tests in This Repository

This is a multi-project monorepo with two main groups of projects in the folders [`packages`](../../packages/) and in [`services`](../../services/) . Each project has its own folder with a standard structure (`src/`, `tests/`, etc.). Test fixtures and helpers shared across projects live in [`pytest-simcore`](../../packages/pytest-simcore) , a shared pytest plugin.

### General

- Use `pytest` for all tests.
- Do not add return type annotations to `test_*` functions. All non-test helpers must be fully annotated.

### Fixtures

- Reuse existing fixtures and helpers before creating new ones. Check `packages/pytest-simcore` first.
- If a fixture is used across multiple files within the same project, move it to the local `conftest.py`.
- If a fixture is useful across multiple projects, move it to `pytest-simcore` instead.

#### `autouse=True` fixtures

- **Banned** in `conftest.py` and in `pytest_simcore` plugins.
- **Allowed only** when the fixture is defined and used within the same test module. Add a comment above the fixture explaining why `autouse` is necessary and confirming it is scoped to that module to avoid unintended side effects.

### File size

- If a test file exceeds 1000 lines, split it into multiple files using descriptive name suffixes (e.g. `test_users_accounts_rest_registration.py` → `test_users_accounts_rest_registration_create.py`, `test_users_accounts_rest_registration_delete.py`, etc.).
- If the split files share fixtures, move shared fixtures to a `conftest.py`. If the number of files warrants it, group them into a subfolder with its own `conftest.py` (e.g. `test_users_accounts_rest_registration/test_*.py` + `test_users_accounts_rest_registration/conftest.py`).
```

## How to Run Tests

See the [`run-python-tests`](../skills/run-python-tests/SKILL.md) skill for the full step-by-step procedure.

---
*Last updated: 2026-03-23*
