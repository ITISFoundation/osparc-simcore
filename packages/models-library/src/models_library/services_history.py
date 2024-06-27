from datetime import datetime
from typing import Any, ClassVar, TypeAlias

from pydantic import BaseModel, Field

from .services_types import ServiceVersion


class Compatibility(BaseModel):
    # NOTE: as an object it is more maintainable than a list
    can_update_to: ServiceVersion = Field(
        ...,
        description="Latest compatible version at this moment."
        "Current service can update to this version and still work",
    )


class ServiceRelease(BaseModel):
    # from ServiceMetaDataPublished
    version: ServiceVersion
    version_display: str | None = Field(default=None)
    released_at: datetime | None = Field(default=None)
    deprecated_at: datetime | None = Field(
        default=None, description="If deprecated, it sets the deprecation date"
    )

    # computed compatibility
    compatibility: Compatibility | None = Field(default=None)

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                # minimal
                {
                    "version": "0.9.0",
                },
                # complete
                {
                    "version": "0.9.1",
                    "version_display": "Matterhorn",
                    "released_at": "2024-06-20T18:49:17",
                    "deprecated_at": "2034-06-20T00:00:00",
                    "compatibility": {"can_update_to": "0.9.10"},
                },
            ]
        }


ReleaseHistory: TypeAlias = list[ServiceRelease]
