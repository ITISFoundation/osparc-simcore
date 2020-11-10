""" API of computation subsystem within this application

"""
# pylint: disable=too-many-arguments
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa import Engine
from celery import Celery
from celery.contrib.abortable import AbortableAsyncResult
from sqlalchemy import and_

from models_library.projects import RunningState
from servicelib.application_keys import APP_DB_ENGINE_KEY
from servicelib.logging_utils import log_decorator
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.webserver_models import (
    NodeClass,
    comp_pipeline,
    comp_tasks,
)


from .computation_config import ComputationSettings
from .computation_config import get_settings as get_computation_settings
from .director import director_api

log = logging.getLogger(__file__)


#
# API ------------------------------------------
#


def get_celery(app: web.Application) -> Celery:
    comp_settings: ComputationSettings = get_computation_settings(app)
    celery_app = Celery(
        comp_settings.task_name,
        broker=comp_settings.broker_url,
        backend=comp_settings.result_backend,
    )
    return celery_app


def get_celery_publication_timeout(app: web.Application) -> int:
    comp_settings: ComputationSettings = get_computation_settings(app)
    return comp_settings.publication_timeout


DB_TO_RUNNING_STATE = {
    StateType.FAILED: RunningState.FAILED,
    StateType.PENDING: RunningState.PENDING,
    StateType.SUCCESS: RunningState.SUCCESS,
    StateType.PUBLISHED: RunningState.PUBLISHED,
    StateType.NOT_STARTED: RunningState.NOT_STARTED,
    StateType.RUNNING: RunningState.STARTED,
    StateType.ABORTED: RunningState.ABORTED,
}


@log_decorator(logger=log)
def convert_state_from_db(db_state: StateType) -> RunningState:
    return RunningState(DB_TO_RUNNING_STATE[StateType(db_state)])


@log_decorator(logger=log)
async def get_task_states(
    app: web.Application, project_id: str
) -> Dict[str, Tuple[RunningState, datetime]]:
    db_engine = app[APP_DB_ENGINE_KEY]
    task_states: Dict[str, RunningState] = {}
    async with db_engine.acquire() as conn:
        async for row in conn.execute(
            sa.select([comp_tasks]).where(comp_tasks.c.project_id == project_id)
        ):
            if row.node_class != NodeClass.COMPUTATIONAL:
                continue
            task_states[row.node_id] = (convert_state_from_db(row.state), row.submit)
    return task_states


@log_decorator(logger=log)
async def get_pipeline_state(app: web.Application, project_id: str) -> RunningState:
    task_states: Dict[str, Tuple[RunningState, datetime]] = await get_task_states(
        app, project_id
    )
    # compute pipeline state from task states
    now = datetime.utcnow()
    if task_states:
        # put in a set of unique values
        set_states = {state[0] for state in task_states.values()}
        last_update = next(
            iter(sorted([time[1] for time in task_states.values()], reverse=True))
        )
        if RunningState.PUBLISHED in set_states:
            if (now - last_update).seconds > get_celery_publication_timeout(app):
                return RunningState.NOT_STARTED
        if len(set_states) == 1:
            # this is typically for success, pending, published
            return next(iter(set_states))

        for state in [
            RunningState.FAILED,  # task is failed -> pipeline as well
            RunningState.PUBLISHED,  # still in publishing phase
            RunningState.STARTED,  # task is started or retrying
            RunningState.PENDING,  # still running
        ]:
            if state in set_states:
                return state

    return RunningState.NOT_STARTED


@log_decorator(logger=log)
async def delete_pipeline_db(app: web.Application, project_id: str) -> None:
    db_engine = app[APP_DB_ENGINE_KEY]

    async with db_engine.acquire() as conn:
        # pylint: disable=no-value-for-parameter
        query = comp_tasks.delete().where(comp_tasks.c.project_id == project_id)
        await conn.execute(query)
        query = comp_pipeline.delete().where(comp_pipeline.c.project_id == project_id)
        await conn.execute(query)


@log_decorator(logger=log)
async def get_task_output(
    app: web.Application, project_id: str, node_id: str
) -> Optional[Dict]:
    db_engine = app[APP_DB_ENGINE_KEY]
    async with db_engine.acquire() as conn:
        query = sa.select([comp_tasks]).where(
            and_(comp_tasks.c.project_id == project_id, comp_tasks.c.node_id == node_id)
        )
        result = await conn.execute(query)
        comp_task = await result.fetchone()
        if comp_task:
            return comp_task.outputs
