""" Common utils for OAS script generators
"""

import sys
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI
from models_library.basic_types import LogLevel
from pydantic import BaseModel, Field
from servicelib.fastapi.openapi import override_fastapi_openapi_method

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


class Log(BaseModel):
    level: Optional[LogLevel] = Field("INFO", description="log level")
    message: str = Field(
        ...,
        description="log message. If logger is USER, then it MUST be human readable",
    )
    logger: Optional[str] = Field(
        None, description="name of the logger receiving this message"
    )

    class Config:
        schema_extra = {
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
    resource: Optional[str] = Field(
        None, description="API resource affected by this error"
    )
    field: Optional[str] = Field(None, description="Specific field within the resource")


class Error(BaseModel):
    logs: Optional[list[Log]] = Field(None, description="log messages")
    errors: Optional[list[ErrorItem]] = Field(None, description="errors metadata")
    status: Optional[int] = Field(None, description="HTTP error code")


def create_openapi_specs(
    app: FastAPI, file_path: Path, *, drop_fastapi_default_422: bool = True
):
    override_fastapi_openapi_method(app)
    openapi = app.openapi()

    # Remove these sections
    for section in ("info", "openapi"):
        openapi.pop(section)

    # Removes default response 422
    if drop_fastapi_default_422:
        for _, method_item in openapi.get("paths", {}).items():
            for _, param in method_item.items():
                # NOTE: If description is like this,
                # it assumes it is the default HTTPValidationError from fastapi
                if (
                    e422 := param.get("responses", {}).get("422", None)
                    and e422.get("description") == "Validation Error"
                ):
                    param.get("responses", {}).pop("422", None)

    with file_path.open("wt") as fh:
        yaml.safe_dump(openapi, fh, indent=1, sort_keys=False)

    print("Saved OAS to", file_path)
