# simcore pydantic models library

Contains the [pydantic](https://pydantic-docs.helpmanual.io/)-based models for use in the simcore platform. As a reminder pydantic allows creation of python classes that automatically validate their contents based on types. It also provides mechanism to generate json schemas describing the classes internals.

Requirements to be compatible with the library:

- be a pydantic-based model
- not a model for use in a REST API (or at least not directly) only for a specific service (ServiceUpdate model for use in a PATCH REST call on the webserver has nothing to do in the library for example, but a base class for it is ok)

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

1. setup environment
```bash
make devenv
source .venv/bin/activate
cd packages/models-library
make install-dev
```
2. set ``REGISTRY_*`` env vars in ``.env`` (in the repository base folder)
3. download test data, run diagnostics, archive tests-data, and cleanup
```bash
export DEPLOY_NAME=my-deploy
make pull_test_data >$DEPLOY_NAME-registry-diagnostics.log 2>&1
pytest -vv -m diagnostics >>$DEPLOY_NAME-registry-diagnostics.log 2>&1
zip -r $DEPLOY_NAME-registry-test-data.zip tests/data/.downloaded-ignore
rm -r tests/data/.downloaded-ignore
```
4. move all ``$DEPLOY_NAME-*`` files to save place
