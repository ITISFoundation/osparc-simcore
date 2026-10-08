---
applyTo: '**/test*.py,**/conftest.py,**/tests/**/*.py,**/pytest_simcore/**/*.py'
---


# Python test instructions

Projects live in [`packages`](../../packages/) and [`services`](../../services/),
each with its own `src/` and `tests/`. Shared fixtures, helpers, and test-support
types live in [`pytest-simcore`](../../packages/pytest-simcore).

## Test structure

- Use `pytest` with flat, module-level `test_*` functions; no `class Test...`
  containers solely for grouping.
- Name tests after behavior and scenario, e.g.
  `test_ordering_query_params_defaults_to_created_at()`.
- Do not add a return annotation to `test_*` functions. Annotate helpers,
  fixtures, and factories.
- Test externally observable behavior, not private implementation details.

## Parametrization

- Remove repetition only when readability improves; never abstract away the
  scenario under test.
- Use `pytest.mark.parametrize` for cases with the same flow and give them
  stable, descriptive IDs. Keep separate tests when setup, intent, or failure
  diagnosis differ.

## Fixtures

- Reuse existing fixtures from `pytest-simcore` and the project before adding
  new ones.
- Extract repeated, meaningful setup into a named fixture or factory; keep small
  setup inline when a fixture would hide it.
- Put fixtures shared within a project in its nearest `conftest.py`, and ones
  useful across projects in `pytest-simcore`.
- Fixtures must not leak mutable state, files, network resources, database
  records, environment variables, time patches, or monkeypatches into other
  tests.

## `autouse=True` fixtures

- Do not add `autouse=True` fixtures in `conftest.py` or `pytest_simcore`
  plugins.
- Use `autouse=True` only for a fixture defined and used in the same test
  module, with a short comment above it explaining why explicit injection is
  impractical.

## Shared test data types

- Do not import dataclasses, `TypedDict`s, or other test-support types from
  another test module or from `conftest.py`; pytest's import behavior makes
  this fragile.
- Put types shared across modules in a domain-named `pytest_simcore.helpers`
  module (e.g. `webserver_users.py`), and only once there is a real
  multi-module or multi-project reuse case. Otherwise keep them in their module.

## File and directory names

- Test filenames must be unique across the package's test tree; avoid generic
  names such as `test_list.py`.
- When splitting a module, keep the full original prefix in each filename, and
  name the directory after the original filename without `test_`:
  ```text
  users_accounts_rest_registration/
    test_users_accounts_rest_registration_create.py
    test_users_accounts_rest_registration_search.py
  ```
- Split a test module when it exceeds 1,000 lines by behavior or scenario, moving shared
  fixtures to the nearest `conftest.py`. Do not split if it would duplicate
  setup or obscure relationships.

## Running tests

- Follow the [`run-python-tests`](../skills/run-python-tests/SKILL.md) procedure
  and start with the narrowest relevant target; broaden when the change crosses
  package, service, database, serialization, or API boundaries.
- Use `--keep-docker-up` only for local iteration, never for clean-state or
  CI-equivalent validation.
