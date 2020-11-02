import logging
import re
from typing import Dict

from models_library.projects import KEY_RE, NodeID, RunningState

from ..models.domains.comp_tasks import CompTaskAtDB
from ..modules.db.tables import NodeClass

log = logging.getLogger(__file__)


def get_pipeline_state_from_task_states(
    tasks: Dict[NodeID, CompTaskAtDB]
) -> RunningState:

    # compute pipeline state from task states
    # now = datetime.utcnow()
    if tasks:
        # put in a set of unique values
        set_states = {task.state for task in tasks.values()}
        # last_update = next(
        #     iter(sorted([task.submit for task in tasks.values()], reverse=True))
        # )
        # FIXME: this should be done automatically after the timeout!!
        # if RunningState.PUBLISHED in set_states:
        #     if (now - last_update).seconds > get_celery_publication_timeout(app):
        #         return RunningState.NOT_STARTED
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


_node_key_re = re.compile(KEY_RE)
_STR_TO_NODECLASS = {
    "comp": NodeClass.COMPUTATIONAL,
    "dynamic": NodeClass.INTERACTIVE,
    "frontend": NodeClass.FRONTEND,
}


def to_node_class(service_key: str) -> NodeClass:
    match = _node_key_re.match(service_key)
    if match:
        return _STR_TO_NODECLASS.get(match.group(3))
    raise ValueError
