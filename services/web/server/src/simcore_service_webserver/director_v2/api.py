""" plugin API

PLEASE avoid importing from any other module to access this plugin's functionality
"""

from ._abc import (
    AbstractProjectRunPolicy,
    get_project_run_policy,
    set_project_run_policy,
)
from ._core_computations import (
    create_or_update_pipeline,
    delete_pipeline,
    get_batch_tasks_outputs,
    get_computation_task,
    is_pipeline_running,
    stop_pipeline,
)
from ._core_utils import is_healthy
from .exceptions import DirectorServiceError

# director-v2 module internal API
__all__: tuple[str, ...] = (
    "AbstractProjectRunPolicy",
    "create_or_update_pipeline",
    "delete_pipeline",
    "DirectorServiceError",
    "get_batch_tasks_outputs",
    "get_computation_task",
    "get_project_run_policy",
    "is_healthy",
    "is_pipeline_running",
    "set_project_run_policy",
    "stop_pipeline",
)
# nopycln: file
