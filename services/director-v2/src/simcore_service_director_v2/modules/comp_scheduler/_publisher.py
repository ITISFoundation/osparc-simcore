from dask_task_models_library.models import DaskJobID
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.rabbitmq import RabbitMQClient
from sqlalchemy.ext.asyncio import AsyncEngine

from ...models.comp_runs import Iteration, RunID, RunMetadataDict
from ..db.repositories.comp_runs import CompRunsRepository
from ._models import ReleaseTaskResultRabbitMessage, SchedulePipelineRabbitMessage


async def request_pipeline_scheduling(
    rabbitmq_client: RabbitMQClient,
    db_engine: AsyncEngine,
    *,
    user_id: UserID,
    project_id: ProjectID,
    iteration: Iteration,
) -> None:
    # NOTE: it is important that the DB is set up first before scheduling, in case the worker already schedules before we change the DB
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


async def request_task_result_release(
    rabbitmq_client: RabbitMQClient,
    *,
    user_id: UserID,
    project_id: ProjectID,
    run_id: RunID,
    use_on_demand_clusters: bool,
    run_metadata: RunMetadataDict,
    job_ids: list[DaskJobID],
) -> None:
    await rabbitmq_client.publish(
        ReleaseTaskResultRabbitMessage.get_channel_name(),
        ReleaseTaskResultRabbitMessage(
            user_id=user_id,
            project_id=project_id,
            run_id=run_id,
            use_on_demand_clusters=use_on_demand_clusters,
            run_metadata=run_metadata,
            job_ids=job_ids,
        ),
    )
