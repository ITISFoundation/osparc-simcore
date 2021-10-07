"""
    Models to interact with the projects table in the database

"""
import csv
import json
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeIDStr
from pydantic import Field, validator
from pydantic.main import Extra
from pydantic.networks import HttpUrl
from pydantic.types import Json, PositiveInt

from .projects import ProjectAtDB, ProjectCommons, ProjectType


class ProjectDbSelect(ProjectCommons):
    """Fields used to select (i.e. read) rows in table"""

    id: int = Field(..., description="The table primary index")

    project_type: ProjectType = Field(..., alias="type", description="The project type")

    prj_owner: Optional[int] = Field(..., description="The project owner id")

    published: Optional[bool] = Field(
        False, description="Defines if a study is available publicly"
    )

    @validator("project_type", pre=True)
    @classmethod
    def convert_sql_alchemy_enum(cls, v):
        if isinstance(v, Enum):
            return v.value
        return v

    class Config:
        orm_mode = True
        use_enum_values = True


class ProjectDbInsert(ProjectCommons):
    """Fields used to insert a new row in table"""

    # Within this context, there is no need to set a default
    # value from table since the sa_tables will take care of that
    project_type: Optional[ProjectType] = Field(None, alias="type")
    uuid: UUID
    name: str
    description: Optional[str]
    thumbnail: Optional[HttpUrl]

    prj_owner: PositiveInt

    access_rights: Dict[GroupID, AccessRights]

    workbench: Dict[NodeIDStr, Node]

    ui: Optional[StudyUI]

    classifiers: Optional[List[ClassifierID]] = Field(default_factory=list)

    dev: Dict
    quality: Dict

    ui: Json
    classifiers: str  # FIXME: this is ARRAY[sa.STRING]
    dev: Json
    quality: Json
    hidden: bool

    class Config:
        extra = Extra.forbid


class ProjectFromCsv(ProjectAtDB):
    """Parse database's project from a CSV export

    Adds extra tooling (i.e. validation and conversion logic) to correctly
    read and parse rows of a projects table in the database that was exported
    as a CSV file (as produced by adminer)
    """

    # These fields below are REQUIRED in this context
    # since ALL columns are expected from an export CSV files

    access_rights: Json
    ui: Json
    classifiers: str  # FIXME: this is ARRAY[sa.STRING]
    dev: Json
    quality: Json
    hidden: bool

    class Config:
        extra = Extra.forbid

    # NOTE: validators introduced to parse CSV

    @validator("published", "hidden", pre=True, check_fields=False)
    @classmethod
    def empty_str_parsed_as_false(cls, v):
        # See booleans for >v1.0  https://pydantic-docs.helpmanual.io/usage/types/#booleans
        if isinstance(v, str) and v == "":
            return False
        return v

    @validator("workbench", pre=True, check_fields=False)
    @classmethod
    def jsonstr_loaded_as_dict(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


# UTILS


def load_projects_exported_as_csv(
    csvpath: Path, *, delimiter: str = ",", **reader_options
) -> List[ProjectAtDB]:
    """Loads a project table exported as a CSV and returns a list of models"""
    models = []
    with csvpath.open(encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter, **reader_options)
        for row in reader:
            model = ProjectFromCsv.parse_obj(row)
            models.append(model)
    return models
