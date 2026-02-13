from contextlib import suppress

from aiohttp import web
from models_library.emails import LowerCaseEmailStr
from models_library.groups import (
    AccessRightsDict,
    Group,
    GroupID,
    GroupMember,
    GroupsByTypeTuple,
    StandardGroupCreate,
    StandardGroupUpdate,
)
from models_library.products import ProductName
from models_library.users import UserID, UserNameID
from pydantic import EmailStr

from ..products.models import Product
from . import _groups_repository
from .exceptions import GroupNotFoundError, GroupsError

#
# GROUPS
#


async def get_group_by_gid(app: web.Application, group_id: GroupID) -> Group | None:
    group_db = await _groups_repository.get_group_by_gid(app, group_id=group_id)

    if group_db:
        return Group.model_construct(**group_db.model_dump())
    return None


#
# USER GROUPS: groups a user belongs to
#


async def list_user_groups_with_read_access(app: web.Application, *, user_id: UserID) -> GroupsByTypeTuple:
    """
    Returns the user primary group, standard groups and the all group
    """
    # NOTE: Careful! It seems we are filtering out groups, such as Product Groups,
    # because they do not have read access. I believe this was done because the
    # frontend did not want to display them.
    return await _groups_repository.get_all_user_groups_with_read_access(app, user_id=user_id)


async def list_user_groups_ids_with_read_access(app: web.Application, *, user_id: UserID) -> list[GroupID]:
    return await _groups_repository.get_ids_of_all_user_groups_with_read_access(app, user_id=user_id)


async def list_all_user_groups_ids(app: web.Application, *, user_id: UserID) -> list[GroupID]:
    return await _groups_repository.get_ids_of_all_user_groups(app, user_id=user_id)


async def get_product_group_for_user(
    app: web.Application, *, user_id: UserID, product_gid: GroupID
) -> tuple[Group, AccessRightsDict]:
    """
    Returns product's group if user belongs to it, otherwise it
    raises GroupNotFoundError
    """
    return await _groups_repository.get_any_group_for_user(app, user_id=user_id, group_gid=product_gid)


async def get_user_profile_groups(
    app: web.Application, *, user_id: UserID, product: Product
) -> tuple[
    GroupsByTypeTuple,
    tuple[Group, AccessRightsDict] | None,
    Group | None,
    Group | None,
]:
    """
    Get all groups needed for user profile including standard groups,
    product group, and support group.

    Returns:
        Tuple of (groups_by_type, my_product_group, product_support_group)
    """
    groups_by_type = await list_user_groups_with_read_access(app, user_id=user_id)

    my_product_group = None
    if product.group_id:  # Product group is optional
        with suppress(GroupNotFoundError):
            my_product_group = await get_product_group_for_user(
                app=app,
                user_id=user_id,
                product_gid=product.group_id,
            )

    product_support_group = None
    if product.support_standard_group_id:  # Support group is optional
        # NOTE: my_support_group can be part of groups_by_type.standard!
        product_support_group = await get_group_by_gid(app, product.support_standard_group_id)

    product_chatbot_primary_group = None
    if product.support_chatbot_user_id:
        from ..users import _users_service  # noqa: PLC0415

        group_id = await _users_service.get_user_primary_group_id(app, user_id=product.support_chatbot_user_id)
        product_chatbot_primary_group = await get_group_by_gid(app, group_id)

    return (
        groups_by_type,
        my_product_group,
        product_support_group,
        product_chatbot_primary_group,
    )


#
# CRUD operations on groups linked to a user
#


async def create_standard_group(
    app: web.Application,
    *,
    user_id: UserID,
    create: StandardGroupCreate,
) -> tuple[Group, AccessRightsDict]:
    """NOTE: creation/update and deletion restricted to STANDARD groups

    raises GroupNotFoundError
    raises UserInsufficientRightsError: needs WRITE access
    """
    return await _groups_repository.create_standard_group(
        app,
        user_id=user_id,
        create=create,
    )


async def get_associated_group(
    app: web.Application,
    *,
    user_id: UserID,
    group_id: GroupID,
) -> tuple[Group, AccessRightsDict]:
    """NOTE: here it can also be a non-standard group

    raises GroupNotFoundError
    raises UserInsufficientRightsError: needs READ access
    """
    return await _groups_repository.get_user_group(app, user_id=user_id, group_id=group_id)


async def update_standard_group(
    app: web.Application,
    *,
    user_id: UserID,
    group_id: GroupID,
    update: StandardGroupUpdate,
) -> tuple[Group, AccessRightsDict]:
    """NOTE: creation/update and deletion restricted to STANDARD groups

    raises GroupNotFoundError
    raises UserInsufficientRightsError: needs WRITE access
    """

    return await _groups_repository.update_standard_group(
        app,
        user_id=user_id,
        group_id=group_id,
        update=update,
    )


