# NOTE: we will slowly move heere projects_api.py


from ._access_rights_service import (
    check_user_project_permission,
    has_user_project_access_rights,
)
from ._crud_api_read import list_projects
from ._groups_service import (
    create_project_group_without_checking_permissions,
    delete_project_group_without_checking_permissions,
)
from ._projects_service import (
    batch_get_project_name,
    clone_project_data,
    copy_allow_guests_to_push_states_and_output_ports,
    get_project_dict_and_type,
    get_project_dict_legacy,
    patch_project_and_notify_users,
)

__all__: tuple[str, ...] = (
    "batch_get_project_name",
    "check_user_project_permission",
    "clone_project_data",
    "copy_allow_guests_to_push_states_and_output_ports",
    "create_project_group_without_checking_permissions",
    "delete_project_group_without_checking_permissions",
    "get_project_dict_and_type",
    "get_project_dict_legacy",
    "has_user_project_access_rights",
    "list_projects",
    "patch_project_and_notify_users",
)  # nopycln: file
