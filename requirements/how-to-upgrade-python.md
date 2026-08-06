# How to upgrade the Python version

In principle each service could use a different Python version, but in practice
we keep a single version across the whole repository.

## Where the version is specified

- Service/script `Dockerfile`:
  ```Dockerfile
  ARG PYTHON_VERSION="<X.Y.Z>"
  FROM python:${PYTHON_VERSION}-slim-bookworm AS base
  ```
- `.python-version` (repo root)
- `requirements/PYTHON_VERSION`

These are kept in sync by reusing the `PYTHON_VERSION` variable where possible.
`tests/environment-setup/test_used_python.py` asserts that all of them match.

## Tooling support

- CI job `unit-test-python-linting` (in `.github/workflows/ci-testing-deploy.yml`)
  runs the lint suite against a matrix of the current and next Python versions
  to surface incompatibilities early.
- [pyupgrade](https://github.com/asottile/pyupgrade) is containerized as
  `make pyupgrade` to modernize syntax for the new version.

## Checklist before upgrading

- `pylint` passes on the codebase under the new version.
- All third-party libraries provide wheels/support for the new version.
- All dev tools are compatible.
- See https://pythonspeed.com/articles/switch-python-3.10/ for migration tips.

## See also

- [python-dependencies.md](python-dependencies.md) — overall dependency model and security workflow
- [how-to-unify-versions.md](how-to-unify-versions.md)
- [how-to-prune-requirements.md](how-to-prune-requirements.md)
