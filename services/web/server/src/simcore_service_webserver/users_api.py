import logging

from aiohttp import web
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.login.cfg import get_storage

logger = logging.getLogger(__name__)


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
