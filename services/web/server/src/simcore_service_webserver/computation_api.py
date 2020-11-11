""" API of computation subsystem within this application

"""
# pylint: disable=too-many-arguments
import logging
from typing import Dict, Optional

import sqlalchemy as sa
from aiohttp import web
from celery import Celery
from sqlalchemy import and_

from models_library.projects import RunningState
from servicelib.application_keys import APP_DB_ENGINE_KEY
from servicelib.logging_utils import log_decorator
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.webserver_models import (
    comp_pipeline,
    comp_tasks,
)


from .computation_config import ComputationSettings
from .computation_config import get_settings as get_computation_settings

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
