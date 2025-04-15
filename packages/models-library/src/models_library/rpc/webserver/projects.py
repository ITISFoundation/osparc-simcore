from datetime import datetime
from typing import Annotated, TypeAlias

from models_library.projects import ProjectID
from models_library.rpc_pagination import PageRpc
from pydantic import BaseModel, ConfigDict, Field


class ProjectRpcGet(BaseModel):
    """
    Minimal information about a project that (for now) will fullfill
    the needs of the api-server. Specifically, the fields needed in
    project to call create_job_from_project
    """

    uuid: Annotated[
        ProjectID,
        Field(description="project unique identifier"),
    ]
    name: Annotated[
        str,
        Field(description="project display name"),
    ]
    description: str

    # timestamps
    creation_date: datetime
    last_change_date: datetime

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )


PageRpcProjectRpcGet: TypeAlias = PageRpc[
    # WARNING: keep this definition in models_library and not in the RPC interface
    # otherwise the metaclass PageRpc[*] will create *different* classes in server/client side
    # and will fail to serialize/deserialize these parameters when transmitted/received
    ProjectRpcGet
]
