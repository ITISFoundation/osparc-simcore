from aiohttp import web
from models_library.basic_types import IDStr
from models_library.emails import LowerCaseEmailStr
from models_library.groups import (
    AccessRightsDict,
    Group,
    GroupMember,
    GroupsByTypeTuple,
    OrganizationCreate,
    OrganizationUpdate,
)
from models_library.products import ProductName
from models_library.users import GroupID, UserID
from pydantic import EmailStr

from ..users.api import get_user
from . import _groups_db
from .exceptions import GroupsError

#
# GROUPS
#


async def get_group_from_gid(app: web.Application, group_id: GroupID) -> Group | None:
    group_db = await _groups_db.get_group_from_gid(app, group_id=group_id)

    if group_db:
        return Group.model_construct(**group_db.model_dump())
    return None


#
# USER GROUPS: groups a user belongs to
#
async def list_user_groups_ids_with_read_access(
    app: web.Application, *, user_id: UserID
) -> list[GroupID]:
    # TODO: Room for optimization. For the moment we reuse existing db functions
    groups_by_type = await _groups_db.get_all_user_groups_with_read_access(
        app, user_id=user_id
    )
    assert groups_by_type.primary  # nosec

    groups_ids = [groups_by_type.primary[0].gid]

    # NOTE: that product-groups will not be listed here
    groups_ids += [g[0].gid for g in groups_by_type.standard]

    assert groups_by_type.everyone  # nosec
    groups_ids.append(groups_by_type.everyone[0].gid)

    return groups_ids


async def list_user_groups_with_read_access(
    app: web.Application, *, user_id: UserID
) -> GroupsByTypeTuple:
    """
    Returns the user primary group, standard groups and the all group
    """
    # NOTE: Careful! It seems we are filtering out groups, such as Product Groups,
    # because they do not have read access. I believe this was done because the
    # frontend did not want to display them.

    return await _groups_db.get_all_user_groups_with_read_access(app, user_id=user_id)


async def list_all_user_groups_ids(
    app: web.Application, *, user_id: UserID
) -> list[GroupID]:
    # TODO: Room for optimization. For the moment we reuse existing db functions
    user_groups = await _groups_db.get_all_user_groups(app, user_id=user_id)
    return [g.gid for g in user_groups]


async def get_product_group_for_user(
    app: web.Application, *, user_id: UserID, product_gid: GroupID
) -> tuple[Group, AccessRightsDict]:
    """
    Returns product's group if user belongs to it, otherwise it
    raises GroupNotFoundError
    """
    return await _groups_db.get_product_group_for_user(
        app, user_id=user_id, product_gid=product_gid
    )


#
# ORGANIZATIONS CRUD operations
#


async def create_organization(
    app: web.Application,
    *,
    user_id: UserID,
    create: OrganizationCreate,
) -> tuple[Group, AccessRightsDict]:
    """
    raises GroupNotFoundError
    raises UserInsufficientRightsError
    """
    return await _groups_db.create_user_group(
        app,
        user_id=user_id,
        create=create,
    )


async def get_organization(
    app: web.Application,
    *,
    user_id: UserID,
    group_id: GroupID,
) -> tuple[Group, AccessRightsDict]:
    """
    Gets group gid if user associated to it and has read access

    raises GroupNotFoundError
    raises UserInsufficientRightsError
    """
    return await _groups_db.get_user_group(app, user_id=user_id, group_9d=group_id)


async def update_organization(
    app: web.Application,
    *,
    user_id: UserID,
    group_id: GroupID,
    update: OrganizationUpdate,
) -> tuple[Group, AccessRightsDict]:
    """

    raises GroupNotFoundError
    raises UserInsufficientRightsError
    """

    return await _groups_db.update_user_group(
        app,
        user_id=user_id,
        group_id=group_id,
        update=update,
    )


async def delete_organization(
    app: web.Application, *, user_id: UserID, group_id: GroupID
) -> None:
    """

    raises GroupNotFoundError
    raises UserInsufficientRightsError
    """
    return await _groups_db.delete_user_group(app, user_id=user_id, group_id=group_id)


#
# ORGANIZATION MEMBERS
#


async def list_users_in_group(
    app: web.Application, user_id: UserID, group_id: GroupID
) -> list[GroupMember]:
    return await _groups_db.list_users_in_group(app, user_id=user_id, group_id=group_id)


async def get_user_in_group(
    app: web.Application,
    user_id: UserID,
    group_id: GroupID,
    the_user_id_in_group: UserID,
) -> GroupMember:

    return await _groups_db.get_user_in_group(
        app,
        user_id=user_id,
        group_id=group_id,
        the_user_id_in_group=the_user_id_in_group,
    )


async def update_user_in_group(
    app: web.Application,
    user_id: UserID,
    group_id: GroupID,
    the_user_id_in_group: UserID,
    access_rights: AccessRightsDict,
) -> GroupMember:
    return await _groups_db.update_user_in_group(
        app,
        user_id=user_id,
        group_id=group_id,
        the_user_id_in_group=the_user_id_in_group,
        access_rights=access_rights,
    )


async def delete_user_in_group(
    app: web.Application,
    user_id: UserID,
    group_id: GroupID,
    the_user_id_in_group: UserID,
) -> None:
    return await _groups_db.delete_user_from_group(
        app,
        user_id=user_id,
        group_id=group_id,
        the_user_id_in_group=the_user_id_in_group,
    )


async def is_user_by_email_in_group(
    app: web.Application, user_email: LowerCaseEmailStr, group_id: GroupID
) -> bool:

    return await _groups_db.is_user_by_email_in_group(
        app,
        email=user_email,
        group_id=group_id,
    )


async def auto_add_user_to_groups(app: web.Application, user_id: UserID) -> None:
    user: dict = await get_user(app, user_id)
    return await _groups_db.auto_add_user_to_groups(app, user=user)


async def auto_add_user_to_product_group(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
) -> GroupID:
    return await _groups_db.auto_add_user_to_product_group(
        app, user_id=user_id, product_name=product_name
    )


def _only_one_true(*args):
    return sum(bool(arg) for arg in args) == 1


async def add_user_in_group(
    app: web.Application,
    user_id: UserID,
    group_id: GroupID,
    *,
    new_user_id: UserID | None = None,
    new_user_name: IDStr | None = None,
    new_user_email: EmailStr | None = None,
    access_rights: AccessRightsDict | None = None,
) -> None:
    """Adds new_user (either by id or email) in group (with gid) owned by user_id

    Raises:
        UserInGroupNotFoundError
        GroupsException
    """
    if not _only_one_true(new_user_id, new_user_name, new_user_email):
        msg = "Invalid method call, required one of these: user id, username or user email, none provided"
        raise GroupsError(msg=msg)

    if new_user_email:
        user = await _groups_db.get_user_from_email(
            app, email=new_user_email, caller_user_id=user_id
        )
        new_user_id = user.id

    if not new_user_id:
        msg = "Missing new user in arguments"
        raise GroupsError(msg=msg)

    return await _groups_db.add_new_user_in_group(
        app,
        user_id=user_id,
        group_id=group_id,
        new_user_id=new_user_id,
        access_rights=access_rights,
    )
