from enum import Enum
from typing import Any, Literal, Optional

from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic import BaseModel, Field
from pydantic.types import NonNegativeFloat


class RabbitEventMessageType(str, Enum):
    RELOAD_IFRAME = "RELOAD_IFRAME"


class RabbitMessageBase(BaseModel):
    channel_name: str = Field(..., const=True)

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


class _RabbitAutoscalingBaseMessage(RabbitMessageBase):
    channel_name: Literal["io.simcore.autoscaling"] = Field(
        default="io.simcore.autoscaling", const=True
    )
    origin: str = Field(
        ..., description="autoscaling app type, in case there would be more than one"
    )


class _RabbitAutoscalingStatusMessage(_RabbitAutoscalingBaseMessage):
    nodes_total: int
    nodes_active: int
    nodes_reserved: int

    cluster_total_resources: dict[str, Any]
    cluster_used_resources: dict[str, Any]


class RabbitAutoscalingIdleMessage(_RabbitAutoscalingStatusMessage):
    ...


class RabbitAutoscalingUpScalingMessage(_RabbitAutoscalingStatusMessage):
    instances_launched: int
    instances_booting: int
    instances_running: int
