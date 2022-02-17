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
    attach_network_to_dynamic_sidecar,
    create_or_update_pipeline,
    delete_pipeline,
    detach_network_from_dynamic_sidecar,
    DirectorServiceError,
    get_computation_task,
    get_service_state,
    get_services,
    is_healthy,
    request_retrieve_dyn_service,
    requires_dynamic_sidecar,
    restart,
    retrieve,
    start_service,
    stop_service,
    stop_services,
)

# director-v2 module internal API
__all__: Tuple[str, ...] = (
    "AbstractProjectRunPolicy",
    "attach_network_to_dynamic_sidecar",
    "create_or_update_pipeline",
    "delete_pipeline",
    "detach_network_from_dynamic_sidecar",
    "DirectorServiceError",
    "get_computation_task",
    "get_project_run_policy",
    "get_service_state",
    "get_services",
    "is_healthy",
    "request_retrieve_dyn_service",
    "requires_dynamic_sidecar",
    "restart",
    "retrieve",
    "set_project_run_policy",
    "start_service",
    "stop_service",
    "stop_services",
)
