#
# Domain-Specific Interfaces
#
from ._groups_service import (
    add_user_in_group,
    auto_add_user_to_groups,
    auto_add_user_to_product_group,
    get_group_from_gid,
    get_product_group_for_user,
    is_user_by_email_in_group,
    list_all_user_groups_ids,
    list_group_members,
    list_user_groups_ids_with_read_access,
    list_user_groups_with_read_access,
)

__all__: tuple[str, ...] = (
    "add_user_in_group",
    "auto_add_user_to_groups",
    "auto_add_user_to_product_group",
    "get_group_from_gid",
    "get_product_group_for_user",
    "is_user_by_email_in_group",
    "list_all_user_groups_ids",
    "list_user_groups_ids_with_read_access",
    "list_user_groups_with_read_access",
    "list_group_members",
    # nopycln: file
)
