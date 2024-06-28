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
    released: datetime | None = Field(
        default=None, description="When provided, it indicates the release timestamp"
    )
    retired: datetime | None = Field(
        default=None,
        description="whether this service is planned to be retired. "
        "If None, the service is still active. "
        "If now<retired then the service is deprecated. "
        "If retired<now then the service is retired and should not be used. ",
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
                    "released": "2024-06-20T18:49:17",
                    "retired": "2034-06-20T00:00:00",
                    "compatibility": {"can_update_to": "0.9.10"},
                },
            ]
        }


ReleaseHistory: TypeAlias = list[ServiceRelease]
