from typing import Any

from aiohttp import web
from aiopg.sa.result import RowProxy
from models_library.emails import LowerCaseEmailStr
from models_library.groups import Group
from models_library.users import GroupID, UserID

from ..db.plugin import get_database_engine
from ..users.api import get_user
from . import _db
from ._utils import AccessRightsDict
from .exceptions import GroupsError


async def list_user_groups_with_read_access(
    app: web.Application, user_id: UserID
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """
    Returns the user primary group, standard groups and the all group
    """
    # NOTE: Careful! It seems we are filtering out groups, such as Product Groups,
    # because they do not have read access. I believe this was done because the frontend did not want to display them.
    async with get_database_engine(app).acquire() as conn:
        return await _db.get_all_user_groups_with_read_access(conn, user_id=user_id)


async def list_all_user_groups(app: web.Application, user_id: UserID) -> list[Group]:
    """
    Return all user groups
    """
    async with get_database_engine(app).acquire() as conn:
        groups_db = await _db.get_all_user_groups(conn, user_id=user_id)

    return [Group.model_construct(**group.model_dump()) for group in groups_db]


async def get_user_group(
    app: web.Application, user_id: UserID, gid: GroupID
) -> dict[str, str]:
    """
    Gets group gid if user associated to it and has read access

    raises GroupNotFoundError
    raises UserInsufficientRightsError
    """
    async with get_database_engine(app).acquire() as conn:
        return await _db.get_user_group(conn, user_id=user_id, gid=gid)


async def get_product_group_for_user(
    app: web.Application, user_id: UserID, product_gid: GroupID
) -> dict[str, str]:
    """
    Returns product's group if user belongs to it, otherwise it
    raises GroupNotFoundError
    """
    async with get_database_engine(app).acquire() as conn:
        return await _db.get_product_group_for_user(
            conn, user_id=user_id, product_gid=product_gid
        )


async def create_user_group(
    app: web.Application, user_id: UserID, new_group: dict
) -> dict[str, Any]:
    async with get_database_engine(app).acquire() as conn:
        return await _db.create_user_group(conn, user_id=user_id, new_group=new_group)


async def update_user_group(
    app: web.Application,
    user_id: UserID,
    gid: GroupID,
    new_group_values: dict[str, str],
) -> dict[str, str]:
    async with get_database_engine(app).acquire() as conn:
        return await _db.update_user_group(
            conn, user_id=user_id, gid=gid, new_group_values=new_group_values
        )


async def delete_user_group(
    app: web.Application, user_id: UserID, gid: GroupID
) -> None:
    async with get_database_engine(app).acquire() as conn:
        return await _db.delete_user_group(conn, user_id=user_id, gid=gid)


async def list_users_in_group(
    app: web.Application, user_id: UserID, gid: GroupID
) -> list[dict[str, str]]:
    async with get_database_engine(app).acquire() as conn:
        return await _db.list_users_in_group(conn, user_id=user_id, gid=gid)


async def auto_add_user_to_groups(app: web.Application, user_id: UserID) -> None:
    user: dict = await get_user(app, user_id)

    async with get_database_engine(app).acquire() as conn:
        return await _db.auto_add_user_to_groups(conn, user=user)


async def auto_add_user_to_product_group(
    app: web.Application, user_id: UserID, product_name: str
) -> GroupID:
    async with get_database_engine(app).acquire() as conn:
        return await _db.auto_add_user_to_product_group(
            conn, user_id=user_id, product_name=product_name
        )


async def is_user_by_email_in_group(
    app: web.Application, user_email: LowerCaseEmailStr, group_id: GroupID
) -> bool:
    async with get_database_engine(app).acquire() as conn:
        return await _db.is_user_by_email_in_group(
            conn,
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

    async with get_database_engine(app).acquire() as conn:
        if new_user_email:
            user: RowProxy = await _db.get_user_from_email(conn, new_user_email)
            new_user_id = user["id"]

        if not new_user_id:
            msg = "Missing new user in arguments"
            raise GroupsError(msg=msg)

        return await _db.add_new_user_in_group(
            conn,
            user_id=user_id,
            gid=gid,
            new_user_id=new_user_id,
            access_rights=access_rights,
        )


async def get_user_in_group(
    app: web.Application, user_id: UserID, gid: GroupID, the_user_id_in_group: int
) -> dict[str, str]:
    async with get_database_engine(app).acquire() as conn:
        return await _db.get_user_in_group(
            conn, user_id=user_id, gid=gid, the_user_id_in_group=the_user_id_in_group
        )


async def update_user_in_group(
    app: web.Application,
    user_id: UserID,
    gid: GroupID,
    the_user_id_in_group: int,
    access_rights: dict,
) -> dict[str, str]:
    async with get_database_engine(app).acquire() as conn:
        return await _db.update_user_in_group(
            conn,
            user_id=user_id,
            gid=gid,
            the_user_id_in_group=the_user_id_in_group,
            access_rights=access_rights,
        )


async def delete_user_in_group(
    app: web.Application, user_id: UserID, gid: GroupID, the_user_id_in_group: int
) -> None:
    async with get_database_engine(app).acquire() as conn:
        return await _db.delete_user_in_group(
            conn, user_id=user_id, gid=gid, the_user_id_in_group=the_user_id_in_group
        )


async def get_group_from_gid(app: web.Application, gid: GroupID) -> Group | None:
    async with get_database_engine(app).acquire() as conn:
        group_db = await _db.get_group_from_gid(conn, gid=gid)

    if group_db:
        return Group.model_construct(**group_db.model_dump())
    return None
