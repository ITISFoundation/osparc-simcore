from aiopg.sa import Engine
from servicelib.rabbitmq import RabbitMQClient

from ...models.comp_runs import CompRunsAtDB
from ..db.repositories.comp_runs import CompRunsRepository
from ._models import SchedulePipelineRabbitMessage


async def request_pipeline_scheduling(
    run: CompRunsAtDB, rabbitmq_client: RabbitMQClient, db_engine: Engine
) -> None:
    # NOTE: we should use the transaction and the asyncpg engine here to ensure 100% consistency
    # https://github.com/ITISFoundation/osparc-simcore/issues/6818
    # async with transaction_context(get_asyncpg_engine(app)) as connection:
    await rabbitmq_client.publish(
        SchedulePipelineRabbitMessage.get_channel_name(),
        SchedulePipelineRabbitMessage(
            user_id=run.user_id,
            project_id=run.project_uuid,
            iteration=run.iteration,
        ),
    )
    await CompRunsRepository.instance(db_engine).mark_as_scheduled(
        user_id=run.user_id, project_id=run.project_uuid, iteration=run.iteration
    )
