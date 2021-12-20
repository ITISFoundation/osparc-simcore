import logging
import re
from typing import List, Set

from models_library.projects_state import RunningState
from models_library.services import SERVICE_KEY_RE

from ..models.domains.comp_tasks import CompTaskAtDB
from ..modules.db.tables import NodeClass

log = logging.getLogger(__file__)


def get_pipeline_state_from_task_states(tasks: List[CompTaskAtDB]) -> RunningState:

    # compute pipeline state from task states
    if tasks:
        # put in a set of unique values
        set_states: Set[RunningState] = {task.state for task in tasks}
        if len(set_states) == 1:
            # this is typically for success, pending, published
            the_state = next(iter(set_states))
            return the_state
        if set_states.issubset({RunningState.NOT_STARTED, RunningState.PUBLISHED}):
            return RunningState.PUBLISHED

        if set_states.issubset({RunningState.PENDING, RunningState.PUBLISHED}):
            # a pending pipeline has nodes either in PENDING or PUBLISHED state
            return RunningState.PENDING

        if set_states.issubset({RunningState.SUCCESS, RunningState.ABORTED}):
            # if only ABORTED and SUCCESS --> then it is aborted
            return RunningState.ABORTED

        if set_states.issubset(
            {RunningState.SUCCESS, RunningState.FAILED, RunningState.ABORTED}
        ):
            # if there are also failed state in there --> failed
            return RunningState.FAILED

        if set_states.issubset(
            {
                RunningState.PENDING,
                RunningState.PUBLISHED,
                RunningState.STARTED,
                RunningState.SUCCESS,
                RunningState.RETRY,
                RunningState.FAILED,
                RunningState.ABORTED,
            }
        ):
            # a running pipeline has typically any number of nodes
            # in STARTED, PENDING and PUBLISHED state
            return RunningState.STARTED

    return RunningState.NOT_STARTED


_node_key_re = re.compile(SERVICE_KEY_RE)
_STR_TO_NODECLASS = {
    "comp": NodeClass.COMPUTATIONAL,
    "dynamic": NodeClass.INTERACTIVE,
    "frontend": NodeClass.FRONTEND,
}


def to_node_class(service_key: str) -> NodeClass:
    match = _node_key_re.match(service_key)
    if match:
        node_class = _STR_TO_NODECLASS.get(match.group(3))
        if node_class:
            return node_class
    raise ValueError


def is_pipeline_running(pipeline_state: RunningState) -> bool:
    return pipeline_state in [
        RunningState.PUBLISHED,
        RunningState.PENDING,
        RunningState.STARTED,
        RunningState.RETRY,
    ]


def is_pipeline_stopped(pipeline_state: RunningState) -> bool:
    return not is_pipeline_running(pipeline_state)
