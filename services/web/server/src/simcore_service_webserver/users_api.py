
import logging
from typing import Dict, List, Tuple

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.result import RowProxy

from servicelib.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.login.cfg import get_storage

from .db_models import groups, user_to_groups, GroupType

logger = logging.getLogger(__name__)

def _convert_to_schema(db_row: RowProxy) -> Dict:
    return {
        "gid": db_row["gid"],
        "label": db_row["name"],
        "description": db_row["description"],
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
