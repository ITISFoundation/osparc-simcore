"""Domain models for groups."""

from typing import Annotated

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
)

__all__: tuple[str, ...] = (
    # models
    "ClassifierItem",
    "Classifiers",
    "TreePath",
)

MAX_SIZE_SHORT_MSG: int = 100


# MODELS


type TreePath = Annotated[
    str,
    StringConstraints(pattern=r"[\w:]+"),  # Examples 'a::b::c
]


class ClassifierItem(BaseModel):
    classifier: str = Field(..., description="Unique identifier used to tag studies or services")
    display_name: str
    short_description: str | None
    url: Annotated[
        HttpUrl | None,
        Field(
            description="Link to more information",
            examples=["https://scicrunch.org/resources/Any/search?q=osparc&l=osparc"],
        ),
    ] = None

    @field_validator("short_description", mode="before")
    @classmethod
    def truncate_to_short(cls, v: str | None) -> str | None:
        if v and len(v) >= MAX_SIZE_SHORT_MSG:
            return v[:MAX_SIZE_SHORT_MSG] + "…"
        return v


class Classifiers(BaseModel):
    # meta
    vcs_url: str | None
    vcs_ref: str | None

    # data
    classifiers: dict[TreePath, ClassifierItem]
