# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any, NamedTuple

import jsonref
import pytest
import yaml

try:
    from aiohttp import web

    has_aiohttp = True
except ImportError:
    has_aiohttp = False


class Entrypoint(NamedTuple):
    name: str
    method: str
    path: str


@pytest.fixture(scope="session")
def openapi_specs_path() -> Path:
    # NOTE: cannot be defined as a session scope because it is designed to be overriden
    pytest.fail(reason="Must be overriden in caller test suite")


def _load(file: Path, base_uri: str = "") -> dict:
    match file.suffix:
        case ".yaml" | ".yml":
            loaded = yaml.safe_load(file.read_text())
        case "json":
            loaded = json.loads(file.read_text())
        case _:
            msg = f"Expect yaml or json, got {file.suffix}"
            raise ValueError(msg)

    # SEE https://jsonref.readthedocs.io/en/latest/#lazy-load-and-load-on-repr
    data: dict = jsonref.replace_refs(  # type: ignore
        loaded,
        base_uri=base_uri,
        lazy_load=True,  # this data will be iterated
        merge_props=False,
    )
    return data


@pytest.fixture(scope="session")
def openapi_specs(openapi_specs_path: Path) -> dict[str, Any]:
    assert openapi_specs_path.is_file()
    openapi: dict[str, Any] = _load(
        openapi_specs_path, base_uri=openapi_specs_path.as_uri()
    )
    return deepcopy(openapi)


@pytest.fixture(scope="session")
def openapi_specs_entrypoints(
    openapi_specs: dict,
) -> set[Entrypoint]:
    entrypoints: set[Entrypoint] = set()

    # openapi-specifications, i.e. "contract"
    for path, path_obj in openapi_specs["paths"].items():
        for operation, operation_obj in path_obj.items():
            entrypoints.add(
                Entrypoint(
                    method=operation.upper(),
                    path=path,
                    name=operation_obj["operationId"],
                )
            )
    return entrypoints


if has_aiohttp:

    @pytest.fixture
    def create_aiohttp_app_rest_entrypoints() -> Callable[
        [web.Application], set[Entrypoint]
    ]:
        def _(app: web.Application):
            entrypoints: set[Entrypoint] = set()

            # app routes, i.e. "exposed"
            for resource_name, resource in app.router.named_resources().items():
                resource_path = resource.canonical
                for route in resource:
                    assert route.name == resource_name
                    assert route.resource
                    assert route.name is not None

                    if route.method == "HEAD":
                        continue

                    entrypoints.add(
                        Entrypoint(
                            method=route.method,
                            path=resource_path,
                            name=route.name,
                        )
                    )
            return entrypoints

        return _
