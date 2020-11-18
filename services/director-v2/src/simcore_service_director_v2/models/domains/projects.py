from datetime import datetime
from typing import Dict, Optional

from models_library.projects import Project, Workbench
from pydantic import Field
from pydantic.class_validators import validator
from pydantic.networks import HttpUrl
from simcore_postgres_database.models.projects import ProjectType


class ProjectAtDB(Project):
    id: int
    project_type: ProjectType = Field(..., alias="type")
    prjOwner: Optional[int] = Field(..., alias="prj_owner")
    accessRights: Dict = Field(..., alias="access_rights")
    creationDate: datetime = Field(
        ...,
        alias="creation_date",
    )
    lastChangeDate: datetime = Field(
        ...,
        alias="last_change_date",
    )
    published: Optional[bool] = Field(False)
    thumbnail: Optional[HttpUrl] = Field(None)
    workbench: Workbench

    @validator("thumbnail", pre=True)
    @classmethod
    def convert_empty_str_to_none(v):
        if isinstance(v, str) and v == "":
            return None
        return v

    class Config:
        orm_mode = True
