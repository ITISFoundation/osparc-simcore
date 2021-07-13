#
#
# Parameter node needs to be evaluated before the workflow is submitted
# Every evaluation creates a snapshot
#
# Constant Param has 1 input adn one output
#   Optimizer can produce semi-cyclic feedback loop by connecting to output of target to
#


from typing import Iterator, Tuple
from uuid import UUID, uuid3

from models_library.projects_nodes import Node

from .parametrization_models import Snapshot
from .projects.projects_db import ProjectAtDB
from .projects.projects_utils import clone_project_document


def is_parametrized(node: Node) -> bool:
    try:
        return "parameter" == node.key.split("/")[-2]
    except IndexError:
        return False


def iter_param_nodes(project: ProjectAtDB) -> Iterator[Tuple[UUID, Node]]:
    for node_id, node in project.workbench.items():
        if is_parametrized(node):
            yield UUID(node_id), node


def is_parametrized_project(project: ProjectAtDB) -> bool:
    return any(is_parametrized(node) for node in project.workbench.values())


def snapshot_project(parent: ProjectAtDB, snapshot_label: str):

    if is_parametrized_project(parent):
        raise NotImplementedError(
            "Only non-parametrized projects can be snapshot right now"
        )

    project, nodes_map = clone_project_document(
        parent.dict(),
        forced_copy_project_id=str(uuid3(namespace=parent.uuid, name=snapshot_label)),
    )

    assert nodes_map  # nosec

    snapshot = Snapshot(
        id, label=snapshot_label, parent_id=parent.id, project_id=project.id
    )
