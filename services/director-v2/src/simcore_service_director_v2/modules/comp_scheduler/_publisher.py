from aiopg.sa import Engine
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.rabbitmq import RabbitMQClient

from ...models.comp_runs import Iteration
from ..db.repositories.comp_runs import CompRunsRepository
from ._models import SchedulePipelineRabbitMessage


async def request_pipeline_scheduling(
    rabbitmq_client: RabbitMQClient,
    db_engine: Engine,
    *,
    user_id: UserID,
    project_id: ProjectID,
    iteration: Iteration
) -> None:
    # NOTE: we should use the transaction and the asyncpg engine here to ensure 100% consistency
    # https://github.com/ITISFoundation/osparc-simcore/issues/6818
    # async with transaction_context(get_asyncpg_engine(app)) as connection:
    await rabbitmq_client.publish(
        SchedulePipelineRabbitMessage.get_channel_name(),
        SchedulePipelineRabbitMessage(
            user_id=user_id,
            project_id=project_id,
            iteration=iteration,
        ),
    )
    await CompRunsRepository.instance(db_engine).mark_for_scheduling(
        user_id=user_id, project_id=project_id, iteration=iteration
    )
