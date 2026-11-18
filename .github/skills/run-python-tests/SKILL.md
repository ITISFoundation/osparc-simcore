---
name: run-python-tests
description: 'Run Python tests for any service or package in this monorepo. Use when: running pytest, executing unit tests, running integration tests, test failures, make install-dev, test setup, installing test dependencies.'
---

# Run Python Tests

## Step 1: Activate the workspace virtual environment

```bash
source .venv/bin/activate
```

All projects share the single `.venv` at the repository root, created once by
`make devenv`. Every `install-*` and `test-*` target depends on
`_check_venv_active`, so the check fails early rather than installing into the
wrong environment.

## Step 2: Change to the project directory

```bash
cd services/web/server        # a service
cd packages/models-library    # a package
```

## Step 3: Install in development mode

```bash
make install-dev
```

This runs `uv pip sync requirements/dev.txt`, which installs the project and its
in-repo dependencies in editable mode (`--editable .`) together with
`_base.txt`, `_test.txt` and `_tools.txt`. Edits under `src/` take effect without
reinstalling. `install-ci` syncs the same list non-editably
(`simcore-models-library @ .`) and is what CI runs, so use it only to reproduce
a CI environment.

The sync is exact and the `.venv` is shared, so installing project B removes the
dependencies that only project A lists. Install the project under test last, and
expect to reinstall when alternating between projects.

In `packages/service-library`, extras are opt-in, so quote the target:

```bash
make "install-dev[all]"   # also [aiohttp] and [fastapi]
```

## Step 4: Run the tests

Start with the narrowest target that covers the change, then broaden.

```bash
# one file, or one folder: services take target= and test-path=
make test-ci-unit target=tests/unit/test_foo.py
make test-ci-unit test-path=tests/unit/isolated

# packages take the pytest target, or extra parameters
make test-ci-unit TEST_TARGET=tests/test_foo.py
make test-ci-unit pytest-parameters="-k foo"

# packages/service-library keeps its extras in separate targets
make "test-ci[all]"

# services and packages/simcore-sdk also have test-ci-integration
make test-ci-integration

# one test, without make
pytest tests/unit/test_foo.py::test_name -v
```

A service's targets default to `tests/unit`, a package's to all of `tests`.
`packages/simcore-sdk` is the exception: its `test-ci-unit` targets
`tests/unit`, and its integration suite runs only through
`make test-ci-integration`.

Run the whole suite in parallel where the project declares `pytest-xdist`:

```bash
make test-ci-unit pytest-parameters=--numprocesses=auto
pytest tests -n auto
```

The declaring projects are `service-library`, `simcore-sdk`, `web/server`,
`director-v2`, `catalog`, `autoscaling`, `datcore-adapter`, `dynamic-sidecar` and
`storage`. Elsewhere pytest rejects `--numprocesses` as an unrecognized argument.
The fixtures in `pytest_simcore` are xdist-aware: the first worker sets shared
resources up, the controller removes them at session end, and each worker gets
its own database clone and S3 bucket, so parallel runs do not race.

`test-ci-*` is CI's pytest argument set, which also deselects `heavy_load`
markers; a bare `pytest tests/` runs those tests too. `test-dev-*` adds
`--exitfirst`, `-vv` and `--pdb`, so an unattended run stops at the first failure
and waits on a debugger. Requesting workers in dev mode drops `--pdb` and prints
a warning.

## Step 5: Static checks

```bash
make ruff      # linter, also a pre-commit hook
make mypy      # static type checker
make pylint    # no pre-commit hook: CI runs it, so run it by hand
```

Run the ones that cover the change. For a few edited files,
`pylint --rcfile="$(git rev-parse --show-toplevel)/.pylintrc" <files>` is
enough; `.pylintrc` exists only at the repository root, and pylint resolves a
relative `--rcfile` against the current directory. A line-level `# noqa`
satisfies ruff only; pylint needs a matching `# pylint: disable=` directive.

## Docker-backed tests

Services pass `--keep-docker-up` in `PYTEST_BASE_ARGS`, so it is set in dev and
CI mode alike. `packages/service-library`, `packages/simcore-sdk` and
`packages/celery-library` do the same. The flag skips teardown of the Swarm
stack, its network and the docker registry fixture. Workers never remove them;
the xdist controller does at session end. To start from no stack, run `make
down` and then `make leave` from the repository root.

## Troubleshooting

- `ModuleNotFoundError`: a later `make install-dev` in another project synced the
  shared `.venv` to that project's file. Re-run `make install-dev` here.
- `unrecognized arguments: --numprocesses`: the project does not declare
  `pytest-xdist`. Run without workers.
- `command not found`, or the wrong Python: the venv is not active, so
  `source .venv/bin/activate`.
- Port conflicts or connection errors: containers left by an earlier run.
  `make down` and then `make leave` from the repository root.
- A run that stops at the first failure and waits: `test-dev-*` passes `--pdb`.
  Use `test-ci-*`.
- Tests discovered from the wrong rootdir, or `conftest.py` not found: pytest ran
  from the repository root. `cd` to the project first.
