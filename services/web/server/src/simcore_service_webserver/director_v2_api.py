""" plugin API

PLEASE avoid importing from any other module to access this plugin's functionality
"""

from typing import Tuple

from .director_v2_abc import (
    AbstractProjectRunPolicy,
    get_project_run_policy,
    set_project_run_policy,
)
from .director_v2_core import (
    DirectorServiceError,
    create_or_update_pipeline,
    delete_pipeline,
    get_computation_task,
    get_dynamic_service_state,
    get_dynamic_services,
    is_healthy,
    is_pipeline_running,
    request_retrieve_dyn_service,
    restart,
    retrieve,
    start_dynamic_service,
    stop_dynamic_service,
    stop_dynamic_services_in_project,
)

# director-v2 module internal API
__all__: Tuple[str, ...] = (
    "AbstractProjectRunPolicy",
    "create_or_update_pipeline",
    "delete_pipeline",
    "DirectorServiceError",
    "get_computation_task",
    "get_project_run_policy",
    "get_dynamic_service_state",
    "get_dynamic_services",
    "is_healthy",
    "is_pipeline_running",
    "request_retrieve_dyn_service",
    "restart",
    "retrieve",
    "set_project_run_policy",
    "start_dynamic_service",
    "stop_dynamic_service",
    "stop_dynamic_services_in_project",
)
