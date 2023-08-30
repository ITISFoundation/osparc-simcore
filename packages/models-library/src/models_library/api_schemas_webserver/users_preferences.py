from typing import Any, TypeAlias

from pydantic import BaseModel, Field

from ..services_ui import WidgetType
from ..user_preferences import PreferenceName, ValueType


class FrontendUserPreference(BaseModel):
    # these fields are inherited from `BaseFrontendUserPreference``
    expose_in_preferences: bool = Field(default=..., alias="exposeInPreferences")
    widget_type: WidgetType | None = Field(default=..., alias="widget")
    label: str | None = Field(default=...)
    description: str | None = Field(default=...)

    value_type: ValueType = Field(default=..., alias="type")
    default_value: Any = Field(default=..., alias="defaultValue")
    value: Any

    class Config:
        allow_population_by_field_name = True


FrontendUserPreferencesGet: TypeAlias = dict[PreferenceName, FrontendUserPreference]


class FrontendUserPreferencePatchRequestBody(BaseModel):
    value: Any


class FrontendUserPreferencePatchPathParams(BaseModel):
    frontend_preference_name: PreferenceName
