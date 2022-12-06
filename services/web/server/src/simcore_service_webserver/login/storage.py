from datetime import datetime
from logging import getLogger
from typing import Literal, Optional, TypedDict

import asyncpg
from aiohttp import web

from . import _sql
from .utils import get_random_string

log = getLogger(__name__)

APP_LOGIN_STORAGE_KEY = f"{__name__}.APP_LOGIN_STORAGE_KEY"


## MODELS

ActionLiteralStr = Literal[
    "REGISTRATION", "INVITATION", "RESET_PASSWORD", "CHANGE_EMAIL"
]


class ConfirmationTokenDict(TypedDict):
    # SEE packages/postgres-database/src/simcore_postgres_database/models/confirmations.py
    code: str
    user_id: int
    action: ActionLiteralStr
    created_at: datetime
    # SEE handlers_confirmation.py::email_confirmation to determine what type is associated to each action
    data: Optional[str]


## REPOSITORY


class AsyncpgStorage:
    def __init__(
        self, pool, *, user_table_name="users", confirmation_table_name="confirmations"
    ):
        self.pool = pool
        self.user_tbl = user_table_name
        self.confirm_tbl = confirmation_table_name

    async def get_user(self, with_data) -> asyncpg.Record:
        # FIXME: these can throw!!!!
        async with self.pool.acquire() as conn:
            data = await _sql.find_one(conn, self.user_tbl, with_data)
            return data

    async def create_user(self, data: dict) -> asyncpg.Record:
        data.setdefault("created_at", datetime.utcnow())
        async with self.pool.acquire() as conn:
            data["id"] = await _sql.insert(conn, self.user_tbl, data)
            new_user = await _sql.find_one(conn, self.user_tbl, {"id": data["id"]})
            data["primary_gid"] = new_user["primary_gid"]
        return data

    async def update_user(self, user, updates) -> asyncpg.Record:
        async with self.pool.acquire() as conn:
            await _sql.update(conn, self.user_tbl, {"id": user["id"]}, updates)

    async def delete_user(self, user):
        async with self.pool.acquire() as conn:
            await _sql.delete(conn, self.user_tbl, {"id": user["id"]})

    async def create_confirmation(
        self, user_id, action: ActionLiteralStr, data=None
    ) -> ConfirmationTokenDict:
        async with self.pool.acquire() as conn:
            while True:
                code = get_random_string(30)
                if not await _sql.find_one(conn, self.confirm_tbl, {"code": code}):
                    break
            confirmation: ConfirmationTokenDict = {
                "code": code,
                "user_id": user_id,
                "action": action,
                "data": data,
                "created_at": datetime.utcnow(),
            }
            c = await _sql.insert(
                conn, self.confirm_tbl, confirmation, returning="code"
            )
            assert code == c  # nosec
            return confirmation

    async def get_confirmation(self, filter_dict) -> Optional[ConfirmationTokenDict]:
        if "user" in filter_dict:
            filter_dict["user_id"] = filter_dict.pop("user")["id"]
        async with self.pool.acquire() as conn:
            confirmation = await _sql.find_one(conn, self.confirm_tbl, filter_dict)
            return (
                ConfirmationTokenDict(**confirmation) if confirmation else confirmation
            )

    async def delete_confirmation(self, confirmation: ConfirmationTokenDict):
        async with self.pool.acquire() as conn:
            await _sql.delete(conn, self.confirm_tbl, {"code": confirmation["code"]})

    async def delete_user_registration_data(
        self, user, confirmation: ConfirmationTokenDict
    ):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await _sql.delete(
                    conn, self.confirm_tbl, {"code": confirmation["code"]}
                )
                await _sql.delete(conn, self.user_tbl, {"id": user["id"]})


def get_plugin_storage(app: web.Application) -> AsyncpgStorage:
    storage = app.get(APP_LOGIN_STORAGE_KEY)
    assert storage, "login plugin was not initialized"  # nosec
    return storage
