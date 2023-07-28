""" API of computation subsystem within this application

"""

from models_library.projects_state import RunningState
from simcore_postgres_database.models.comp_pipeline import StateType

#
# API ------------------------------------------
#


DB_TO_RUNNING_STATE = {
    StateType.FAILED: RunningState.FAILED,
    StateType.PENDING: RunningState.PENDING,
    StateType.SUCCESS: RunningState.SUCCESS,
    StateType.PUBLISHED: RunningState.PUBLISHED,
    StateType.NOT_STARTED: RunningState.NOT_STARTED,
    StateType.RUNNING: RunningState.STARTED,
    StateType.ABORTED: RunningState.ABORTED,
    StateType.WAITING_FOR_RESOURCES: RunningState.WAITING_FOR_RESOURCES,
}


def convert_state_from_db(db_state: StateType) -> RunningState:
    return RunningState(DB_TO_RUNNING_STATE[StateType(db_state)])
