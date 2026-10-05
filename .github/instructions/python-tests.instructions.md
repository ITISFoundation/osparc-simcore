---
applyTo: '**/test*.py,**/conftest.py,**/tests/**/*.py,**/pytest_simcore/**/*.py'
---


# Python test instructions

This is a multi-project monorepo. Projects live primarily in
[`packages`](../../packages/) and [`services`](../../services/). Each project
normally has its own `src/` and `tests/` directories. Shared pytest fixtures,
helpers, and test-support types live in
[`pytest-simcore`](../../packages/pytest-simcore).

Follow `python.instructions.md` as well as these test-specific rules.

## Test structure

- Use `pytest`.
- Prefer flat, module-level `test_*` functions. Do not introduce `class Test...`
  containers solely for grouping.
- Use descriptive test names that state the behavior and scenario, for example:
  `test_ordering_query_params_defaults_to_created_at()`.
- Do not add a return type annotation to `test_*` functions.
- Fully annotate non-test helpers, fixtures, factories, and structured test data
  where that improves clarity or is required by configured static checks.
- Test externally observable behavior. Avoid asserting private implementation
  details unless they are themselves part of a required contract.
- For a bug fix, add a focused regression test when practical.

## Clarity and parametrization

- Prefer a weak-DRY style: remove repetition only when readability improves;
  never abstract away the scenario being tested.
- Use `pytest.mark.parametrize` when the case table makes the input/output
  matrix clearer and each case has the same test flow.
- Keep separate explicit tests when cases have distinct setup, intent, expected
  behavior, or failure diagnosis.
- Give parametrized cases stable, descriptive IDs when a failure would
  otherwise be difficult to identify.

## Fixtures

- Reuse existing fixtures and helpers before adding new ones. Check
  [`pytest-simcore`](../../packages/pytest-simcore) and the local project
  fixtures first.
- Extract repeated meaningful setup into a fixture or factory with a descriptive
  name when doing so improves call-site clarity.
- Keep small setup blocks inline when a fixture would hide important setup or
  add indirection.
- Put fixtures used by multiple test modules in the same project in that
  project's nearest `conftest.py`.
- Put fixtures that are genuinely useful across multiple projects in
  `pytest-simcore`.
- Fixtures must not leak mutable state, filesystem state, network resources,
  database records, environment variables, time patches, or monkeypatches into
  unrelated tests. Ensure cleanup follows the established fixture lifecycle.

## `autouse=True` fixtures

- Do not add `autouse=True` fixtures in `conftest.py` or `pytest_simcore`
  plugins.
- An `autouse=True` fixture is allowed only when it is defined and used in the
  same test module.
- Add a short comment above every permitted `autouse=True` fixture explaining
  why explicit injection is impractical and confirming that its effect is
  restricted to that test module.


## Shared test data types

- Do not import dataclasses, `TypedDict`s, or other test-support types from
  another test module or from `conftest.py`. Pytest's import behavior makes
  these imports fragile.
- Put types shared across test modules in the appropriate
  `pytest_simcore.helpers` module, using a domain-specific filename such as
  `webserver_users.py` or `storage_utils.py`.
- Keep types used by only one test module in that module.
- Do not promote a type to `pytest-simcore` until it has a real multi-module or
  multi-project reuse case.

## File and directory names

- Test filenames must be unique across the entire project test tree, even when
  they are in different subdirectories.
- Do not use generic filenames such as `test_list.py`, `test_search.py`, or
  `test_create.py`.
- Preserve the original full test-name prefix after splitting:
  ```text
  users_accounts_rest_registration/
    test_users_accounts_rest_registration_create.py
    test_users_accounts_rest_registration_delete.py
    test_users_accounts_rest_registration_search.py
  ```
- Directory names should be a short form of the original test filename without
  the `test_` prefix:
  ```text
  users_accounts_rest_registration/
  ```
  Do not use:
  ```text
  test_users_accounts_rest_registration/
  ```

## Test-file size

- Keep test modules cohesive and navigable.
- When a test module approaches or exceeds 1,000 lines, split it by behavior,
  endpoint family, workflow, or scenario if doing so improves navigation and
  ownership.
- Move shared fixtures to the nearest `conftest.py`. When several related test
  files need shared fixtures, create a focused subdirectory with its own
  `conftest.py`.
- Do not split a cohesive test file mechanically if the split would duplicate
  setup, obscure relationships, or make test discovery harder.

## Running tests

- Follow the
  [`run-python-tests`](../skills/run-python-tests/SKILL.md) procedure and use
  the repository-managed Python environment or task runner.
- Run the narrowest relevant test target first. Broaden validation when the
  change crosses package, service, database, serialization, or API boundaries.
- For local Docker-backed iteration, use `--keep-docker-up` only when supported
  and when reusing containers will not retain stale state. Do not rely on it for
  clean-state reproduction or CI-equivalent validation.
- If the relevant tests cannot be run, state which command was not run and why.
