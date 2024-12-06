from typing import Any

from aiohttp import web
from models_library.emails import LowerCaseEmailStr
from models_library.groups import Group
from models_library.users import GroupID, UserID

from ..users.api import get_user
from . import _groups_db
from ._common.types import AccessRightsDict
from ._groups_api import list_all_user_groups_ids, list_user_groups_ids_with_read_access
from .exceptions import GroupsError

__all__: tuple[str, ...] = (
    "list_user_groups_ids_with_read_access",
    "list_all_user_groups_ids",
    # nopycln: file
)


async def get_user_group(
    app: web.Application, user_id: UserID, gid: GroupID
) -> dict[str, str]:
    """
    Gets group gid if user associated to it and has read access

    raises GroupNotFoundError
    raises UserInsufficientRightsError
    """
    return await _groups_db.get_user_group(app, user_id=user_id, gid=gid)


async def update_user_group(
    app: web.Application,
    user_id: UserID,
    gid: GroupID,
    new_group_values: dict[str, str],
) -> dict[str, str]:
    return await _groups_db.update_user_group(
        app, user_id=user_id, gid=gid, new_group_values=new_group_values
    )


async def delete_user_group(
    app: web.Application, user_id: UserID, gid: GroupID
) -> None:
    return await _groups_db.delete_user_group(app, user_id=user_id, gid=gid)


async def list_users_in_group(
    app: web.Application, user_id: UserID, gid: GroupID
) -> list[dict[str, str]]:
    return await _groups_db.list_users_in_group(app, user_id=user_id, gid=gid)


async def auto_add_user_to_groups(app: web.Application, user_id: UserID) -> None:
    user: dict = await get_user(app, user_id)
    return await _groups_db.auto_add_user_to_groups(app, user=user)


async def auto_add_user_to_product_group(
    app: web.Application, user_id: UserID, product_name: str
) -> GroupID:
    return await _groups_db.auto_add_user_to_product_group(
        app, user_id=user_id, product_name=product_name
    )


async def is_user_by_email_in_group(
    app: web.Application, user_email: LowerCaseEmailStr, group_id: GroupID
) -> bool:

    return await _groups_db.is_user_by_email_in_group(
        app,
        email=user_email,
        group_id=group_id,
    )


async def add_user_in_group(
    app: web.Application,
    user_id: UserID,
    gid: GroupID,
    *,
    new_user_id: UserID | None = None,
    new_user_email: str | None = None,
    access_rights: AccessRightsDict | None = None,
) -> None:
    """Adds new_user (either by id or email) in group (with gid) owned by user_id

    Raises:
        UserInGroupNotFoundError
        GroupsException
    """

    if not new_user_id and not new_user_email:
        msg = "Invalid method call, missing user id or user email"
        raise GroupsError(msg=msg)

    if new_user_email:
        user = await _groups_db.get_user_from_email(app, email=new_user_email)
        new_user_id = user.id

    if not new_user_id:
        msg = "Missing new user in arguments"
        raise GroupsError(msg=msg)

    return await _groups_db.add_new_user_in_group(
        app,
        user_id=user_id,
        gid=gid,
        new_user_id=new_user_id,
        access_rights=access_rights,
    )


async def get_user_in_group(
    app: web.Application, user_id: UserID, gid: GroupID, the_user_id_in_group: int
) -> dict[str, str]:

    return await _groups_db.get_user_in_group(
        app, user_id=user_id, gid=gid, the_user_id_in_group=the_user_id_in_group
    )


async def update_user_in_group(
    app: web.Application,
    user_id: UserID,
    gid: GroupID,
    the_user_id_in_group: int,
    access_rights: dict,
) -> dict[str, str]:
    return await _groups_db.update_user_in_group(
        app,
        user_id=user_id,
        gid=gid,
        the_user_id_in_group=the_user_id_in_group,
        access_rights=access_rights,
    )


async def delete_user_in_group(
    app: web.Application, user_id: UserID, gid: GroupID, the_user_id_in_group: int
) -> None:
    return await _groups_db.delete_user_in_group(
        app, user_id=user_id, gid=gid, the_user_id_in_group=the_user_id_in_group
    )


async def get_group_from_gid(app: web.Application, gid: GroupID) -> Group | None:
    group_db = await _groups_db.get_group_from_gid(app, gid=gid)

    if group_db:
        return Group.model_construct(**group_db.model_dump())
    return None
