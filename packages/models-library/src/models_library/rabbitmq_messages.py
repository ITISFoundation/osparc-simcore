import datetime
import logging
from abc import abstractmethod
from decimal import Decimal
from enum import Enum, IntEnum, auto
from typing import Any, Literal, TypeAlias

import arrow
from models_library.products import ProductName
from pydantic import BaseModel, Field
from pydantic.types import NonNegativeFloat

from .projects import ProjectID
from .projects_nodes_io import NodeID
from .projects_state import RunningState
from .services import ServiceKey, ServiceType, ServiceVersion
from .services_resources import ServiceResourcesDict
from .users import UserID
from .utils.enums import StrAutoEnum
from .wallets import WalletID

LogLevelInt: TypeAlias = int
LogMessageStr: TypeAlias = str


class RabbitEventMessageType(str, Enum):
    __slots__ = ()

    RELOAD_IFRAME = "RELOAD_IFRAME"


class RabbitMessageBase(BaseModel):
    channel_name: str = Field(..., const=True)

    @classmethod
    def get_channel_name(cls) -> str:
        # NOTE: this returns the channel type name
        name: str = cls.__fields__["channel_name"].default
        return name

    @abstractmethod
    def routing_key(self) -> str | None:
        """this is used to define the topic of the message

        :return: the topic or None (NOTE: None will implicitely use a FANOUT exchange)
        """

    def body(self) -> bytes:
        return self.json().encode()


class ProjectMessageBase(BaseModel):
    user_id: UserID
    project_id: ProjectID


class NodeMessageBase(ProjectMessageBase):
    node_id: NodeID


class LoggerRabbitMessage(RabbitMessageBase, NodeMessageBase):
    channel_name: Literal["simcore.services.logs.v2"] = "simcore.services.logs.v2"
    node_id: NodeID | None
    messages: list[LogMessageStr]
    log_level: LogLevelInt = logging.INFO

    def routing_key(self) -> str:
        return f"{self.project_id}.{self.log_level}"


class EventRabbitMessage(RabbitMessageBase, NodeMessageBase):
    channel_name: Literal["simcore.services.events"] = "simcore.services.events"
    action: RabbitEventMessageType

    def routing_key(self) -> str | None:
        return None


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


class ProgressMessageMixin(RabbitMessageBase):
    channel_name: Literal[
        "simcore.services.progress.v2"
    ] = "simcore.services.progress.v2"
    progress_type: ProgressType = (
        ProgressType.COMPUTATION_RUNNING
    )  # NOTE: backwards compatible
    progress: NonNegativeFloat

    def routing_key(self) -> str | None:
        return None


class ProgressRabbitMessageNode(ProgressMessageMixin, NodeMessageBase):
    def routing_key(self) -> str | None:
        return f"{self.project_id}.{self.node_id}"


class ProgressRabbitMessageProject(ProgressMessageMixin, ProjectMessageBase):
    def routing_key(self) -> str | None:
        return f"{self.project_id}.all_nodes"


class InstrumentationRabbitMessage(RabbitMessageBase, NodeMessageBase):
    channel_name: Literal[
        "simcore.services.instrumentation"
    ] = "simcore.services.instrumentation"
    metrics: str
    service_uuid: NodeID
    service_type: str
    service_key: str
    service_tag: str
    result: RunningState | None = None
    simcore_user_agent: str

    def routing_key(self) -> str | None:
        return None


class _RabbitAutoscalingBaseMessage(RabbitMessageBase):
    channel_name: Literal["io.simcore.autoscaling"] = Field(
        default="io.simcore.autoscaling", const=True
    )
    origin: str = Field(
        ..., description="autoscaling app type, in case there would be more than one"
    )

    def routing_key(self) -> str | None:
        return None


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


class RabbitResourceTrackingMessageType(StrAutoEnum):
    TRACKING_STARTED = auto()
    TRACKING_HEARTBEAT = auto()
    TRACKING_STOPPED = auto()


class RabbitResourceTrackingBaseMessage(RabbitMessageBase):
    channel_name: Literal["io.simcore.service.tracking"] = Field(
        default="io.simcore.service.tracking", const=True
    )

    service_run_id: str = Field(
        ..., description="uniquely identitifies the service run"
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: arrow.utcnow().datetime,
        description="message creation datetime",
    )

    def routing_key(self) -> str | None:
        return None


class RabbitResourceTrackingStartedMessage(RabbitResourceTrackingBaseMessage):
    message_type: RabbitResourceTrackingMessageType = Field(
        default=RabbitResourceTrackingMessageType.TRACKING_STARTED, const=True
    )

    wallet_id: WalletID | None
    wallet_name: str | None

    pricing_plan_id: int | None
    pricing_unit_id: int | None
    pricing_unit_cost_id: int | None

    product_name: str
    simcore_user_agent: str

    user_id: UserID
    user_email: str

    project_id: ProjectID
    project_name: str

    node_id: NodeID
    node_name: str

    service_key: ServiceKey
    service_version: ServiceVersion
    service_type: ServiceType
    service_resources: ServiceResourcesDict
    service_additional_metadata: dict[str, Any] = Field(
        default_factory=dict, description="service additional 'free' metadata"
    )


class RabbitResourceTrackingHeartbeatMessage(RabbitResourceTrackingBaseMessage):
    message_type: RabbitResourceTrackingMessageType = Field(
        default=RabbitResourceTrackingMessageType.TRACKING_HEARTBEAT, const=True
    )


class SimcorePlatformStatus(StrAutoEnum):
    OK = auto()
    BAD = auto()


class RabbitResourceTrackingStoppedMessage(RabbitResourceTrackingBaseMessage):
    message_type: RabbitResourceTrackingMessageType = Field(
        default=RabbitResourceTrackingMessageType.TRACKING_STOPPED, const=True
    )

    simcore_platform_status: SimcorePlatformStatus = Field(
        ...,
        description=f"{SimcorePlatformStatus.BAD} if simcore failed to run the service properly",
    )


RabbitResourceTrackingMessages = (
    RabbitResourceTrackingStartedMessage
    | RabbitResourceTrackingStoppedMessage
    | RabbitResourceTrackingHeartbeatMessage
)


class WalletCreditsMessage(RabbitMessageBase):
    channel_name: Literal["io.simcore.service.wallets"] = Field(
        default="io.simcore.service.wallets", const=True
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: arrow.utcnow().datetime,
        description="message creation datetime",
    )
    wallet_id: WalletID
    credits: Decimal
    product_name: ProductName

    def routing_key(self) -> str | None:
        return f"{self.wallet_id}"


class CreditsLimit(IntEnum):
    MIN_CREDITS = 0


class WalletCreditsLimitReachedMessage(RabbitMessageBase):
    channel_name: Literal["io.simcore.service.wallets-credit-limit-reached"] = Field(
        default="io.simcore.service.wallets-credit-limit-reached", const=True
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: arrow.utcnow().datetime,
        description="message creation datetime",
    )
    service_run_id: str = Field(
        ..., description="uniquely identitifies the service run"
    )
    user_id: UserID
    project_id: ProjectID
    node_id: NodeID
    wallet_id: WalletID
    credits: Decimal
    credits_limit: CreditsLimit

    def routing_key(self) -> str | None:
        return f"{self.wallet_id}.{self.credits_limit}"
