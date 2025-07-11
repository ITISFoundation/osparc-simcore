from aiohttp import web
from models_library.basic_types import IDStr
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
from models_library.users import UserID
from pydantic import EmailStr

from ..users import users_service
from . import _groups_repository
from .exceptions import GroupsError

#
# GROUPS
#


async def get_group_from_gid(app: web.Application, group_id: GroupID) -> Group | None:
    group_db = await _groups_repository.get_group_from_gid(app, group_id=group_id)

    if group_db:
        return Group.model_construct(**group_db.model_dump())
    return None


#
# USER GROUPS: groups a user belongs to
#


async def list_user_groups_with_read_access(
    app: web.Application, *, user_id: UserID
) -> GroupsByTypeTuple:
    """
    Returns the user primary group, standard groups and the all group
    """
    # NOTE: Careful! It seems we are filtering out groups, such as Product Groups,
    # because they do not have read access. I believe this was done because the
    # frontend did not want to display them.
    return await _groups_repository.get_all_user_groups_with_read_access(
        app, user_id=user_id
    )


async def list_user_groups_ids_with_read_access(
    app: web.Application, *, user_id: UserID
) -> list[GroupID]:
    return await _groups_repository.get_ids_of_all_user_groups_with_read_access(
        app, user_id=user_id
    )


async def list_all_user_groups_ids(
    app: web.Application, *, user_id: UserID
) -> list[GroupID]:
    return await _groups_repository.get_ids_of_all_user_groups(app, user_id=user_id)


async def get_product_group_for_user(
    app: web.Application, *, user_id: UserID, product_gid: GroupID
) -> tuple[Group, AccessRightsDict]:
    """
    Returns product's group if user belongs to it, otherwise it
    raises GroupNotFoundError
    """
    return await _groups_repository.get_product_group_for_user(
        app, user_id=user_id, product_gid=product_gid
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
    return await _groups_repository.get_user_group(
        app, user_id=user_id, group_id=group_id
    )


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


async def delete_standard_group(
    app: web.Application, *, user_id: UserID, group_id: GroupID
) -> None:
    """NOTE: creation/update and deletion restricted to STANDARD groups

    raises GroupNotFoundError
    raises UserInsufficientRightsError: needs DELETE access
    """
    return await _groups_repository.delete_standard_group(
        app, user_id=user_id, group_id=group_id
    )


#
# GROUP MEMBERS (= a user with some access-rights to a group)
#


async def list_group_members(
    app: web.Application, user_id: UserID, group_id: GroupID
) -> list[GroupMember]:
    return await _groups_repository.list_users_in_group(
        app, caller_id=user_id, group_id=group_id
    )


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


async def is_user_by_email_in_group(
    app: web.Application, user_email: LowerCaseEmailStr, group_id: GroupID
) -> bool:

    return await _groups_repository.is_user_by_email_in_group(
        app,
        email=user_email,
        group_id=group_id,
    )


async def auto_add_user_to_groups(app: web.Application, user_id: UserID) -> None:
    user: dict = await users_service.get_user(app, user_id)
    return await _groups_repository.auto_add_user_to_groups(app, user=user)


async def auto_add_user_to_product_group(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
) -> GroupID:
    return await _groups_repository.auto_add_user_to_product_group(
        app, user_id=user_id, product_name=product_name
    )


def _only_one_true(*args):
    return sum(bool(arg) for arg in args) == 1


async def add_user_in_group(
    app: web.Application,
    user_id: UserID,
    group_id: GroupID,
    *,
    # identifies
    new_by_user_id: UserID | None = None,
    new_by_user_name: IDStr | None = None,
    new_by_user_email: EmailStr | None = None,
    access_rights: AccessRightsDict | None = None,
) -> None:
    """Adds new_user (either by id or email) in group (with gid) owned by user_id

    Raises:
        UserInGroupNotFoundError
        GroupsException
    """
    if not _only_one_true(new_by_user_id, new_by_user_name, new_by_user_email):
        msg = "Invalid method call, required one of these: user id, username or user email, none provided"
        raise GroupsError(msg=msg)

    # get target user to add to group
    if new_by_user_email:
        user = await _groups_repository.get_user_from_email(
            app, email=new_by_user_email, caller_id=user_id
        )
        new_by_user_id = user.id

    if new_by_user_id is not None:
        new_user = await users_service.get_user(app, new_by_user_id)
        new_by_user_name = new_user["name"]

    return await _groups_repository.add_new_user_in_group(
        app,
        caller_id=user_id,
        group_id=group_id,
        new_user_id=new_by_user_id,
        new_user_name=new_by_user_name,
        access_rights=access_rights,
    )
