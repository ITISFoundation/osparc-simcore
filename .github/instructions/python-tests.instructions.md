---
applyTo: '**/test*.py,**/conftest.py,**/tests/**/*.py,**/pytest_simcore/**/*.py'
---


# Python test instructions

Projects live in [`packages`](../../packages/) and [`services`](../../services/),
each with its own `src/` and `tests/`. Shared fixtures, helpers, and test-support
types live in [`pytest-simcore`](../../packages/pytest-simcore).

## Test structure

- Use `pytest` with module-level `test_*` functions. Do not use `class Test...`
  containers solely to group tests.
- Name tests after behavior and scenario, e.g.
  `test_ordering_query_params_defaults_to_created_at()`.
- Do not annotate return types of `test_*` functions or methods. Their parameters
  still require annotations.
- Test externally observable behavior, not private implementation details.

## Parametrization

- Remove repetition only when it improves readability. Keep the scenario under
  test clear.
- Use `pytest.mark.parametrize` for cases with the same flow and give them
  stable, descriptive IDs. Keep separate tests when setup, intent, or failure
  diagnosis differ.

## Fixtures

- Reuse existing fixtures from `pytest-simcore` and the project before adding
  new ones. Before writing a test, search for an existing fixture or helper for
  each collaborator it needs (user, product, project, wallet, service or
  backend client stubs, and so on). Search `pytest-simcore`, every `conftest.py`
  up the test tree, and the fixtures defined in sibling test modules. Do not
  copy fixtures or fakes from an earlier test, including one you wrote
  yourself, without repeating this search.
- When a sibling test module defines a fixture you need, move it to the nearest
  `conftest.py` and use it from both modules. Do not duplicate it.
- Prefer `mock.create_autospec(Client, instance=True)` over hand-written fakes
  such as `SimpleNamespace`, so that calls are checked against the real
  signature. Do not patch private functions of the code under test when its
  collaborators can be replaced through their public API.
- Extract repeated, meaningful setup into a named fixture or factory. Keep small
  setup inline when a fixture would hide it.
- Name a fixture that returns a callable which creates or performs something
  (a callback-style fixture) with a `create_` prefix, e.g.
  `create_running_service_task`, so call sites read as actions. Do not name it
  after the created object alone.
- Put fixtures shared within a project in its nearest `conftest.py`, and ones
  useful across projects in `pytest-simcore`.
- Fixtures must not leak mutable state, files, network resources, database
  records, environment variables, time patches, or monkeypatches into other
  tests.

## `autouse=True` fixtures

- Do not add `autouse=True` fixtures in `conftest.py`.
- In `pytest_simcore` plugins, allow them only when loading the plugin
  explicitly opts a suite into behavior that applies across its tests.
  Document that contract in the plugin's module docstring.
- Otherwise, use `autouse=True` only for a fixture defined and used in the same
  test module. Add a short comment above it explaining why explicit injection
  is impractical.

## Shared test data types

- Do not import dataclasses, `TypedDict`s, or other test-support types from
  another test module or from `conftest.py`. Pytest's import behavior makes
  this fragile.
- Put types shared across modules in a domain-named `pytest_simcore.helpers`
  module, such as `webserver_users.py`, only when multiple modules or projects
  need them. Otherwise, keep them in their module.

## File and directory names

- Test filenames must be unique across the package's test tree. Avoid generic
  names such as `test_list.py`.
- When splitting a module, keep the full original prefix in each filename, and
  name the directory after the original filename without `test_`:

  ```text
  users_accounts_rest_registration/
    test_users_accounts_rest_registration_create.py
    test_users_accounts_rest_registration_search.py
  ```

- Split test modules over 1,000 lines by behavior or scenario. Move shared
  fixtures to the nearest `conftest.py`. Do not split if it would duplicate
  setup or obscure relationships.

## Running tests

- Follow the [`run-python-tests`](../skills/run-python-tests/SKILL.md) procedure
  and start with the narrowest relevant target. Broaden validation when the
  change crosses package, service, database, serialization, or API boundaries.
- Use `--keep-docker-up` only for local iteration, never for clean-state or
  CI-equivalent validation.
