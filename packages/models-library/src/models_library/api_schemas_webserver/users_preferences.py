from typing import Any, TypeAlias

from pydantic import BaseModel, Field

from ..user_preferences import PreferenceIdentifier


class FrontendUserPreference(BaseModel):
    default_value: Any = Field(
        default=..., alias="defaultValue", description="used by the frontend"
    )
    value: Any = Field(default=..., description="preference value")

    class Config:
        allow_population_by_field_name = True


FrontendUserPreferencesGet: TypeAlias = dict[
    PreferenceIdentifier, FrontendUserPreference
]


class FrontendUserPreferencePatchRequestBody(BaseModel):
    value: Any


class FrontendUserPreferencePatchPathParams(BaseModel):
    preference: PreferenceIdentifier
