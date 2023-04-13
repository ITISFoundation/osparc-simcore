from models_library.projects import AccessRights, Node, Project, StudyUI
from models_library.projects_nodes import InputTypes, OutputTypes
from models_library.projects_nodes_io import SimCoreFileLink

from ...utils.serialization import json_dumps, json_loads


class NewProjectIn(Project):
    """Web-server API model in body for create_project"""

    # - uuid
    # - name
    # - description
    # - prjOwner
    # - accessRights
    # - creationDate
    # - lastChangeDate
    # - thumbnail
    # - workbench
    class Config:
        json_loads = json_loads
        json_dumps = json_dumps


# nopycln: file
__all__: tuple[str, ...] = (
    "AccessRights",
    "InputTypes",
    "Node",
    "OutputTypes",
    "Project",
    "SimCoreFileLink",
    "StudyUI",
)
