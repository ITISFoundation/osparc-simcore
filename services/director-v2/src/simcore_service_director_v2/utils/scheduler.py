from models_library.projects_state import RunningState
from pydantic import PositiveInt

SCHEDULED_STATES: set[RunningState] = {
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.STARTED,
    RunningState.RETRY,
}

WAITING_FOR_START_STATES: set[RunningState] = {
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.RETRY,
}

PROCESSING_STATES: set[RunningState] = {
    RunningState.PENDING,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.STARTED,
    RunningState.RETRY,
}

COMPLETED_STATES: set[RunningState] = {
    RunningState.ABORTED,
    RunningState.SUCCESS,
    RunningState.FAILED,
    RunningState.UNKNOWN,
}


Iteration = PositiveInt
