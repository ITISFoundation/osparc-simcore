from typing import Final

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID, UserIDAdapter

from ..models import DaskJobID


def generate_dask_job_id(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    run_id: int,
) -> DaskJobID:
    """creates a deterministic dask job id:
    The job ID shall contain the user_id, project_id, node_id and run_id
    """
    return DaskJobID(
        f"{service_key}:{service_version}:userid_{user_id}:projectid_{project_id}:nodeid_{node_id}:runid_{run_id}"
    )


_JOB_ID_PARTS: Final[int] = 6


def parse_dask_job_id(
    job_id: str,
) -> tuple[ServiceKey, ServiceVersion, UserID, ProjectID, NodeID]:
    parts = job_id.split(":")
    assert len(parts) == _JOB_ID_PARTS, f"unexpected job id {parts=}"  # nosec
    return (
        parts[0],
        parts[1],
        UserIDAdapter.validate_python(parts[2][len("userid_") :]),
        ProjectID(parts[3][len("projectid_") :]),
        NodeID(parts[4][len("nodeid_") :]),
    )
