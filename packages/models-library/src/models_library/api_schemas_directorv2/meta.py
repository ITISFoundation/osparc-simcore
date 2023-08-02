from typing import Any, ClassVar

from pydantic import BaseModel, Field

from ..basic_types import VersionStr


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
