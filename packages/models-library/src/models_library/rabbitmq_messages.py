import logging
from enum import Enum, auto
from typing import Any, Literal, Optional

from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from models_library.utils.enums import StrAutoEnum
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


class ProjectMessageBase(BaseModel):
    user_id: UserID
    project_id: ProjectID


class NodeMessageBase(ProjectMessageBase):
    node_id: NodeID


class LoggerRabbitMessage(RabbitMessageBase, NodeMessageBase):
    channel_name: Literal["simcore.services.logs"] = "simcore.services.logs"
    messages: list[str]
    log_level: int = logging.INFO


class EventRabbitMessage(RabbitMessageBase, NodeMessageBase):
    channel_name: Literal["simcore.services.events"] = "simcore.services.events"
    action: RabbitEventMessageType


class ProgressType(StrAutoEnum):
    COMPUTATION_RUNNING = auto()  # NOTE: this is the original only progress report

    CLUSTER_UP_SCALING = auto()
    SIDECARS_PULLING = auto()
    SERVICE_INPUTS_PULLING = auto()
    SERVICE_OUTPUTS_PULLING = auto()
    SERVICE_STATE_PULLING = auto()
    SERVICE_IMAGES_PULLING = auto()

    SERVICE_STATE_PUSHING = auto()
    SERVICE_OUTPUTS_PUSHING = auto()

    PROJECT_CLOSING = auto()


class ProgressMessageMixin(BaseModel):
    channel_name: Literal["simcore.services.progress"] = "simcore.services.progress"
    progress_type: ProgressType = (
        ProgressType.COMPUTATION_RUNNING
    )  # NOTE: backwards compatible
    progress: NonNegativeFloat


class ProgressRabbitMessageNode(RabbitMessageBase, NodeMessageBase):
    ...


class ProgressRabbitMessageProject(RabbitMessageBase, ProjectMessageBase):
    ...


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


class _RabbitAutoscalingBaseMessage(RabbitMessageBase):
    channel_name: Literal["io.simcore.autoscaling"] = Field(
        default="io.simcore.autoscaling", const=True
    )
    origin: str = Field(
        ..., description="autoscaling app type, in case there would be more than one"
    )


class RabbitAutoscalingStatusMessage(_RabbitAutoscalingBaseMessage):
    nodes_total: int = Field(
        ..., description="total number of usable nodes (machines) in the cluster"
    )
    nodes_active: int = Field(
        ..., description="number of active nodes (curently in use)"
    )
    nodes_drained: int = Field(
        ...,
        description="number of drained nodes (currently empty but ready for use if needed)",
    )

    cluster_total_resources: dict[str, Any] = Field(
        ..., description="the total available resources in the cluster (cpu, ram, ...)"
    )
    cluster_used_resources: dict[str, Any] = Field(
        ..., description="the used resources in the cluster (cpu, ram, ...)"
    )

    instances_pending: int = Field(
        ..., description="the number of EC2 instances currently in pending state in AWS"
    )
    instances_running: int = Field(
        ..., description="the number of EC2 instances currently in running state in AWS"
    )
