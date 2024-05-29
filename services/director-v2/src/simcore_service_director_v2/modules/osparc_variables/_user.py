from fastapi import FastAPI
from models_library.users import UserID
from simcore_postgres_database.models.users import UserRole

from ...utils.db import get_repository
from ..db.repositories.users import UsersRepository


async def request_user_email(app: FastAPI, user_id: UserID) -> str:
    repo = get_repository(app, UsersRepository)
    return await repo.get_user_email(user_id=user_id)


async def request_user_role(app: FastAPI, user_id: UserID) -> str:
    repo = get_repository(app, UsersRepository)
    user_role: UserRole = await repo.get_user_role(user_id=user_id)
    return f"{user_role.value}"
