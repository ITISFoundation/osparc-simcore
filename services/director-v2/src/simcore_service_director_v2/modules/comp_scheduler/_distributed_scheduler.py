import datetime
import logging
from typing import Final

import networkx as nx
from aiopg.sa import Engine
from fastapi import FastAPI
from models_library.clusters import ClusterID
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.rabbitmq._client import RabbitMQClient
from servicelib.redis import RedisClientSDK
from servicelib.redis_utils import exclusive
from servicelib.utils import limited_gather
from settings_library.redis import RedisDatabase

from ...models.comp_runs import CompRunsAtDB, RunMetadataDict
from ...utils.comp_scheduler import SCHEDULED_STATES
from ...utils.rabbitmq import publish_project_log
from ..comp_scheduler._models import SchedulePipelineRabbitMessage
from ..db import get_db_engine
from ..db.repositories.comp_pipelines import CompPipelinesRepository
from ..db.repositories.comp_runs import CompRunsRepository
from ..rabbitmq import get_rabbitmq_client
from ..redis import get_redis_client_manager

_logger = logging.getLogger(__name__)
_SCHEDULER_INTERVAL: Final[datetime.timedelta] = datetime.timedelta(seconds=5)
_MAX_CONCURRENT_PIPELINE_SCHEDULING: Final[int] = 10


async def run_new_pipeline(
    app: FastAPI,
    *,
    user_id: UserID,
    project_id: ProjectID,
    cluster_id: ClusterID,
    run_metadata: RunMetadataDict,
    use_on_demand_clusters: bool,
) -> None:
    """Sets a new pipeline to be scheduled on the computational resources.
    Passing cluster_id=0 will use the default cluster. Passing an existing ID will instruct
    the scheduler to run the tasks on the defined cluster"""
    # ensure the pipeline exists and is populated with something
    db_engine = get_db_engine(app)
    dag = await _get_pipeline_dag(project_id, db_engine)
    if not dag:
        _logger.warning(
            "project %s has no computational dag defined. not scheduled for a run.",
            f"{project_id=}",
        )
        return

    new_run = await CompRunsRepository.instance(db_engine).create(
        user_id=user_id,
        project_id=project_id,
        cluster_id=cluster_id,
        metadata=run_metadata,
        use_on_demand_clusters=use_on_demand_clusters,
    )

    rabbitmq_client = get_rabbitmq_client(app)
    await _distribute_pipeline(new_run, rabbitmq_client, db_engine)
    await publish_project_log(
        rabbitmq_client,
        user_id,
        project_id,
        log=f"Project pipeline scheduled using {'on-demand clusters' if use_on_demand_clusters else 'pre-defined clusters'}, starting soon...",
        log_level=logging.INFO,
    )


async def stop_pipeline(
    app: FastAPI,
    *,
    user_id: UserID,
    project_id: ProjectID,
    iteration: int | None = None,
) -> None:
    db_engine = get_db_engine(app)
    comp_run = await CompRunsRepository.instance(db_engine).get(
        user_id, project_id, iteration
    )

    # mark the scheduled pipeline for stopping
    updated_comp_run = await CompRunsRepository.instance(
        db_engine
    ).mark_for_cancellation(
        user_id=user_id, project_id=project_id, iteration=comp_run.iteration
    )
    if updated_comp_run:
        # ensure the scheduler starts right away
        rabbitmq_client = get_rabbitmq_client(app)
        await _distribute_pipeline(updated_comp_run, rabbitmq_client, db_engine)


def _redis_client_getter(*args, **kwargs) -> RedisClientSDK:
    assert kwargs is not None  # nosec
    app = args[0]
    assert isinstance(app, FastAPI)  # nosec
    return get_redis_client_manager(app).client(RedisDatabase.LOCKS)


async def _distribute_pipeline(
    run: CompRunsAtDB, rabbitmq_client: RabbitMQClient, db_engine: Engine
) -> None:
    # TODO: we should use the transaction and the asyncpg engine here to ensure 100% consistency
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


async def _get_pipeline_dag(project_id: ProjectID, db_engine: Engine) -> nx.DiGraph:
    comp_pipeline_repo = CompPipelinesRepository.instance(db_engine)
    pipeline_at_db = await comp_pipeline_repo.get_pipeline(project_id)
    return pipeline_at_db.get_graph()


@exclusive(_redis_client_getter, lock_key="computational-distributed-scheduler")
async def schedule_pipelines(app: FastAPI) -> None:
    db_engine = get_db_engine(app)
    runs_to_schedule = await CompRunsRepository.instance(db_engine).list(
        filter_by_state=SCHEDULED_STATES, scheduled_since=_SCHEDULER_INTERVAL
    )
    rabbitmq_client = get_rabbitmq_client(app)
    await limited_gather(
        *(
            _distribute_pipeline(run, rabbitmq_client, db_engine)
            for run in runs_to_schedule
        ),
        limit=_MAX_CONCURRENT_PIPELINE_SCHEDULING,
    )