async def delete_standard_group(app: web.Application, *, user_id: UserID, group_id: GroupID) -> None:
    """NOTE: creation/update and deletion restricted to STANDARD groups

    raises GroupNotFoundError
    raises UserInsufficientRightsError: needs DELETE access
    """
    return await _groups_repository.delete_standard_group(app, user_id=user_id, group_id=group_id)


#
# GROUP MEMBERS (= a user with some access-rights to a group)
#


async def list_group_members_with_caller_check(
    app: web.Application, user_id: UserID, group_id: GroupID
) -> list[GroupMember]:
    return await _groups_repository.list_users_in_group_with_caller_check(
        app, caller_user_id=user_id, group_id=group_id
    )


async def list_group_members(app: web.Application, group_id: GroupID) -> list[GroupMember]:
    return await _groups_repository.list_users_in_group(app, group_id=group_id)


async def get_group_member(
    app: web.Application,
    user_id: UserID,
    group_id: GroupID,
    the_user_id_in_group: UserID,
) -> GroupMember:
    return await _groups_repository.get_user_in_group(
        app,
        caller_id=user_id,
        group_id=group_id,
        the_user_id_in_group=the_user_id_in_group,
    )


async def update_group_member(
    app: web.Application,
    user_id: UserID,
    group_id: GroupID,
    the_user_id_in_group: UserID,
    access_rights: AccessRightsDict,
) -> GroupMember:
    return await _groups_repository.update_user_in_group(
        app,
        caller_id=user_id,
        group_id=group_id,
        the_user_id_in_group=the_user_id_in_group,
        access_rights=access_rights,
    )


async def delete_group_member(
    app: web.Application,
    user_id: UserID,
    group_id: GroupID,
    the_user_id_in_group: UserID,
) -> None:
    return await _groups_repository.delete_user_from_group(
        app,
        caller_id=user_id,
        group_id=group_id,
        the_user_id_in_group=the_user_id_in_group,
    )


async def is_user_by_email_in_group(app: web.Application, user_email: LowerCaseEmailStr, group_id: GroupID) -> bool:
    return await _groups_repository.is_user_by_email_in_group(
        app,
        email=user_email,
        group_id=group_id,
    )


async def is_user_in_group(app: web.Application, *, user_id: UserID, group_id: GroupID) -> bool:
    return await _groups_repository.is_user_in_group(app, user_id=user_id, group_id=group_id)


async def auto_add_user_to_groups(app: web.Application, user_id: UserID) -> None:
    from ..users import _users_service  # noqa: PLC0415

    user: dict = await _users_service.get_user(app, user_id)
    return await _groups_repository.auto_add_user_to_groups(app, user=user)


async def auto_add_user_to_product_group(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
) -> GroupID:
    return await _groups_repository.auto_add_user_to_product_group(app, user_id=user_id, product_name=product_name)


def _only_one_true(*args):
    return sum(bool(arg) for arg in args) == 1


async def add_user_in_group(
    app: web.Application,
    user_id: UserID,
    group_id: GroupID,
    *,
    # identifies
    new_by_user_id: UserID | None = None,
    new_by_user_name: UserNameID | None = None,
    new_by_user_email: EmailStr | None = None,
    access_rights: AccessRightsDict | None = None,
) -> None:
    """Adds new_user (either by id or email) in group (with gid) owned by user_id

    Raises:
        UserInGroupNotFoundError
        GroupsException
        GroupNotFoundError
        UserInsufficientRightsError
    """
    if not _only_one_true(new_by_user_id, new_by_user_name, new_by_user_email):
        msg = "Invalid method call, required one of these: user id, username or user email, none provided"
        raise GroupsError(msg=msg)

    # First check if caller has write access to the group
    await _groups_repository.check_group_write_access(app, caller_id=user_id, group_id=group_id)

    # get target user to add to group
    if new_by_user_email:
        user = await _groups_repository.get_user_from_email(app, email=new_by_user_email, caller_id=user_id)
        new_by_user_id = user.id

    if new_by_user_id is not None:
        from .._users._users_service import get_user  # noqa: PLC0415

        new_user = await get_user(app, new_by_user_id)
        new_by_user_name = new_user["name"]

    return await _groups_repository.add_new_user_in_group(
        app,
        group_id=group_id,
        new_user_id=new_by_user_id,
        new_user_name=new_by_user_name,
        access_rights=access_rights,
    )
