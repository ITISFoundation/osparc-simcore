# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, NamedTuple

import jsonref
import pytest
import yaml


class Entrypoint(NamedTuple):
    name: str
    method: str
    path: str


@lru_cache  # ANE: required to boost tests speed, gains 3.5s per test
def _load(file: Path, base_uri: str = "") -> dict:
    # SEE https://jsonref.readthedocs.io/en/latest/#lazy-load-and-load-on-repr
    data: dict = jsonref.replace_refs(  # type: ignore
        yaml.safe_load(file.read_text()),
        base_uri=base_uri,
        lazy_load=True,  # this data will be iterated
        merge_props=False,
    )
    return data


@pytest.fixture
def openapi_specs_path() -> Path:
    pytest.fail(reason="Must be overriden in caller tests package")


@pytest.fixture
def openapi_specs(openapi_specs_path: Path) -> dict[str, Any]:
    assert openapi_specs_path.is_file()
    # TODO: If openapi_specs_path is a url, download in tmp_dir and get path

    openapi: dict[str, Any] = _load(
        openapi_specs_path, base_uri=openapi_specs_path.as_uri()
    )
    return deepcopy(openapi)


@pytest.fixture
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
