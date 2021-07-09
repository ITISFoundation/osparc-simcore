from typing import Iterator, Tuple
from uuid import uuid4

import pytest
from models_library.projects import Project, ProjectAtDB
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from simcore_service_webserver.projects.projects_api import get_project_for_user


# is parametrized project?
def is_param(node: Node):
    return node.key.split("/")[-2] == "param"


def is_parametrized_project(project: Project):
    return any(is_param(node) for node in project.workbench.values())


def iter_params(project: Project) -> Iterator[Tuple[NodeID, Node]]:
    for node_id, node in project.workbench.items():
        if is_param(node):
            yield NodeID(node_id), node


def is_const_param(node: Node) -> bool:
    return is_param(node) and "const" in node.key and not node.inputs


async def test_it(app):

    project_id = str(uuid4())
    user_id = 0

    prj_dict = await get_project_for_user(
        app, project_id, user_id, include_templates=False, include_state=True
    )

    parent_project = Project.parse_obj(prj_dict)

    # three types of "parametrization" nodes

    # const -> replace in connecting nodes

    # generators -> iterable data sources (no inputs connected!)

    # feedback  -> parametrizations with connected inputs!
