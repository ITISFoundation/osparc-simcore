from typing import Annotated

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import BaseModel, Field

from ..api_schemas_directorv2.computations import (
    ComputationGet as _ComputationGetDirectorV2,
)
from ..projects import CommitID, ProjectID
from ._base import InputSchema, OutputSchema


class ComputationPathParams(BaseModel):
    project_id: ProjectID


class ComputationGet(_ComputationGetDirectorV2, OutputSchema):
    # FIXME: camelcase!!
    # NOTE: this is a copy of the same class in models_library.api_schemas_directorv2
    #       but it is used in a different context (webserver)
    #       and we need to add the `OutputSchema` mixin
    #       so that it can be used as a response model in FastAPI
    pass


class ComputationStart(InputSchema):
    # FIXME: camelcase!!
    force_restart: bool = False
    subgraph: Annotated[set[str], Field(default_factory=set)]


class ComputationStarted(OutputSchema):
    # FIXME: camelcase!!
    pipeline_id: Annotated[
        ProjectID, Field(description="ID for created pipeline (=project identifier)")
    ]
    ref_ids: Annotated[
        list[CommitID],
        Field(default_factory=list, description="Checkpoints IDs for created pipeline"),
    ] = DEFAULT_FACTORY
