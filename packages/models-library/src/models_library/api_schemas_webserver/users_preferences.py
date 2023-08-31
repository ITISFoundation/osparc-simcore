from typing import Any, TypeAlias

from pydantic import BaseModel, Field

from ..user_preferences import PreferenceIdentifier
from ._base import InputSchema, OutputSchema


class FrontendUserPreference(OutputSchema):
    default_value: Any = Field(default=..., description="used by the frontend")
    value: Any = Field(default=..., description="preference value")


AggregatedPreferencesResponse: TypeAlias = dict[
    PreferenceIdentifier, FrontendUserPreference
]


class PatchRequestBody(InputSchema):
    value: Any


class PatchPathParams(BaseModel):
    preference_id: PreferenceIdentifier
