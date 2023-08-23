from enum import auto
from typing import Any, TypeAlias

from pydantic import BaseModel, Field

from .services import ServiceKey
from .utils.enums import StrAutoEnum


class PreferenceType(StrAutoEnum):
    BACKEND = auto()
    FRONTEND = auto()
    USER_SERVICE = auto()


class PreferenceWidgetType(StrAutoEnum):
    CHECKBOX = auto()


class BaseUserPreferenceModel(BaseModel):
    identifier: str = Field(..., description="has to be unique per preference_type")

    preference_type: PreferenceType = Field(
        ..., description="distinguish between the types of preferences"
    )

    # needs to be encoded to bytes and decoded from bytes
    value: Any | None = Field(
        ...,
        description="the value of the preference. Stored as is and cannot be queried over",
    )


class BaseBackendUserPreference(BaseUserPreferenceModel):
    preference_type: PreferenceType = PreferenceType.BACKEND


class BaseFrontendUserPreference(BaseUserPreferenceModel):
    preference_type: PreferenceType = PreferenceType.FRONTEND

    # NOTE: below fields do not require storage in the DB
    widget_type: PreferenceWidgetType = Field(
        ..., description="type of widget to display in the frontend"
    )
    display_label: str = Field(..., description="short label to display")
    tooltip_message: str = Field(
        ..., description="more information to display when hovering"
    )


class BaseUserServiceUserPreference(BaseUserPreferenceModel):
    preference_type: PreferenceType = PreferenceType.USER_SERVICE

    # NOTE: preferences are stored per service and the version is not considered
    service_key: ServiceKey = Field(
        ..., description="the service which manages the preferences"
    )

    # NOTE: below fields do not require storage in the DB
    last_changed_utc_timestamp: float = Field(
        ...,
        description="needs to be provided to signal that the value of the property changed",
    )


UserPreferenceModel: TypeAlias = (
    BaseBackendUserPreference
    | BaseFrontendUserPreference
    | BaseUserServiceUserPreference
)
