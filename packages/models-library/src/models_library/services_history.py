from datetime import datetime
from typing import Annotated, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from .services_types import ServiceKey, ServiceVersion
from .utils.change_case import snake_to_camel


class CompatibleService(BaseModel):
    key: Annotated[
        ServiceKey | None,
        Field(
            description="If None, it refer to current service. Used only for inter-service compatibility"
        ),
    ] = None
    version: ServiceVersion


class Compatibility(BaseModel):
    can_update_to: Annotated[
        CompatibleService, Field(description="Latest compatible service at this moment")
    ]

    model_config = ConfigDict(alias_generator=snake_to_camel, populate_by_name=True)


class ServiceRelease(BaseModel):
    version: ServiceVersion
    version_display: Annotated[
        str | None, Field(description="If None, then display `version`")
    ] = None
    released: Annotated[
        datetime | None,
        Field(description="When provided, it indicates the release timestamp"),
    ] = None
    retired: Annotated[
        datetime | None,
        Field(
            description="whether this service is planned to be retired. If None, the service is still active. If now<retired then the service is deprecated. If retired<now then the service is retired and should not be used."
        ),
    ] = None
    compatibility: Annotated[
        Compatibility | None,
        Field(description="Compatibility with other releases at this moment"),
    ] = None

    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                # minimal
                {"version": "0.9.0"},
                # complete
                {
                    "version": "0.9.1",
                    "version_display": "Matterhorn",
                    "released": "2024-06-20T18:49:17",
                    "retired": "2034-06-20T00:00:00",
                    "compatibility": {
                        "can_update_to": {
                            "version": "0.9.10",
                            "service": "simcore/services/comp/foo",
                        }
                    },
                },
            ]
        },
    )


ReleaseHistory: TypeAlias = list[ServiceRelease]
