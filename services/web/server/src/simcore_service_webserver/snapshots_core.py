#
#
# Parameter node needs to be evaluated before the workflow is submitted
# Every evaluation creates a snapshot
#
# Constant Param has 1 input adn one output
#   Optimizer can produce semi-cyclic feedback loop by connecting to output of target to
#


from typing import Any, Dict, Iterator, Optional, Tuple
from uuid import UUID, uuid3

from models_library.projects_nodes import Node

from .projects import projects_utils
from .projects.projects_db import ProjectAtDB
from .snapshots_models import Snapshot

ProjectDict = Dict[str, Any]


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


async def take_snapshot(
    parent: ProjectDict,
    snapshot_label: Optional[str] = None,
) -> Tuple[ProjectDict, Snapshot]:

    assert ProjectAtDB.parse_obj(parent)  # nosec

    # FIXME:
    # if is_parametrized_project(parent):
    #     raise NotImplementedError(
    #         "Only non-parametrized projects can be snapshot right now"
    #     )

    # Clones parent's project document
    snapshot_timestamp = parent["last_change_date"]

    child: ProjectDict
    child, nodes_map = projects_utils.clone_project_document(
        project=parent,
        forced_copy_project_id=uuid3(
            UUID(parent["uuid"]), f"snapshot.{snapshot_timestamp}"
        ),
    )

    assert child  # nosec
    assert nodes_map  # nosec
    assert ProjectAtDB.parse_obj(child)  # nosec

    child["name"] += snapshot_label or f" [snapshot {snapshot_timestamp}]"
    # creation_data = state of parent upon copy! WARNING: changes can be state changes and not project definition?
    child["creation_date"] = parent["last_change_date"]
    child["hidden"] = True
    child["published"] = False

    snapshot = Snapshot(
        name=f"Snapshot {snapshot_timestamp} [{parent['name']}]",
        created_at=snapshot_timestamp,
        parent_uuid=parent["uuid"],
        project_uuid=child["uuid"],
    )

    return (child, snapshot)
