from typing import Any, TypeAlias

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import (
    InstrumentationRabbitMessage,
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStartedMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from models_library.services import ServiceKey, ServiceType, ServiceVersion
from models_library.services_resources import ServiceResourcesDict
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq import RabbitMQClient
from simcore_postgres_database.models.comp_tasks import NodeClass

from ..models.comp_tasks import CompTaskAtDB
from .scheduler import COMPLETED_STATES, WAITING_FOR_START_STATES

TaskBefore: TypeAlias = CompTaskAtDB
TaskCurrent: TypeAlias = CompTaskAtDB


async def publish_service_started_metrics(
    rabbitmq_client: RabbitMQClient,
    user_id: UserID,
    project_id: ProjectID,
    simcore_user_agent: str,
    changed_tasks: list[tuple[TaskBefore, TaskCurrent]],
) -> None:
    for previous, current in changed_tasks:
        if current.state is RunningState.STARTED or (
            previous.state in WAITING_FOR_START_STATES
            and current.state in COMPLETED_STATES
        ):
            message = InstrumentationRabbitMessage.construct(
                metrics="service_started",
                user_id=user_id,
                project_id=project_id,
                node_id=current.node_id,
                service_uuid=current.node_id,
                service_type=NodeClass.COMPUTATIONAL.value,
                service_key=current.image.name,
                service_tag=current.image.tag,
                simcore_user_agent=simcore_user_agent,
            )
            await rabbitmq_client.publish(message.channel_name, message)


async def publish_service_stopped_metrics(
    rabbitmq_client: RabbitMQClient,
    user_id: UserID,
    simcore_user_agent: str,
    task: CompTaskAtDB,
    task_final_state: RunningState,
) -> None:
    message = InstrumentationRabbitMessage.construct(
        metrics="service_stopped",
        user_id=user_id,
        project_id=task.project_id,
        node_id=task.node_id,
        service_uuid=task.node_id,
        service_type=NodeClass.COMPUTATIONAL.value,
        service_key=task.image.name,
        service_tag=task.image.tag,
        result=task_final_state,
        simcore_user_agent=simcore_user_agent,
    )
    await rabbitmq_client.publish(message.channel_name, message)


async def publish_service_resource_tracking_started(
    rabbitmq_client: RabbitMQClient,
    service_run_id: str,
    *,
    wallet_id: WalletID,
    wallet_name: str,
    product_name: str,
    simcore_user_agent: str,
    user_id: UserID,
    user_email: str,
    project_id: ProjectID,
    project_name: str,
    node_id: NodeID,
    node_name: str,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    service_type: ServiceType,
    service_resources: ServiceResourcesDict,
    service_additional_metadata: dict[str, Any]
) -> None:
    message = RabbitResourceTrackingStartedMessage(
        service_run_id=service_run_id,
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        product_name=product_name,
        simcore_user_agent=simcore_user_agent,
        user_id=user_id,
        user_email=user_email,
        project_id=project_id,
        project_name=project_name,
        node_id=node_id,
        node_name=node_name,
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
    simcore_platform_status: SimcorePlatformStatus
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
