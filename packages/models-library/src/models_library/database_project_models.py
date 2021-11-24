"""
    Models to interact with the projects table in the database

"""
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeIDStr
from pydantic import Field, validator
from pydantic.main import BaseModel, Extra
from pydantic.networks import HttpUrl
from pydantic.types import Json, PositiveInt

from .projects import ClassifierID, ProjectAtDB, ProjectType, Workbench
from .projects_access import AccessRights
from .projects_ui import StudyUI
from .users import GroupID


class _NodeRelaxed(Node):
    class Config(Node.Config):
        # Drops all extra fields passed at the input
        extra = Extra.allow
        allow_population_by_field_name = True


class ProjectForPgInsert(BaseModel):
    """Fields used to insert a new row in a postgres (pg) table"""

    project_type: ProjectType = Field(ProjectType.STANDARD, alias="type")
    uuid: UUID
    name: str
    description: Optional[str]
    thumbnail: Optional[HttpUrl]
    prj_owner: PositiveInt
    access_rights: Dict[GroupID, AccessRights]
    workbench: Dict[NodeIDStr, _NodeRelaxed]
    ui: StudyUI = Field({})
    classifiers: List[ClassifierID] = []
    dev: Dict = {}
    quality: Dict = {}
    published: bool = False
    hidden: bool = False

    class Config:
        extra = Extra.allow
        allow_population_by_field_name = True

    def to_values(self) -> Dict[str, Any]:
        return self.dict(exclude_unset=True, by_alias=True)


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
