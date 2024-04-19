from abc import abstractmethod
from typing import Literal

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import ProgressRabbitMessageNode, ProgressType
from models_library.socketio import SocketMessageDict
from models_library.users import UserID
from pydantic import BaseModel, Field


class WebSocketMessageBase(BaseModel):
    event_type: str = Field(..., constr=True)

    @classmethod
    def get_event_type(cls) -> str:
        return cls.__fields__["event_type"].default

    @abstractmethod
    def to_socket_dict(self) -> SocketMessageDict:
        ...

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
        return cls(
            user_id=message.user_id,
            project_id=message.project_id,
            node_id=message.node_id,
            progress_type=message.progress_type,
            progress=message.report.percent_value,
        )
