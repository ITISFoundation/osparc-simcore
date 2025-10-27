from typing import Final
from uuid import uuid4

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import TypeAdapter

from ..models import DaskJobID


def generate_dask_job_id(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> DaskJobID:
    """creates a dask job id:
    The job ID shall contain the user_id, project_id, node_id
    Also, it must be unique
    and it is shown in the Dask scheduler dashboard website
    """
    return DaskJobID(
        f"{service_key}:{service_version}:userid_{user_id}:projectid_{project_id}:nodeid_{node_id}:uuid_{uuid4()}"
    )


_JOB_ID_PARTS: Final[int] = 6


def parse_dask_job_id(
    job_id: str,
) -> tuple[ServiceKey, ServiceVersion, UserID, ProjectID, NodeID]:
    parts = job_id.split(":")
    assert len(parts) == _JOB_ID_PARTS  # nosec
    return (
        parts[0],
        parts[1],
        TypeAdapter(UserID).validate_python(parts[2][len("userid_") :]),
        ProjectID(parts[3][len("projectid_") :]),
        NodeID(parts[4][len("nodeid_") :]),
    )
