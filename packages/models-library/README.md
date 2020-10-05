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
