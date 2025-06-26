from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.rabbitmq import RabbitMQClient
from sqlalchemy.ext.asyncio import AsyncEngine

from ...models.comp_runs import Iteration
from ..db.repositories.comp_runs import CompRunsRepository
from ._models import SchedulePipelineRabbitMessage


async def request_pipeline_scheduling(
    rabbitmq_client: RabbitMQClient,
    db_engine: AsyncEngine,
    *,
    user_id: UserID,
    project_id: ProjectID,
    iteration: Iteration,
) -> None:
    await CompRunsRepository.instance(db_engine).mark_for_scheduling(
        user_id=user_id, project_id=project_id, iteration=iteration
    )
    await rabbitmq_client.publish(
        SchedulePipelineRabbitMessage.get_channel_name(),
        SchedulePipelineRabbitMessage(
            user_id=user_id,
            project_id=project_id,
            iteration=iteration,
        ),
    )
