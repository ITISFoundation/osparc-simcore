import re
from typing import Any, ClassVar

from models_library.basic_regex import VERSION_RE
from pydantic import BaseModel, ConstrainedStr, Field


class VersionStr(ConstrainedStr):
    regex = re.compile(VERSION_RE)


class Meta(BaseModel):
    name: str
    version: VersionStr
    released: dict[str, VersionStr] | None = Field(
        None, description="Maps every route's path tag with a released version"
    )

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "name": "simcore_service_foo",
                "version": "2.4.45",
                "released": {"v1": "1.3.4", "v2": "2.4.45"},
            }
        }
