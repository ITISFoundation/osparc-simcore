"""

- How to detect that a particular feature/characteristic in an entity has changed over time?

Feature/charateristics of an entity at a given moment can be "snapshot" and given a hash value
- If the same feature at another moment results in a different hash value, it means that this feature
has changed


"""

from typing import Any
from uuid import UUID, uuid3

from models_library.basic_types import SHA1Str
from models_library.projects import ProjectID, ProjectIDStr
from models_library.projects_nodes import Node

from ..projects.models import ProjectProxy
from ..utils import compute_sha1_on_small_dataset


def compute_workbench_checksum(workbench: dict[str, Any]) -> SHA1Str:
    #
    # NOTE that UI is NOT accounted in the checksum
    #
    normalized = {
        str(k): (Node(**v) if not isinstance(v, Node) else v)
        for k, v in workbench.items()
    }

    checksum = compute_sha1_on_small_dataset(
        {
            k: node.model_dump(
                exclude_unset=True,
                exclude_defaults=True,
                exclude_none=True,
                include={
                    "key",
                    "version",
                    "inputs",
                    "input_nodes",
                    "outputs",
                    "output_nodes",
                },
            )
            for k, node in normalized.items()
        }
    )
    return checksum


def _eval_checksum(repo, project: ProjectProxy) -> SHA1Str:
    # cached checksum of project workcopy
    checksum: SHA1Str | None = repo.project_checksum
    is_invalid = not checksum or (checksum and repo.modified < project.last_change_date)
    if is_invalid:
        # invalid -> recompute
        checksum = compute_workbench_checksum(project.workbench)
    assert checksum  # nosec
    return checksum


def eval_workcopy_project_id(
    repo_project_uuid: ProjectID | ProjectIDStr, snapshot_checksum: SHA1Str
) -> ProjectID:
    """
    A working copy is a real project associated to a snapshot so it can be operated
    as a project resource (e.g. run, save, etc).

    The uuid of the workcopy is a composition of the repo-project uuid and the snapshot-checksum
    i.e. all identical snapshots (e.g. different iterations commits) map to the same project workcopy
    can avoid re-run

    If a snapshot is identical but associated to two different repos, then it will still be
    treated as a separate project to avoid colision between e.g. two users having coincidentaly the same
    worbench blueprint. Nonetheless, this could be refined in the future since we could use this
    knowledge to reuse results.
    """
    if isinstance(repo_project_uuid, str):
        repo_project_uuid = UUID(repo_project_uuid)

    return uuid3(repo_project_uuid, snapshot_checksum)
