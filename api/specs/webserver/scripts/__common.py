import functools
import types
from types import FunctionType
from typing import Any, Dict, Generic, List, Optional, Tuple, TypeVar

from fastapi.applications import FastAPI
from fastapi.routing import APIRoute, APIRouter
from pydantic import PositiveInt
from pydantic.fields import Field
from pydantic.generics import GenericModel
from pydantic.main import BaseModel, Extra
from pydantic.networks import AnyHttpUrl
from pydantic.types import NonNegativeInt, constr

# see https://google.aip.dev/122
ResourceName = constr(regex=r"^(.+)\/([^\/]+)$")
ResourceID = constr(min_length=1, max_length=63)
UserSetResourceID = constr(
    regex=r"^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$", min_length=1, max_length=63
)
CollectionID = constr(regex=r"[a-z][a-zA-Z0-9]*")


class Resource(BaseModel):
    # e.g. format: publishers/{publisher}/books/{book}
    name: ResourceName = Field(...)


# PAGINATION ----------------------------------------


class PageMetaInfoLimitOffset(BaseModel):
    limit: PositiveInt = 20
    total: NonNegativeInt
    offset: NonNegativeInt = 0
    count: NonNegativeInt


class PageLinks(BaseModel):
    self: AnyHttpUrl
    first: AnyHttpUrl
    prev: Optional[AnyHttpUrl]
    next: Optional[AnyHttpUrl]
    last: AnyHttpUrl

    class Config:
        extra = Extra.forbid


ItemT = TypeVar("ItemT")


class Page(GenericModel, Generic[ItemT]):
    meta: PageMetaInfoLimitOffset = Field(alias="_meta")
    links: PageLinks = Field(alias="_links")
    data: List[ItemT]


DataT = TypeVar("DataT")


class Error(BaseModel):
    code: int
    message: str


class Envelope(GenericModel, Generic[DataT]):
    data: Optional[DataT]
    error: Optional[Error]


# OVERRIDES APP ---------------------------------------------------------------------


def copy_func(f):
    # SEE https://stackoverflow.com/questions/13503079/how-to-create-a-copy-of-a-python-function
    g = types.FunctionType(
        f.__code__,
        f.__globals__,
        name=f.__name__,
        argdefs=f.__defaults__,
        closure=f.__closure__,
    )
    g = functools.update_wrapper(g, f)
    g.__kwdefaults__ = f.__kwdefaults__
    return g


def redefine_operation_id_in_router(router: APIRouter, operation_id_prefix: str):
    """
    Overrides default operation_ids assigning the same name as the handler functions and a prefix

    MUST be called only after all routes have been added.

    PROS: auto-generated client has one-to-one correspondence and human readable names
    CONS: highly coupled. Changes in server handler names will change client
    """
    for route in router.routes:
        if isinstance(route, APIRoute):
            assert isinstance(route.endpoint, FunctionType)  # nosec
            route.operation_id = (
                f"{operation_id_prefix}._{route.endpoint.__name__}_handler"
            )


# https://swagger.io/docs/specification/data-models/data-types/#numbers
SCHEMA_TO_PYTHON_TYPES = {"integer": int, "number": float}

SKIP = (
    "examples",
    # SEE openapi-standard: https://swagger.io/docs/specification/adding-examples/
    # - exampleS are Dicts and not Lists
    "patternProperties"
    # SEE Unsupported openapi-standard: https://swagger.io/docs/specification/data-models/keywords/?sbsearch=patternProperties
    # SEE https://github.com/OAI/OpenAPI-Specification/issues/687
    # SEE https://json-schema.org/understanding-json-schema/reference/object.html#pattern-properties
)


def _patch_openapi_specs(app_openapi: Dict[str, Any]):
    """Patches app.openapi with some fixes and osparc conventions"""

    def _patch(node):
        if isinstance(node, Dict):
            for key in list(node.keys()):
                # SEE fastapi ISSUE: https://github.com/tiangolo/fastapi/issues/240 (test_openap.py::test_exclusive_min_openapi_issue )
                # SEE openapi-standard: https://swagger.io/docs/specification/data-models/data-types/#range
                if key == "exclusiveMinimum":
                    cast_to_python = SCHEMA_TO_PYTHON_TYPES[node["type"]]
                    node["minimum"] = cast_to_python(node[key])
                    node["exclusiveMinimum"] = True

                elif key == "exclusiveMaximum":
                    cast_to_python = SCHEMA_TO_PYTHON_TYPES[node["type"]]
                    node["maximum"] = cast_to_python(node[key])
                    node["exclusiveMaximum"] = True

                elif key in SKIP:
                    node.pop(key)
                    continue

                _patch(node[key])

        elif isinstance(node, list):
            for value in node:
                _patch(value)

    _patch(app_openapi)


def override_fastapi_openapi_method(app: FastAPI) -> FastAPI:
    # pylint: disable=protected-access
    app._original_openapi = types.MethodType(copy_func(app.openapi), app)  # type: ignore

    def _custom_openapi_method(self: FastAPI) -> Dict:
        """Overrides FastAPI.openapi member function
        returns OAS schema with vendor extensions
        """
        # NOTE: see fastapi.applications.py:FastApi.openapi(self) implementation
        if not self.openapi_schema:
            self.openapi_schema = self._original_openapi()  # type: ignore
            _patch_openapi_specs(self.openapi_schema)

        return self.openapi_schema

    app.openapi = types.MethodType(_custom_openapi_method, app)
    return app


__all__: Tuple[str, ...] = ("Page", "Envelope", "override_fastapi_openapi_method")
