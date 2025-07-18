from datetime import datetime
from logging import getLogger
from typing import Any, Literal, TypedDict, cast

import asyncpg
from aiohttp import web
from servicelib.utils_secrets import generate_passcode

from . import _login_repository_legacy_sql

_logger = getLogger(__name__)

APP_LOGIN_STORAGE_KEY = f"{__name__}.APP_LOGIN_STORAGE_KEY"


## MODELS

ActionLiteralStr = Literal[
    "REGISTRATION", "INVITATION", "RESET_PASSWORD", "CHANGE_EMAIL"
]


class BaseConfirmationTokenDict(TypedDict):
    code: str
    action: ActionLiteralStr


class ConfirmationTokenDict(BaseConfirmationTokenDict):
    # SEE packages/postgres-database/src/simcore_postgres_database/models/confirmations.py
    user_id: int
    created_at: datetime
    # SEE handlers_confirmation.py::email_confirmation to determine what type is associated to each action
    data: str | None


## REPOSITORY


class AsyncpgStorage:
    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        user_table_name: str = "users",
        confirmation_table_name: str = "confirmations",
    ):
        self.pool = pool
        self.user_tbl = user_table_name
        self.confirm_tbl = confirmation_table_name

    #
    # CRUD confirmation
    #
    async def create_confirmation(
        self, user_id: int, action: ActionLiteralStr, data: str | None = None
    ) -> ConfirmationTokenDict:
        async with self.pool.acquire() as conn:
            # generate different code
            while True:
                # NOTE: use only numbers (i.e. avoid generate_password) since front-end does not handle well url encoding
                numeric_code: str = generate_passcode(20)
                if not await _login_repository_legacy_sql.find_one(
                    conn, self.confirm_tbl, {"code": numeric_code}
                ):
                    break
            # insert confirmation
            # NOTE: returns timestamp generated at the server-side
            confirmation = ConfirmationTokenDict(
                code=numeric_code,
                action=action,
                user_id=user_id,
                data=data,
                created_at=datetime.utcnow(),
            )
            c = await _login_repository_legacy_sql.insert(
                conn, self.confirm_tbl, dict(confirmation), returning="code"
            )
            assert numeric_code == c  # nosec
            return confirmation

    async def get_confirmation(
        self, filter_dict: dict[str, Any]
    ) -> ConfirmationTokenDict | None:
        if "user" in filter_dict:
            filter_dict["user_id"] = filter_dict.pop("user")["id"]
        async with self.pool.acquire() as conn:
            confirmation = await _login_repository_legacy_sql.find_one(
                conn, self.confirm_tbl, filter_dict
            )
            confirmation_token: ConfirmationTokenDict | None = (
                ConfirmationTokenDict(**confirmation) if confirmation else None  # type: ignore[typeddict-item]
            )
            return confirmation_token

    async def delete_confirmation(self, confirmation: ConfirmationTokenDict):
        async with self.pool.acquire() as conn:
            await _login_repository_legacy_sql.delete(
                conn, self.confirm_tbl, {"code": confirmation["code"]}
            )

    #
    # Transactions that guarantee atomicity. This avoids
    # inconsistent states of confirmation and users rows
    #

    async def delete_confirmation_and_user(
        self, user_id: int, confirmation: ConfirmationTokenDict
    ):
        async with self.pool.acquire() as conn, conn.transaction():
            await _login_repository_legacy_sql.delete(
                conn, self.confirm_tbl, {"code": confirmation["code"]}
            )
            await _login_repository_legacy_sql.delete(
                conn, self.user_tbl, {"id": user_id}
            )

    async def delete_confirmation_and_update_user(
        self, user_id: int, updates: dict[str, Any], confirmation: ConfirmationTokenDict
    ):
        async with self.pool.acquire() as conn, conn.transaction():
            await _login_repository_legacy_sql.delete(
                conn, self.confirm_tbl, {"code": confirmation["code"]}
            )
            await _login_repository_legacy_sql.update(
                conn, self.user_tbl, {"id": user_id}, updates
            )


def get_plugin_storage(app: web.Application) -> AsyncpgStorage:
    storage = cast(AsyncpgStorage, app.get(APP_LOGIN_STORAGE_KEY))
    assert storage, "login plugin was not initialized"  # nosec
    return storage
