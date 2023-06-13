from typing import Any

from aiohttp import web
from aiopg.sa.result import RowProxy
from models_library.users import GroupID, UserID

from ..db.plugin import get_database_engine
from ..users.api import get_user
from . import _db
from ._utils import AccessRightsDict
from .exceptions import GroupsException


async def list_user_groups(
    app: web.Application, user_id: UserID
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """
    Returns the user primary group, standard groups and the all group
    """
    async with get_database_engine(app).acquire() as conn:
        return await _db.get_all_user_groups(conn, user_id=user_id)


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
        raise GroupsException("Invalid method call, missing user id or user email")

    async with get_database_engine(app).acquire() as conn:

        if new_user_email:
            user: RowProxy = await _db.get_user_from_email(conn, new_user_email)
            new_user_id = user["id"]

        if not new_user_id:
            raise GroupsException("Missing new user in arguments")

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
    new_values_for_user_in_group: dict,
) -> dict[str, str]:

    async with get_database_engine(app).acquire() as conn:
        return await _db.update_user_in_group(
            conn,
            user_id=user_id,
            gid=gid,
            the_user_id_in_group=the_user_id_in_group,
            new_values_for_user_in_group=new_values_for_user_in_group,
        )


async def delete_user_in_group(
    app: web.Application, user_id: UserID, gid: GroupID, the_user_id_in_group: int
) -> None:

    async with get_database_engine(app).acquire() as conn:
        return await _db.delete_user_in_group(
            conn, user_id=user_id, gid=gid, the_user_id_in_group=the_user_id_in_group
        )


async def get_group_from_gid(app: web.Application, gid: GroupID) -> RowProxy | None:

    async with get_database_engine(app).acquire() as conn:
        return await _db.get_group_from_gid(conn, gid=gid)
