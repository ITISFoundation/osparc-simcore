# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Dict, Iterator, Tuple
from uuid import UUID, uuid4

import pytest
from aiohttp import web
from models_library.projects import Project, ProjectAtDB
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from simcore_service_webserver.constants import APP_PROJECT_DBAPI
from simcore_service_webserver.parametrization_core import snapshot_project
from simcore_service_webserver.projects.projects_api import get_project_for_user
from simcore_service_webserver.projects.projects_db import APP_PROJECT_DBAPI
from simcore_service_webserver.projects.projects_utils import clone_project_document


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


@pytest.fixture()
def app():
    pass


@pytest.fixture
def project_id() -> UUID:
    return uuid4()


@pytest.fixture
def user_id() -> int:
    return 1


async def test_snapshot_standard_project(
    app: web.Application, project_id: UUID, user_id: int
):

    prj_dict: Dict = await get_project_for_user(
        app, str(project_id), user_id, include_templates=False, include_state=False
    )

    # validates API project data
    project = Project.parse_obj(prj_dict)

    cloned_prj_dict = clone_project_document(prj_dict)

    cloned_project = Project.parse_obj(cloned_prj_dict)

    # project_snapshot = snapshot_project(standard_project)
    # assert isinstance(project_snapshot, Project)
    assert cloned_project.uuid != project.uuid

    projects_repo = app[APP_PROJECT_DBAPI]

    new_project = await projects_repo.replace_user_project(
        new_project, user_id, project_uuid, include_templates=True
    )

    # have same pipeline but different node uuids
    # assert project_snapshot.

    # removes states: snapshots is always un-run??

    # three types of "parametrization" nodes

    # const -> replace in connecting nodes

    # generators -> iterable data sources (no inputs connected!)

    # feedback  -> parametrizations with connected inputs!


#
# - I have a project
# - Take a snapshot
#   - if the project is standard -> clone
#   - if the project is parametrized
#      - clone parametrized?
#      - evaluate param-nodes?
#
