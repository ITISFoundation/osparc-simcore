from typing import Any, ClassVar

from pydantic import BaseModel, Field, HttpUrl

from .emails import LowerCaseEmailStr


class Badge(BaseModel):
    name: str = Field(
        ...,
        description="Name of the subject",
    )
    image: HttpUrl = Field(
        ...,
        description="Url to the badge",
    )
    url: HttpUrl = Field(
        ...,
        description="Link to the status",
    )

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "name": "osparc.io",
                "image": "https://img.shields.io/website-up-down-green-red/https/itisfoundation.github.io.svg?label=documentation",
                "url": "https://itisfoundation.github.io/",
            }
        }


class Author(BaseModel):
    name: str = Field(
        ...,
        description="Name of the author",
    )
    email: LowerCaseEmailStr = Field(
        ...,
        description="Email address",
    )
    affiliation: str | None = Field(None)

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "name": "Jim Knopf",
                    "email": "deleen@minbar.bab",
                    "affiliation": "Babylon 5",
                },
                {
                    "name": "John Smith",
                    "email": "smith@acme.com",
                },
            ]
        }
