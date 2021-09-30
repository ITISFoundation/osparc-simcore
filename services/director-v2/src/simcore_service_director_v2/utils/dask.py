from typing import Tuple
from uuid import uuid4

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID

from ..models.schemas.constants import UserID


def generate_dask_job_id(
    service_key: str,
    service_version: str,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> str:
    """creates a dask job id:
    The job ID shall contain the user_id, project_id, node_id
    Also, it must be unique
    and it is shown in the Dask scheduler dashboard website
    """
    return f"{service_key}:{service_version}:userid_{user_id}:projectid_{project_id}:nodeid_{node_id}:uuid_{uuid4()}"


def parse_dask_job_id(job_id: str) -> Tuple[str, str, UserID, ProjectID, NodeID]:
    parts = job_id.split(":")
    assert len(parts) == 6  # nosec
    return (
        parts[0],
        parts[1],
        UserID(parts[2][len("userid_") :]),
        ProjectID(parts[3][len("projectid_") :]),
        NodeID(parts[4][len("nodeid_") :]),
    )
