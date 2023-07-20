""" Common utils for OAS script generators
"""

import inspect
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar, NamedTuple

import yaml
from fastapi import FastAPI
from models_library.basic_types import LogLevel
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo
from servicelib.fastapi.openapi import override_fastapi_openapi_method

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


class Log(BaseModel):
    level: LogLevel | None = Field("INFO", description="log level")
    message: str = Field(
        ...,
        description="log message. If logger is USER, then it MUST be human readable",
    )
    logger: str | None = Field(
        None, description="name of the logger receiving this message"
    )

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "message": "Hi there, Mr user",
                "level": "INFO",
                "logger": "user-logger",
            }
        }


class ErrorItem(BaseModel):
    code: str = Field(
        ...,
        description="Typically the name of the exception that produced it otherwise some known error code",
    )
    message: str = Field(..., description="Error message specific to this item")
    resource: str | None = Field(
        None, description="API resource affected by this error"
    )
    field: str | None = Field(None, description="Specific field within the resource")


class Error(BaseModel):
    logs: list[Log] | None = Field(None, description="log messages")
    errors: list[ErrorItem] | None = Field(None, description="errors metadata")
    status: int | None = Field(None, description="HTTP error code")


def create_openapi_specs(app: FastAPI, *, drop_fastapi_default_422: bool = True):
    override_fastapi_openapi_method(app)
    openapi = app.openapi()

    # Remove these sections
    for section in ("info", "openapi"):
        openapi.pop(section, None)

    schemas = openapi["components"]["schemas"]
    for section in ("HTTPValidationError", "ValidationError"):
        schemas.pop(section, None)

    # Removes default response 422
    if drop_fastapi_default_422:
        for method_item in openapi.get("paths", {}).values():
            for param in method_item.values():
                # NOTE: If description is like this,
                # it assumes it is the default HTTPValidationError from fastapi
                if (e422 := param.get("responses", {}).get("422", None)) and e422.get(
                    "description"
                ) == "Validation Error":
                    param.get("responses", {}).pop("422", None)
    return openapi


def create_and_save_openapi_specs(
    app: FastAPI, file_path: Path, *, drop_fastapi_default_422: bool = True
):
    openapi = create_openapi_specs(
        app=app, drop_fastapi_default_422=drop_fastapi_default_422
    )
    with file_path.open("wt") as fh:
        yaml.safe_dump(openapi, fh, indent=1, sort_keys=False)
    print("Saved OAS to", file_path)


class ParamSpec(NamedTuple):
    name: str
    annotated_type: type
    field_info: FieldInfo


def assert_handler_signature_against_model(
    handler: Callable, model_cls: type[BaseModel]
):
    sig = inspect.signature(handler)

    # query, path and body parameters
    specs_params = [
        ParamSpec(param.name, param.annotation, param.default)
        for param in sig.parameters.values()
    ]

    # query and path parameters
    implemented_params = [
        ParamSpec(field.name, field.type_, field.field_info)
        for field in model_cls.__fields__.values()
    ]

    assert {p.name for p in implemented_params}.issubset(  # nosec
        {p.name for p in specs_params}
    ), f"Entrypoint {handler} does not implement OAS"
