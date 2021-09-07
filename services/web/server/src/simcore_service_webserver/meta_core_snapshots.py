""" Core module: snapshots (and parametrization)

    Extend project's business logic by adding two new concepts, namely
        - project snapshots and
        - parametrizations

"""


from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from models_library.projects import Project

from .meta_models import Snapshot
from .projects import projects_utils

ProjectDict = Dict[str, Any]


async def take_snapshot(
    parent: ProjectDict,
    snapshot_label: Optional[str] = None,
) -> Tuple[ProjectDict, Snapshot]:

    assert Project.parse_obj(parent)  # nosec

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
        name=snapshot_label or f"Snapshot {snapshot_timestamp} [{parent['name']}]",
        created_at=snapshot_timestamp,
        parent_uuid=parent["uuid"],
        project_uuid=child["uuid"],
    )

    return (child, snapshot)
