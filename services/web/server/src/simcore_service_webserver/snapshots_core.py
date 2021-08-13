#
#
# Parameter node needs to be evaluated before the workflow is submitted
# Every evaluation creates a snapshot
#
# Constant Param has 1 input adn one output
#   Optimizer can produce semi-cyclic feedback loop by connecting to output of target to
#


from datetime import datetime
from typing import Any, Dict, Iterator, Optional, Tuple
from uuid import UUID

from models_library.projects import Project
from models_library.projects_nodes import Node

from .projects import projects_utils
from .snapshots_models import Snapshot

ProjectDict = Dict[str, Any]


def is_parametrized(node: Node) -> bool:
    try:
        return "parameter" == node.key.split("/")[-2]
    except IndexError:
        return False


def iter_param_nodes(project: Project) -> Iterator[Tuple[UUID, Node]]:
    for node_id, node in project.workbench.items():
        if is_parametrized(node):
            yield UUID(node_id), node


def is_parametrized_project(project: Project) -> bool:
    return any(is_parametrized(node) for node in project.workbench.values())


async def take_snapshot(
    parent: ProjectDict,
    snapshot_label: Optional[str] = None,
) -> Tuple[ProjectDict, Snapshot]:

    assert Project.parse_obj(parent)  # nosec

    # FIXME:
    # if is_parametrized_project(parent):
    #     raise NotImplementedError(
    #         "Only non-parametrized projects can be snapshot right now"
    #     )

    # Clones parent's project document
    snapshot_timestamp: datetime = parent["lastChangeDate"]
    snapshot_project_uuid: UUID = Snapshot.compose_project_uuid(
        parent["uuid"], snapshot_timestamp
    )

    child: ProjectDict
    child, _ = projects_utils.clone_project_document(
        project=parent,
        forced_copy_project_id=snapshot_project_uuid,
    )

    assert child  # nosec
    assert Project.parse_obj(child)  # nosec

    child["name"] += snapshot_label or f" [snapshot {snapshot_timestamp}]"
    # creation_date = state of parent upon copy! WARNING: changes can be state changes and not project definition?
    child["creationDate"] = snapshot_timestamp
    child["hidden"] = True
    child["published"] = False

    snapshot = Snapshot(
        name=f"Snapshot {snapshot_timestamp} [{parent['name']}]",
        created_at=snapshot_timestamp,
        parent_uuid=parent["uuid"],
        project_uuid=child["uuid"],
    )

    return (child, snapshot)
