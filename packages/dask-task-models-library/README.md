# simcore dask task models library

Contains the [pydantic](https://pydantic-docs.helpmanual.io/)-based models for use in the simcore platform with dask clients,workers. As a reminder pydantic allows creation of python classes that automatically validate their contents based on types. It also provides mechanism to generate json schemas describing the classes internals.

Requirements to be compatible with the library:

- be a pydantic-based model
- be compatible with dask

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
