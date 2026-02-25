# simcore service library

Contains the osparc service common code.

## Installation

```console
make # shows help
make install-dev
```

## Test

```console
make # shows help
make test                 # run tests without extras
make "test[aiohttp]"      # run tests for aiohttp only
make "test[fastapi]"      # run tests for fastapi only
make "test[all]"          # run tests with all extras
make test-ci              # run CI tests
make "test-ci[all]"       # run CI tests with all extras
```
