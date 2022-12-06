from enum import Enum
from typing import Any, Literal, Optional

from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic import BaseModel
from pydantic.types import NonNegativeFloat


class RabbitEventMessageType(str, Enum):
    RELOAD_IFRAME = "RELOAD_IFRAME"


class RabbitMessageBase(BaseModel):
    channel_name: str

    @classmethod
    def get_channel_name(cls) -> str:
        # NOTE: this returns the channel type name
        return cls.__fields__["channel_name"].default


class NodeMessageBase(BaseModel):
    node_id: NodeID
    user_id: UserID
    project_id: ProjectID


class LoggerRabbitMessage(RabbitMessageBase, NodeMessageBase):
    channel_name: Literal["simcore.services.logs"] = "simcore.services.logs"
    messages: list[str]


class EventRabbitMessage(RabbitMessageBase, NodeMessageBase):
    channel_name: Literal["simcore.services.events"] = "simcore.services.events"
    action: RabbitEventMessageType


class ProgressRabbitMessage(RabbitMessageBase, NodeMessageBase):
    channel_name: Literal["simcore.services.progress"] = "simcore.services.progress"
    progress: NonNegativeFloat


class InstrumentationRabbitMessage(RabbitMessageBase, NodeMessageBase):
    channel_name: Literal[
        "simcore.services.instrumentation"
    ] = "simcore.services.instrumentation"
    metrics: str
    service_uuid: NodeID
    service_type: str
    service_key: str
    service_tag: str
    result: Optional[RunningState] = None


class AutoscalingStatus(str, Enum):
    IDLE = "IDLE"
    SCALING_UP = "SCALING_UP"


class RabbitAutoscalingMessage(RabbitMessageBase):
    channel_name: Literal["io.simcore.autoscaling"] = "io.simcore.autoscaling"
    origin: str
    number_monitored_nodes: int
    cluster_total_resources: dict[str, Any]
    cluster_used_resources: dict[str, Any]
    number_pending_tasks_without_resources: int
    status: AutoscalingStatus
