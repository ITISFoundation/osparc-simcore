from ._client import setup as client_setup
from ._server import setup as server_setup
from ._decorators import mark_long_running_task
from ._context_manager import task_result
from ._task import start_task, TaskManager
from ._dependencies import get_task_manager
from ._models import TaskId, ProgressHandler, TaskStatus
from ._errors import TaskClientResultErrorError, TaskClientTimeoutError

# TODO: cleanup this, too much exposed
__all__: tuple[str, ...] = (
    "client_setup",
    "get_task_manager",
    "mark_long_running_task",
    "ProgressHandler",
    "server_setup",
    "start_task",
    "task_result",
    "TaskClientResultErrorError",
    "TaskClientTimeoutError",
    "TaskId",
    "TaskManager",
    "TaskStatus",
)
