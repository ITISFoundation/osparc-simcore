import logging
from typing import Final

import networkx as nx
from aiopg.sa import Engine
from fastapi import FastAPI
from models_library.clusters import ClusterID
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.exception_utils import silence_exceptions
from servicelib.logging_utils import log_context
from servicelib.redis import CouldNotAcquireLockError
from servicelib.redis_utils import exclusive
from servicelib.utils import limited_gather

from ...models.comp_runs import RunMetadataDict
from ...utils.rabbitmq import publish_project_log
from ..db import get_db_engine
from ..db.repositories.comp_pipelines import CompPipelinesRepository
from ..db.repositories.comp_runs import CompRunsRepository
from ..rabbitmq import get_rabbitmq_client
from ._constants import (
    MAX_CONCURRENT_PIPELINE_SCHEDULING,
    MODULE_NAME_SCHEDULER,
    SCHEDULER_INTERVAL,
)
from ._publisher import request_pipeline_scheduling
from ._utils import SCHEDULED_STATES, get_redis_client_from_app, get_redis_lock_key

_logger = logging.getLogger(__name__)


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
    await request_pipeline_scheduling(
        rabbitmq_client,
        db_engine,
        user_id=new_run.user_id,
        project_id=new_run.project_uuid,
        iteration=new_run.iteration,
    )
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
        await request_pipeline_scheduling(
            rabbitmq_client,
            db_engine,
            user_id=updated_comp_run.user_id,
            project_id=updated_comp_run.project_uuid,
            iteration=updated_comp_run.iteration,
        )


async def _get_pipeline_dag(project_id: ProjectID, db_engine: Engine) -> nx.DiGraph:
    comp_pipeline_repo = CompPipelinesRepository.instance(db_engine)
    pipeline_at_db = await comp_pipeline_repo.get_pipeline(project_id)
    return pipeline_at_db.get_graph()


_LOST_TASKS_FACTOR: Final[int] = 10


@exclusive(
    get_redis_client_from_app,
    lock_key=get_redis_lock_key(MODULE_NAME_SCHEDULER, unique_lock_key_builder=None),
)
async def schedule_all_pipelines(app: FastAPI) -> None:
    with log_context(_logger, logging.DEBUG, msg="scheduling pipelines"):
        db_engine = get_db_engine(app)
        runs_to_schedule = await CompRunsRepository.instance(db_engine).list(
            filter_by_state=SCHEDULED_STATES,
            never_scheduled=True,
            processed_since=SCHEDULER_INTERVAL,
        )
        possibly_lost_scheduled_pipelines = await CompRunsRepository.instance(
            db_engine
        ).list(
            filter_by_state=SCHEDULED_STATES,
            scheduled_since=SCHEDULER_INTERVAL * _LOST_TASKS_FACTOR,
        )
        if possibly_lost_scheduled_pipelines:
            _logger.error(
                "found %d lost pipelines, they will be re-scheduled now",
                len(possibly_lost_scheduled_pipelines),
            )

        rabbitmq_client = get_rabbitmq_client(app)
        with log_context(_logger, logging.DEBUG, msg="distributing pipelines"):
            await limited_gather(
                *(
                    request_pipeline_scheduling(
                        rabbitmq_client,
                        db_engine,
                        user_id=run.user_id,
                        project_id=run.project_uuid,
                        iteration=run.iteration,
                    )
                    for run in runs_to_schedule + possibly_lost_scheduled_pipelines
                ),
                limit=MAX_CONCURRENT_PIPELINE_SCHEDULING,
            )
        if runs_to_schedule:
            _logger.debug("distributed %d pipelines", len(runs_to_schedule))


async def setup_manager(app: FastAPI) -> None:
    app.state.scheduler_manager = start_periodic_task(
        silence_exceptions((CouldNotAcquireLockError,))(schedule_all_pipelines),
        interval=SCHEDULER_INTERVAL,
        task_name=MODULE_NAME_SCHEDULER,
        app=app,
    )


async def shutdown_manager(app: FastAPI) -> None:
    await stop_periodic_task(app.state.scheduler_manager)
