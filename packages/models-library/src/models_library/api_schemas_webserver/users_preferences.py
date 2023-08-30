from typing import Any, TypeAlias

from pydantic import BaseModel, Field

from ..user_preferences import PreferenceName


class FrontendUserPreference(BaseModel):
    # these fields are inherited from `BaseFrontendUserPreference``
    default_value: Any = Field(default=..., alias="defaultValue")
    value: Any

    class Config:
        allow_population_by_field_name = True


FrontendUserPreferencesGet: TypeAlias = dict[PreferenceName, FrontendUserPreference]


class FrontendUserPreferencePatchRequestBody(BaseModel):
    value: Any


class FrontendUserPreferencePatchPathParams(BaseModel):
    frontend_preference_name: PreferenceName
