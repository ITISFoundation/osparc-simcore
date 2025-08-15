from datetime import datetime
from typing import Annotated, TypeAlias
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

from ...projects import NodesDict, ProjectID
from ...projects_nodes import Node
from ...rpc_pagination import PageRpc


class MetadataFilterItem(BaseModel):
    name: str
    pattern: str


class ListProjectsMarkedAsJobRpcFilters(BaseModel):
    """Filters model for the list_projects_marked_as_jobs RPC.

    NOTE: Filters models are used to validate all possible filters in an API early on,
    particularly to ensure compatibility and prevent conflicts between different filters.
    """

    job_parent_resource_name_prefix: str | None = None

    any_custom_metadata: Annotated[
        list[MetadataFilterItem] | None,
        Field(description="Searchs for matches of any of the custom metadata fields"),
    ] = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "job_parent_resource_name_prefix": "solvers/solver123",
                        "any_custom_metadata": [
                            {
                                "name": "solver_type",
                                "pattern": "FEM",
                            },
                            {
                                "name": "mesh_cells",
                                "pattern": "1*",
                            },
                        ],
                    },
                    {
                        "any_custom_metadata": [
                            {
                                "name": "solver_type",
                                "pattern": "*CFD*",
                            }
                        ],
                    },
                    {"job_parent_resource_name_prefix": "solvers/solver123"},
                ]
            }
        )

    model_config = ConfigDict(
        json_schema_extra=_update_json_schema_extra,
    )


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
    storage_assets_deleted: bool

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        nodes_examples = Node.model_json_schema()["examples"]
        schema.update(
            {
                "examples": [
                    {
                        "uuid": "12345678-1234-5678-1234-123456789012",
                        "name": "A solver job",
                        "description": "A description of a solver job with a single node",
                        "workbench": {f"{uuid4()}": n for n in nodes_examples[2:3]},
                        "created_at": "2023-01-01T00:00:00Z",
                        "modified_at": "2023-01-01T00:00:00Z",
                        "job_parent_resource_name": "solvers/simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper/releases/2.0.2",
                        "storage_data_deleted": "false",
                    },
                    {
                        "uuid": "00000000-1234-5678-1234-123456789012",
                        "name": "A study job",
                        "description": "A description of a study job with many node",
                        "workbench": {f"{uuid4()}": n for n in nodes_examples},
                        "created_at": "2023-02-01T00:00:00Z",
                        "modified_at": "2023-02-01T00:00:00Z",
                        "job_parent_resource_name": "studies/96642f2a-a72c-11ef-8776-02420a00087d",
                        "storage_data_deleted": "true",
                    },
                    {
                        "uuid": "00000000-0000-5678-1234-123456789012",
                        "name": "A program job",
                        "description": "A program of a solver job with a single node",
                        "workbench": {f"{uuid4()}": n for n in nodes_examples[2:3]},
                        "created_at": "2023-03-01T00:00:00Z",
                        "modified_at": "2023-03-01T00:00:00Z",
                        "job_parent_resource_name": "program/simcore%2Fservices%2Fdynamic%2Fjupyter/releases/5.0.2",
                        "storage_data_deleted": "false",
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
