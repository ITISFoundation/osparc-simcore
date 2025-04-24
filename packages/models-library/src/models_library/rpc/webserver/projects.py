from datetime import datetime
from typing import Annotated, TypeAlias
from uuid import uuid4

from models_library.projects import NodesDict, ProjectID
from models_library.projects_nodes import Node
from models_library.rpc_pagination import PageRpc
from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict


class ProjectJobRpcGet(BaseModel):
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

    workbench: NodesDict

    # timestamps
    created_at: datetime
    modified_at: datetime

    # Specific to jobs
    job_parent_resource_name: str

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        nodes_examples = Node.model_json_schema()["examples"]
        schema.update(
            {
                "examples": [
                    {
                        "uuid": "12345678-1234-5678-1234-123456789012",
                        "name": "My project",
                        "description": "My project description",
                        "workbench": {f"{uuid4()}": n for n in nodes_examples[2:3]},
                        "created_at": "2023-01-01T00:00:00Z",
                        "modified_at": "2023-01-01T00:00:00Z",
                        "job_parent_resource_name": "solvers/slv_123/release/1.2.3",
                    },
                ]
            }
        )

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra=_update_json_schema_extra,
    )


PageRpcProjectJobRpcGet: TypeAlias = PageRpc[
    # WARNING: keep this definition in models_library and not in the RPC interface
    # otherwise the metaclass PageRpc[*] will create *different* classes in server/client side
    # and will fail to serialize/deserialize these parameters when transmitted/received
    ProjectJobRpcGet
]
