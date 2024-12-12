# mypy: disable-error-code=truthy-function

from ._common.models import FullNameDict
from ._users_service import (
    delete_user_without_projects,
    get_guest_user_ids_and_names,
    get_user,
    get_user_credentials,
    get_user_display_and_id_names,
    get_user_fullname,
    get_user_id_from_gid,
    get_user_invoice_address,
    get_user_name_and_email,
    get_user_profile,
    get_user_role,
    get_users_in_group,
    set_user_as_deleted,
    update_expired_users,
    update_user_profile,
)

# from . import _users_service
# delete_user_without_projects = _users_service.delete_user_without_projects
# get_guest_user_ids_and_names = _users_service.get_guest_user_ids_and_names
# get_user = _users_service.get_user
# get_user_credentials = _users_service.get_user_credentials
# get_user_display_and_id_names = _users_service.get_user_display_and_id_names
# get_user_fullname = _users_service.get_user_fullname
# get_user_id_from_gid = _users_service.get_user_id_from_gid
# get_user_invoice_address = _users_service.get_user_invoice_address
# get_user_name_and_email = _users_service.get_user_name_and_email
# get_user_profile = _users_service.get_user_profile
# get_user_role = _users_service.get_user_role
# get_users_in_group = _users_service.get_users_in_group
# set_user_as_deleted = _users_service.set_user_as_deleted
# update_expired_users = _users_service.update_expired_users
# update_user_profile = _users_service.update_user_profile


__all__: tuple[str, ...] = (
    "delete_user_without_projects",
    "get_guest_user_ids_and_names",
    "get_user",
    "get_user_credentials",
    "get_user_display_and_id_names",
    "get_user_fullname",
    "get_user_id_from_gid",
    "get_user_invoice_address",
    "get_user_name_and_email",
    "get_user_profile",
    "get_user_role",
    "get_users_in_group",
    "set_user_as_deleted",
    "update_expired_users",
    "update_user_profile",
    "FullNameDict",
)
# nopycln: file
