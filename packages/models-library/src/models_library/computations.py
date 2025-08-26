from datetime import datetime
from decimal import Decimal
from typing import Any, TypeAlias
from uuid import UUID

from pydantic import AnyUrl, BaseModel

from .projects import ProjectID
from .projects_nodes_io import NodeID
from .projects_state import RunningState


class ComputationTaskWithAttributes(BaseModel):
    project_uuid: ProjectID
    node_id: NodeID
    state: RunningState
    progress: float
    image: dict[str, Any]
    started_at: datetime | None
    ended_at: datetime | None
    log_download_link: AnyUrl | None

    # Attributes added by the webserver
    node_name: str
    osparc_credits: Decimal | None


class ComputationRunWithAttributes(BaseModel):
    project_uuid: ProjectID
    iteration: int
    state: RunningState
    info: dict[str, Any]
    submitted_at: datetime
    started_at: datetime | None
    ended_at: datetime | None

    # Attributes added by the webserver
    root_project_name: str
    project_custom_metadata: dict[str, Any]


CollectionRunID: TypeAlias = UUID


class ComputationCollectionRunWithAttributes(BaseModel):
    collection_run_id: CollectionRunID
    project_ids: list[str]
    state: RunningState
    info: dict[str, Any]
    submitted_at: datetime
    started_at: datetime | None
    ended_at: datetime | None

    # Attributes added by the webserver
    name: str  # Either root project name or collection name if provided by the client on start


class ComputationCollectionRunTaskWithAttributes(BaseModel):
    project_uuid: ProjectID
    node_id: NodeID
    state: RunningState
    progress: float
    image: dict[str, Any]
    started_at: datetime | None
    ended_at: datetime | None
    log_download_link: AnyUrl | None

    # Attributes added by the webserver
    name: str  # Either node name or job name if provided by the client on start
    osparc_credits: Decimal | None
