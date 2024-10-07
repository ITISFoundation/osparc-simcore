# simcore pydantic common library

Contains the common classes, functions and in general utilities for use in the simcore platform.

## Installation

```console
make help
make install-dev
```

## Test

```console
make help
make test-dev
```


## Diagnostics

How run diagnostics on the service metadata published in a docker registry?

1. Setup environment
```bash
make devenv
source .venv/bin/activate

cd packages/common-library
make install-dev
```
2. Set ``REGISTRY_*`` env vars in ``.env`` (in the repository base folder)
3. Download test data, run diagnostics, archive tests-data, and cleanup
```bash
export DEPLOY_NAME=my-deploy

make pull_test_data >$DEPLOY_NAME-registry-diagnostics.log 2>&1
pytest -vv -m diagnostics >>$DEPLOY_NAME-registry-diagnostics.log 2>&1
zip -r $DEPLOY_NAME-registry-test-data.zip tests/data/.downloaded-ignore
rm -r tests/data/.downloaded-ignore
```
4. Move all ``$DEPLOY_NAME-*`` files to an archive
