---
applyTo: '**/test*.py,**/conftest.py,**/pytest_simcore/**/*.py'
---


## Coding Instructions for Python Tests in This Repository

This is a multi-project monorepo with two main groups of projects in the folders [`packages`](../../packages/) and in [`services`](../../services/) . Each project has its own folder with a standard structure (`src/`, `tests/`, etc.). Test fixtures and helpers shared across projects live in [`pytest-simcore`](../../packages/pytest-simcore) , a shared pytest plugin.

### General

- Use `pytest` for all tests.
- Prefer flat, module-level `test_*` functions over class-based test grouping.
- Do not use `class Test...` containers for grouping tests.
- When flattening or adding tests, use descriptive function name prefixes (e.g. `test_ordering_query_params_defaults_*`) to preserve grouping intent.
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
- If the split files share fixtures, move shared fixtures to a `conftest.py`. If the number of files warrants it, group them into a subfolder with its own `conftest.py`.

### Shared test data types

- Dataclasses, TypedDicts, and other types used to annotate fixtures or pass structured data between test files **must not** be imported across test modules via relative or `conftest` imports — pytest's default `prepend` import mode makes this unreliable.
- Instead, place shared test data types in the appropriate `pytest_simcore.helpers.` module (e.g. `webserver_users.py`, `storage_utils.py`). This ensures reliable imports and encourages reuse across projects.
- Only types that are truly local to a single test file may stay in that file.

### Test file naming

- **Test file names must be unique across the entire project test tree**, regardless of which subfolder they live in. Generic names like `test_list.py`, `test_search.py`, or `test_create.py` are forbidden since they can easily collide with unrelated test files elsewhere. Always keep the full original filename as a prefix for the filename, even inside a dedicated subfolder. **Folder names should be a short version of the original test filename, without the `test_` prefix**:
  - ✅ `users_accounts_rest_registration/test_users_accounts_rest_registration_search.py`
  - ❌ `test_users_accounts_rest_registration/test_users_accounts_rest_registration_search.py`
  - ❌ `users_accounts/test_search.py`

## How to Run Tests

See the [`run-python-tests`](../skills/run-python-tests/SKILL.md) skill for the full step-by-step procedure.

---
*Last updated: 2026-04-23*
