from abc import abstractmethod
from typing import Literal

from models_library.progress_bar import ProgressReport
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import (
    ProgressRabbitMessageNode,
    ProgressRabbitMessageProject,
    ProgressType,
)
from models_library.socketio import SocketMessageDict
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field


class WebSocketMessageBase(BaseModel):
    event_type: str = Field(frozen=True)

    @classmethod
    def get_event_type(cls) -> str:
        _event_type: str = cls.model_fields["event_type"].default
        return _event_type

    @abstractmethod
    def to_socket_dict(self) -> SocketMessageDict:
        ...

    model_config = ConfigDict(frozen=True)


class _WebSocketProjectMixin(BaseModel):
    project_id: ProjectID


class _WebSocketNodeMixin(BaseModel):
    node_id: NodeID


class _WebSocketUserMixin(BaseModel):
    user_id: UserID


class _WebSocketProgressMixin(BaseModel):
    progress_type: ProgressType
    progress_report: ProgressReport


class WebSocketProjectProgress(
    _WebSocketUserMixin,
    _WebSocketProjectMixin,
    _WebSocketProgressMixin,
    WebSocketMessageBase,
):
    event_type: Literal["projectProgress"] = "projectProgress"

    @classmethod
    def from_rabbit_message(
        cls, message: ProgressRabbitMessageProject
    ) -> "WebSocketProjectProgress":
        return cls.model_construct(
            user_id=message.user_id,
            project_id=message.project_id,
            progress_type=message.progress_type,
            progress_report=message.report,
        )

    def to_socket_dict(self) -> SocketMessageDict:
        return SocketMessageDict(
            event_type=self.event_type,
            data=jsonable_encoder(self, exclude={"event_type"}),
        )


class WebSocketNodeProgress(
    _WebSocketUserMixin,
    _WebSocketProjectMixin,
    _WebSocketNodeMixin,
    _WebSocketProgressMixin,
    WebSocketMessageBase,
):
    event_type: Literal["nodeProgress"] = "nodeProgress"

    @classmethod
    def from_rabbit_message(
        cls, message: ProgressRabbitMessageNode
    ) -> "WebSocketNodeProgress":
        return cls.model_construct(
            user_id=message.user_id,
            project_id=message.project_id,
            node_id=message.node_id,
            progress_type=message.progress_type,
            progress_report=message.report,
        )

    def to_socket_dict(self) -> SocketMessageDict:
        return SocketMessageDict(
            event_type=self.event_type,
            data=jsonable_encoder(self, exclude={"event_type"}),
        )
