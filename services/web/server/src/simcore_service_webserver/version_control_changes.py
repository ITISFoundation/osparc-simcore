"""

- How to detect that a particular feature/characteristic in an entity has changed over time?

Feature/charateristics of an entity at a given moment can be "snapshot" and given a hash value
- If the same feature at another moment results in a different hash value, it means that this feature
has changed


"""

from typing import Any, Dict, Optional

from aiopg.sa.result import ResultProxy
from models_library.basic_types import SHA1Str
from models_library.projects_nodes import Node

from .utils import compute_sha1

ProjectProxy = ResultProxy


def compute_workbench_checksum(workbench: Dict[str, Any]) -> SHA1Str:
    #
    # UI is NOT accounted in the checksum
    # TODO: review other fields to mask?
    # TODO: search for async def compute_node_hash
    #
    # - Add options with include/exclude fields (e.g. to avoid status)
    #
    normalized = {
        str(k): (Node.parse_obj(v) if not isinstance(v, Node) else v)
        for k, v in workbench.items()
    }
    checksum = compute_sha1(
        {
            k: node.dict(
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
    # cached checksum of project wcopy
    checksum: Optional[SHA1Str] = repo.project_checksum
    is_invalid = not checksum or (checksum and repo.modified < project.last_change_date)
    if is_invalid:
        # invalid -> recompute
        checksum = compute_workbench_checksum(project.workbench)
        # TODO: cache
    assert checksum
    return checksum
