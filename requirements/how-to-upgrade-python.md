# Python version

In principle every service can use a different python version (*) but in practice it is more
suitable to keep the same python version througout the entire repository.


(*) so far only ``director`` service uses a different python version because it was
frozen and marked as deprecated.

## Where is python version specified?

Both python and pip version are specified:

-  repository's *prefered* python version file in ``requirements/PYTHON_VERSION`` (could not version standard `.python-version` because then we cannot work with different versions on the same repo)
-  in the services/scripts ``Dockerfile``:
  ```Dockerfile
    ARG PYTHON_VERSION="3.9.12"
    FROM python:${PYTHON_VERSION}-slim-bookworm as base
  ```
- in the CI ``.github/workflows/ci-testing-deploy.yml``
  ```yaml
  jobs:
  ... :
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        python: ["3.9"]
  ```
  and in ``ci/helpers/ensure_python_pip.bash``



## How are these versions synced?

- Reusing ``PYTHON_VERSION`` variables when possible
- ``tests/environment-setup/test_used_python.py`` checks that all these configurations are in sync



## Tools to assist python upgrade?

- CI ``.github/workflows/ci-testing-deploy.yml`` runs ``unit-test-python-linting`` job that monitor early incompatibilities fo the codebase with next python's version. See
  ```yaml
  unit-test-python-linting:
    timeout-minutes: 18 # if this timeout gets too small, then split the tests
    name: "[unit] python-linting"
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        python: ["3.9", "3.11"]
  ```
- [pyupgrade](https://github.com/asottile/pyupgrade) tool which has been containarized (``scripts/pyupgrade.bash``) and added as a Makefile recipe (``make pyupgrade``)



## When to upgrade python's version?

Some points to consider (draft)

 - codebase ``pylint`` passes
 - all third-party libraries are available for the new python distribution
 - all tools are compatible with new python version
 - ...

 SEE https://pythonspeed.com/articles/switch-python-3.10/
