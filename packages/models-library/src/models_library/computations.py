from datetime import datetime
from decimal import Decimal
from typing import Any

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
