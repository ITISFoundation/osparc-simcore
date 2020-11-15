""" API of computation subsystem within this application

"""
# pylint: disable=too-many-arguments
import logging

from aiohttp import web
from celery import Celery

from models_library.projects import RunningState
from servicelib.logging_utils import log_decorator
from simcore_postgres_database.models.comp_pipeline import StateType


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
