from aiohttp import web
from models_library.groups import AccessRightsDict, Group, GroupsByTypeTuple, GroupUser
from models_library.users import GroupID, UserID

from . import _groups_db


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
    app: web.Application, *, user_id: UserID, new_group_values: dict
) -> tuple[Group, AccessRightsDict]:
    """
    raises GroupNotFoundError
    raises UserInsufficientRightsError
    """
    return await _groups_db.create_user_group(
        app, user_id=user_id, new_group=new_group_values
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
    return await _groups_db.get_user_group(app, user_id=user_id, gid=group_id)


async def update_organization(
    app: web.Application,
    *,
    user_id: UserID,
    group_id: GroupID,
    new_group_values: dict[str, str],
) -> tuple[Group, AccessRightsDict]:
    """

    raises GroupNotFoundError
    raises UserInsufficientRightsError
    """
    return await _groups_db.update_user_group(
        app, user_id=user_id, gid=group_id, new_group_values=new_group_values
    )


async def delete_organization(
    app: web.Application, *, user_id: UserID, group_id: GroupID
) -> None:
    """

    raises GroupNotFoundError
    raises UserInsufficientRightsError
    """
    return await _groups_db.delete_user_group(app, user_id=user_id, gid=group_id)


#
# ORGANIZATION MEMBERS
#


async def list_users_in_group(
    app: web.Application, user_id: UserID, gid: GroupID
) -> list[GroupUser]:
    return await _groups_db.list_users_in_group(app, user_id=user_id, gid=gid)
