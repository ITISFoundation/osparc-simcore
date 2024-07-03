from pydantic import BaseModel, Field, HttpUrl

from .emails import LowerCaseEmailStr


class Badge(BaseModel):
    name: str = Field(
        ...,
        description="Name of the subject",
        examples=["travis-ci", "coverals.io", "github.io"],
    )
    image: HttpUrl = Field(
        ...,
        description="Url to the badge",
        examples=[
            "https://travis-ci.org/ITISFoundation/osparc-simcore.svg?branch=master",
            "https://coveralls.io/repos/github/ITISFoundation/osparc-simcore/badge.svg?branch=master",
            "https://img.shields.io/website-up-down-green-red/https/itisfoundation.github.io.svg?label=documentation",
        ],
    )
    url: HttpUrl = Field(
        ...,
        description="Link to the status",
        examples=[
            "https://travis-ci.org/ITISFoundation/osparc-simcore 'State of CI: build, test and pushing images'",
            "https://coveralls.io/github/ITISFoundation/osparc-simcore?branch=master 'Test coverage'",
            "https://itisfoundation.github.io/",
        ],
    )


class Author(BaseModel):
    name: str = Field(..., description="Name of the author", example="Jim Knopf")
    email: LowerCaseEmailStr = Field(
        ...,
        examples=["sun@sense.eight", "deleen@minbar.bab"],
        description="Email address",
    )
    affiliation: str | None = Field(
        None, examples=["Sense8", "Babylon 5"], description="Affiliation of the author"
    )
