from datetime import datetime
from typing import Annotated, TypeAlias

from models_library.projects import NodesDict, ProjectID
from models_library.rpc_pagination import PageRpc
from pydantic import BaseModel, ConfigDict, Field


class ProjectRpcGet(BaseModel):
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

    workbench: Annotated[NodesDict, Field(description="Project's pipeline")]

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
