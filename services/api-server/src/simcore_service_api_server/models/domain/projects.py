from models_library.api_schemas_webserver.projects import ProjectCreateNew
from models_library.projects import AccessRights, Node, Project, StudyUI
from models_library.projects_nodes import InputTypes, OutputTypes
from models_library.projects_nodes_io import SimCoreFileLink

from ...utils.serialization import json_dumps, json_loads


class NewProjectIn(ProjectCreateNew):
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


assert AccessRights  # nosec
assert InputTypes  # nosec
assert Node  # nosec
assert OutputTypes  # nosec
assert Project  # nosec
assert SimCoreFileLink  # nosec
assert StudyUI  # nosec

__all__: tuple[str, ...] = (
    "AccessRights",
    "InputTypes",
    "Node",
    "OutputTypes",
    "Project",
    "SimCoreFileLink",
    "StudyUI",
)
