""" Interface to other subsystems

    - Data validation
    - Operations on projects
        - are NOT handlers, therefore do not return web.Response
        - return data and successful HTTP responses (or raise them)
        - upon failure raise errors that can be also HTTP reponses
"""

from typing import Tuple

from ._core_delete import delete_project
from ._core_get import get_project_for_user, validate_project
from ._core_nodes import (
    get_workbench_node_ids_from_project_uuid,
    is_node_id_present_in_any_project_workbench,
    notify_project_node_update,
    post_trigger_connected_service_retrieve,
    update_project_node_outputs,
    update_project_node_progress,
    update_project_node_state,
)
from ._core_notify import (
    notify_project_state_update,
    retrieve_and_notify_project_locked_state,
)
from ._core_services import remove_project_dynamic_services

__all__: Tuple[str, ...] = (
    "get_project_for_user",
    "remove_project_dynamic_services",
    "retrieve_and_notify_project_locked_state",
    "validate_project",
    "notify_project_state_update",
    "update_project_node_outputs",
    "post_trigger_connected_service_retrieve",
    "update_project_node_progress",
    "delete_project",
    "get_workbench_node_ids_from_project_uuid",
    "is_node_id_present_in_any_project_workbench",
    "update_project_node_state",
    "notify_project_node_update",
)
