from typing import Annotated, Any

from pydantic import BaseModel, Field

from ..user_preferences import PreferenceIdentifier
from ._base import InputSchema, OutputSchema


class PreferenceConstraints(OutputSchema):
    """Limits applying to a preference value, used by the frontend to render its widget."""

    ge: int | float | None = None
    gt: int | float | None = None
    le: int | float | None = None
    lt: int | float | None = None
    max_length: int | None = None
    min_length: int | None = None
    multiple_of: int | float | None = None
    pattern: str | None = None


class Preference(OutputSchema):
    default_value: Annotated[Any, Field(description="used by the frontend")]
    value: Annotated[Any, Field(description="preference value")]
    constraints: Annotated[PreferenceConstraints | None, Field(description="null when the value is unconstrained")] = (
        None
    )


type AggregatedPreferences = dict[PreferenceIdentifier, Preference]


class PatchRequestBody(InputSchema):
    value: Any


class PatchPathParams(BaseModel):
    preference_id: PreferenceIdentifier
