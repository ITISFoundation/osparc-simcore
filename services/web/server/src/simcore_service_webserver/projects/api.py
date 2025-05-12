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
from ._projects_service import delete_project_by_user, get_project_dict_legacy

__all__: tuple[str, ...] = (
    "check_user_project_permission",
    "create_project_group_without_checking_permissions",
    "delete_project_group_without_checking_permissions",
    "get_project_dict_legacy",
    "has_user_project_access_rights",
    "list_projects",
    "delete_project_by_user",
)


# nopycln: file
