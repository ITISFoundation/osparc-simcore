
import logging
from typing import Dict, List, Optional, Tuple

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.result import RowProxy
from sqlalchemy import and_, literal_column

from servicelib.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.login.cfg import get_storage

from .db_models import GroupType, groups, user_to_groups
from .users_exceptions import GroupNotFoundError

logger = logging.getLogger(__name__)

def _convert_to_schema(db_row: RowProxy) -> Dict:
    return {
        "gid": db_row["gid"],
        "label": db_row["name"],
        "description": db_row["description"],
    }

def _convert_to_db(schema: Dict) -> Dict:
    return {
        "gid": schema["gid"] if "gid" in schema else None,
        "name": schema["label"] if "label" in schema else None,
        "description": schema["description"] if "description" in schema else None,
    }


async def list_user_groups(
    app: web.Application, user_id: str
) -> Tuple[Dict[str, str], List[Dict[str, str]], Dict[str, str]]:
    """returns the user groups
    Returns:
        Tuple[List[Dict[str, str]]] -- [returns the user primary group, groups and all group]
    """
    engine = app[APP_DB_ENGINE_KEY]
    primary_group = {}
    user_groups = []
    all_group = {}
    async with engine.acquire() as conn:
        query = (
            sa.select(
                [groups.c.gid, groups.c.name, groups.c.description, groups.c.type]
            )
            .select_from(
                user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
            )
            .where(user_to_groups.c.uid == user_id)
        )
        async for row in conn.execute(query):
            if row["type"] == GroupType.EVERYONE:
                all_group = _convert_to_schema(row)
            elif row["type"] == GroupType.PRIMARY:
                primary_group = _convert_to_schema(row)
            else:
                user_groups.append(_convert_to_schema(row))

    return (primary_group, user_groups, all_group)


async def get_user_group(app: web.Application, user_id: str, gid: str) -> Dict[str,str]:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        result = await conn.execute(
            sa.select([groups.c.gid, groups.c.name, groups.c.description]).select_from(user_to_groups.join(groups)).where(and_(user_to_groups.c.uid == user_id, user_to_groups.c.gid == gid))
        )
        group = await result.fetchone()
        if not group:
            raise GroupNotFoundError(gid)
        return _convert_to_schema(group)



async def create_user_group(
    app: web.Application, user_id: str, name: str, description: str
) -> Dict[str,str]:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        result = await conn.execute(
            # pylint: disable=no-value-for-parameter
            groups.insert().values(name=name, description=description).returning(literal_column("*"))
        )
        group: RowProxy = await result.fetchone()
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            user_to_groups.insert().values(uid=user_id, gid=group.gid)
        )
    return _convert_to_schema(group)


async def update_user_group(
        app: web.Application,
        user_id: str,
        gid: str,
        new_group_values: Dict[str, str]) -> Dict[str,str]:
    new_values = {k:v for k,v in _convert_to_db(new_group_values).items() if v}


    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        result = await conn.execute(
            sa.select([groups.c.gid, groups.c.name, groups.c.description]).select_from(user_to_groups.join(groups)).where(and_(user_to_groups.c.uid == user_id, user_to_groups.c.gid == gid))
        )
        group: RowProxy = await result.fetchone()

        if not group:
            raise GroupNotFoundError(gid)

        result = await conn.execute(
            # pylint: disable=no-value-for-parameter
            groups.update().values(**new_values).where(
                groups.c.gid == group.gid
            ).returning(literal_column("*"))
        )
        group = await result.fetchone()
        return _convert_to_schema(group)

async def delete_user_group(
        app: web.Application,
        user_id: str,
        gid: str) -> None:
    engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        result = await conn.execute(
            sa.select([groups.c.gid, groups.c.name, groups.c.description]).select_from(user_to_groups.join(groups)).where(and_(user_to_groups.c.uid == user_id, user_to_groups.c.gid == gid))
        )
        group: RowProxy = await result.fetchone()
        if not group:
            raise GroupNotFoundError(gid)
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            groups.delete().where(groups.c.gid == group.gid)
        )


async def is_user_guest(app: web.Application, user_id: int) -> bool:
    """Returns True if the user exists and is a GUEST"""
    db = get_storage(app)
    user = await db.get_user({"id": user_id})
    if not user:
        logger.warning("Could not find user with id '%s'", user_id)
        return False

    return UserRole(user["role"]) == UserRole.GUEST


async def delete_user(app: web.Application, user_id: int) -> None:
    """Deletes a user from the database if the user exists"""
    db = get_storage(app)
    user = await db.get_user({"id": user_id})
    if not user:
        logger.warning(
            "User with id '%s' could not be deleted because it does not exist", user_id
        )
        return

    await db.delete_user(user)
