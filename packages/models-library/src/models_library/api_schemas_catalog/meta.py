import re
from typing import Any, ClassVar

from pydantic import BaseModel, ConstrainedStr, Field

# TODO: review this RE
# use https://www.python.org/dev/peps/pep-0440/#version-scheme
# or https://www.python.org/dev/peps/pep-0440/#appendix-b-parsing-version-strings-with-regular-expressions
#
VERSION_RE = r"^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z]+)*)?$"


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
