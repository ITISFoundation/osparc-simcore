from typing import TypeAlias

from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import InstrumentationRabbitMessage
from models_library.users import UserID
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
