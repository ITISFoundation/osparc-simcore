from typing import Literal

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import ProgressRabbitMessageNode, ProgressType
from models_library.users import UserID
from pydantic import BaseModel, Field


class WebSocketMessageBase(BaseModel):
    event_type: str = Field(..., constr=True)

    class Config:
        frozen = True


class _WebSocketProjectMixin(BaseModel):
    project_id: ProjectID


class _WebSocketNodeMixin(BaseModel):
    node_id: NodeID


class WebSocketNodeProgress(
    _WebSocketProjectMixin, _WebSocketNodeMixin, WebSocketMessageBase
):
    event_type: Literal["nodeProgress"] = "nodeProgress"
    user_id: UserID
    progress_type: ProgressType
    progress: float

    @classmethod
    def from_rabbit_message(
        cls, message: ProgressRabbitMessageNode
    ) -> "WebSocketNodeProgress":
        return cls()
