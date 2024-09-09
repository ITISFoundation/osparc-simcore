from datetime import datetime
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from .services_types import ServiceKey, ServiceVersion
from .utils.change_case import snake_to_camel


class CompatibleService(BaseModel):
    key: ServiceKey | None = Field(
        default=None,
        description="If None, it refer to current service. Used only for inter-service compatibility",
    )
    version: ServiceVersion


class Compatibility(BaseModel):
    # NOTE: as an object it is more maintainable than a list
    can_update_to: CompatibleService = Field(
        ..., description="Latest compatible service at this moment"
    )
    model_config = ConfigDict(alias_generator=snake_to_camel, populate_by_name=True)


class ServiceRelease(BaseModel):
    # from ServiceMetaDataPublished
    version: ServiceVersion
    version_display: str | None = Field(
        default=None, description="If None, then display `version`"
    )
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
    compatibility: Compatibility | None = Field(
        default=None, description="Compatibility with other releases at this moment"
    )
    model_config = ConfigDict(alias_generator=snake_to_camel, populate_by_name=True)


ReleaseHistory: TypeAlias = list[ServiceRelease]
