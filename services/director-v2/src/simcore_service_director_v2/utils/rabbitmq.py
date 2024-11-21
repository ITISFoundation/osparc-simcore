from typing import Any

from models_library.progress_bar import ProgressReport
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import (
    InstrumentationRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStartedMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from models_library.services import ServiceKey, ServiceType, ServiceVersion
from models_library.services_resources import ServiceResourcesDict
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import NonNegativeFloat
from servicelib.logging_utils import LogLevelInt
from servicelib.rabbitmq import RabbitMQClient

from ..models.comp_tasks import CompTaskAtDB


async def publish_service_started_metrics(
    rabbitmq_client: RabbitMQClient,
    *,
    user_id: UserID,
    simcore_user_agent: str,
    task: CompTaskAtDB,
) -> None:
    message = InstrumentationRabbitMessage.model_construct(
        metrics="service_started",
        user_id=user_id,
        project_id=task.project_id,
        node_id=task.node_id,
        service_uuid=task.node_id,
        service_type=task.node_class.value,
        service_key=task.image.name,
        service_tag=task.image.tag,
        simcore_user_agent=simcore_user_agent,
    )
    await rabbitmq_client.publish(message.channel_name, message)


async def publish_service_stopped_metrics(
    rabbitmq_client: RabbitMQClient,
    *,
    user_id: UserID,
    simcore_user_agent: str,
    task: CompTaskAtDB,
    task_final_state: RunningState,
) -> None:
    message = InstrumentationRabbitMessage.model_construct(
        metrics="service_stopped",
        user_id=user_id,
        project_id=task.project_id,
        node_id=task.node_id,
        service_uuid=task.node_id,
        service_type=task.node_class.value,
        service_key=task.image.name,
        service_tag=task.image.tag,
        result=task_final_state,
        simcore_user_agent=simcore_user_agent,
    )
    await rabbitmq_client.publish(message.channel_name, message)


async def publish_service_resource_tracking_started(  # pylint: disable=too-many-arguments # noqa: PLR0913
    rabbitmq_client: RabbitMQClient,
    service_run_id: str,
    *,
    wallet_id: WalletID | None,
    wallet_name: str | None,
    pricing_plan_id: int | None,
    pricing_unit_id: int | None,
    pricing_unit_cost_id: int | None,
    product_name: str,
    simcore_user_agent: str,
    user_id: UserID,
    user_email: str,
    project_id: ProjectID,
    project_name: str,
    node_id: NodeID,
    node_name: str,
    parent_project_id: ProjectID | None,
    parent_node_id: NodeID | None,
    root_parent_project_id: ProjectID | None,
    root_parent_project_name: str | None,
    root_parent_node_id: NodeID | None,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    service_type: ServiceType,
    service_resources: ServiceResourcesDict,
    service_additional_metadata: dict[str, Any],
) -> None:
    message = RabbitResourceTrackingStartedMessage(
        service_run_id=service_run_id,
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        pricing_plan_id=pricing_plan_id,
        pricing_unit_id=pricing_unit_id,
        pricing_unit_cost_id=pricing_unit_cost_id,
        product_name=product_name,
        simcore_user_agent=simcore_user_agent,
        user_id=user_id,
        user_email=user_email,
        project_id=project_id,
        project_name=project_name,
        node_id=node_id,
        node_name=node_name,
        parent_project_id=parent_project_id or project_id,
        root_parent_project_id=root_parent_project_id or project_id,
        root_parent_project_name=root_parent_project_name or project_name,
        parent_node_id=parent_node_id or node_id,
        root_parent_node_id=root_parent_node_id or node_id,
        service_key=service_key,
        service_version=service_version,
        service_type=service_type,
        service_resources=service_resources,
        service_additional_metadata=service_additional_metadata,
    )
    await rabbitmq_client.publish(message.channel_name, message)


async def publish_service_resource_tracking_stopped(
    rabbitmq_client: RabbitMQClient,
    service_run_id: str,
    *,
    simcore_platform_status: SimcorePlatformStatus,
) -> None:
    message = RabbitResourceTrackingStoppedMessage(
        service_run_id=service_run_id, simcore_platform_status=simcore_platform_status
    )
    await rabbitmq_client.publish(message.channel_name, message)


async def publish_service_resource_tracking_heartbeat(
    rabbitmq_client: RabbitMQClient, service_run_id: str
) -> None:
    message = RabbitResourceTrackingHeartbeatMessage(service_run_id=service_run_id)
    await rabbitmq_client.publish(message.channel_name, message)


async def publish_service_log(
    rabbitmq_client: RabbitMQClient,
    *,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    log: str,
    log_level: LogLevelInt,
) -> None:
    message = LoggerRabbitMessage.model_construct(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        messages=[log],
        log_level=log_level,
    )

    await rabbitmq_client.publish(message.channel_name, message)


async def publish_service_progress(
    rabbitmq_client: RabbitMQClient,
    *,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    progress: NonNegativeFloat,
) -> None:
    message = ProgressRabbitMessageNode.model_construct(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        report=ProgressReport(actual_value=progress, total=1),
    )
    await rabbitmq_client.publish(message.channel_name, message)


async def publish_project_log(
    rabbitmq_client: RabbitMQClient,
    user_id: UserID,
    project_id: ProjectID,
    log: str,
    log_level: LogLevelInt,
) -> None:
    message = LoggerRabbitMessage.model_construct(
        user_id=user_id,
        project_id=project_id,
        node_id=None,
        messages=[log],
        log_level=log_level,
    )
    await rabbitmq_client.publish(message.channel_name, message)
