import datetime
import logging
from abc import abstractmethod
from decimal import Decimal
from enum import Enum, IntEnum, auto
from typing import Any, Literal, TypeAlias

import arrow
from pydantic import BaseModel, Field

from .products import ProductName
from .progress_bar import ProgressReport
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
    channel_name: str

    @classmethod
    def get_channel_name(cls) -> str:
        # NOTE: this returns the channel type name
        name: str = cls.model_fields["channel_name"].default
        return name

    @abstractmethod
    def routing_key(self) -> str | None:
        """this is used to define the topic of the message

        :return: the topic or None (NOTE: None will implicitly use a FANOUT exchange)
        """

    def body(self) -> bytes:
        return self.model_dump_json().encode()


class ProjectMessageBase(BaseModel):
    user_id: UserID
    project_id: ProjectID


class NodeMessageBase(ProjectMessageBase):
    node_id: NodeID


class LoggerRabbitMessage(RabbitMessageBase, NodeMessageBase):
    channel_name: Literal["simcore.services.logs.v2"] = "simcore.services.logs.v2"
    node_id: NodeID | None  # type: ignore[assignment]
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
    SERVICE_CONTAINERS_STARTING = auto()

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
    report: ProgressReport

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
    channel_name: Literal["io.simcore.autoscaling"] = "io.simcore.autoscaling"
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
    channel_name: Literal["io.simcore.service.tracking"] = "io.simcore.service.tracking"

    service_run_id: str = Field(
        ..., description="uniquely identitifies the service run"
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: arrow.utcnow().datetime,
        description="message creation datetime",
    )

    def routing_key(self) -> str | None:
        return None


class DynamicServiceRunningMessage(RabbitMessageBase):
    channel_name: Literal["io.simcore.service.dynamic-service-running"] = Field(
        default="io.simcore.service.dynamic-service-running"
    )

    project_id: ProjectID
    node_id: NodeID
    user_id: UserID
    product_name: ProductName | None
    created_at: datetime.datetime = Field(
        default_factory=lambda: arrow.utcnow().datetime,
        description="message creation datetime",
    )

    def routing_key(self) -> str | None:
        return None


class RabbitResourceTrackingStartedMessage(RabbitResourceTrackingBaseMessage):
    message_type: Literal[
        RabbitResourceTrackingMessageType.TRACKING_STARTED
    ] = RabbitResourceTrackingMessageType.TRACKING_STARTED

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

    parent_project_id: ProjectID
    root_parent_project_id: ProjectID
    root_parent_project_name: str

    parent_node_id: NodeID
    root_parent_node_id: NodeID

    service_key: ServiceKey
    service_version: ServiceVersion
    service_type: ServiceType
    service_resources: ServiceResourcesDict
    service_additional_metadata: dict[str, Any] = Field(
        default_factory=dict, description="service additional 'free' metadata"
    )


class RabbitResourceTrackingHeartbeatMessage(RabbitResourceTrackingBaseMessage):
    message_type: Literal[
        RabbitResourceTrackingMessageType.TRACKING_HEARTBEAT
    ] = RabbitResourceTrackingMessageType.TRACKING_HEARTBEAT


class SimcorePlatformStatus(StrAutoEnum):
    OK = auto()
    BAD = auto()


class RabbitResourceTrackingStoppedMessage(RabbitResourceTrackingBaseMessage):
    message_type: Literal[
        RabbitResourceTrackingMessageType.TRACKING_STOPPED
    ] = RabbitResourceTrackingMessageType.TRACKING_STOPPED

    simcore_platform_status: SimcorePlatformStatus = Field(
        ...,
        description=f"{SimcorePlatformStatus.BAD} if simcore failed to run the service properly",
    )


RabbitResourceTrackingMessages: TypeAlias = (
    RabbitResourceTrackingStartedMessage
    | RabbitResourceTrackingStoppedMessage
    | RabbitResourceTrackingHeartbeatMessage
)


class WalletCreditsMessage(RabbitMessageBase):
    channel_name: Literal["io.simcore.service.wallets"] = "io.simcore.service.wallets"
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
    OUT_OF_CREDITS = 0


class WalletCreditsLimitReachedMessage(RabbitMessageBase):
    channel_name: Literal[
        "io.simcore.service.wallets-credit-limit-reached"
    ] = "io.simcore.service.wallets-credit-limit-reached"
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
