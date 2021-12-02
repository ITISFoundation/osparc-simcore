"""
    "Pydantic models will easily **parse** user-supplied data,
    **providing guarantees** about output data structures" in `Robust Python` by P. Viafore

    With that in mind, it seems logic that we cannot expect to always have a single pydantic class for every
    input/output combination we have (e.g. one single `Project` model for all interfaces).

    Here we explore the best way to deal with different models in each context involving
    the project's data
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

from .projects import ClassifierID, ProjectAtDB, ProjectType
from .projects_access import AccessRights
from .projects_ui import StudyUI
from .users import GroupID


class _NodeRelaxed(Node):
    class Config(Node.Config):
        # Drops all extra fields passed at the input
        extra = Extra.allow
        allow_population_by_field_name = True


class ProjectFromCsv(ProjectAtDB):
    """
    Models project in a exported CSV row

    - Inputs: Parses a row from user-supplied CSV export containing a pg project's table
    - Outputs: Produces a data compatible with a project in the pg interface

    These CSV files can be exported from adminer GUI
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
    def _empty_str_parsed_as_false(cls, v):
        # See booleans for >v1.0  https://pydantic-docs.helpmanual.io/usage/types/#booleans
        if isinstance(v, str) and v == "":
            return False
        return v

    @validator("workbench", pre=True, check_fields=False)
    @classmethod
    def _jsonstr_loaded_as_dict(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


class ProjectForPgInsert(BaseModel):
    """
    Model to insert a project row in a pg table

    - Inputs: parses data that fits pg table columns
    - Outputs: filters out and guarantees fields used to insert a new row in a postgres (pg) table


    The model needed to output an update shall be analogous
    but with all Optional (if independent) or inter-dependent optional (e.g. if a is optional then b is also/ or not)
    """

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


# UTILS ---------------------------------


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
