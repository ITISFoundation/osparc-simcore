from datetime import datetime

from typing import Dict, Any
from pydantic import Field, validator, EmailStr

from .base_models import BaseLoadingModel


class Manifest(BaseLoadingModel):
    _STORAGE_PATH: str = "manifest.yaml"

    version: str = Field(
        ...,
        description=(
            "Version of the formatter used to export the study. This version should "
            "be also used for importing the study back"
        ),
    )

    creation_date_utc: datetime = Field(
        description="UTC date and time from when the project was exported",
        default_factory=datetime.utcnow,
    )

    @validator("version")
    @classmethod
    def _validate_version(cls, v):
        return str(v)


class Project(BaseLoadingModel):
    _STORAGE_PATH: str = "project.yaml"

    name: str = Field(..., description="name of the study")
    description: str = Field(..., description="study description")
    uuid: str = Field(..., description="study unique id")
    last_change_date: datetime = Field(
        ..., alias="lastChangeDate", description="date when study was last changed"
    )
    creation_date: datetime = Field(
        ..., alias="creationDate", description="date when study was created"
    )
    project_owner: EmailStr = Field(
        ..., alias="prjOwner", description="email of the owner of the study"
    )
    thumbnail: str = Field(
        ..., description="contains a link to an image to be used as thumbnail"
    )
    ui: Dict[str, Any] = Field(..., description="contains data used to render the UI")
    workbench: Dict[str, Any] = Field(
        ...,
        description="representation all the information required to run and render studies",
    )

    # TODO: also use uuid from project which needs to get mixed
