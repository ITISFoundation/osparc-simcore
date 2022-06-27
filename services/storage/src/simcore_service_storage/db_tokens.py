import logging
from typing import Any

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from models_library.users import UserID
from psycopg2 import Error as DbApiError
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .constants import APP_CONFIG_KEY, APP_DB_ENGINE_KEY, MINUTE, RETRY_WAIT_SECS
from .models import tokens

log = logging.getLogger(__name__)


@retry(
    wait=wait_fixed(RETRY_WAIT_SECS),
    stop=stop_after_delay(1 * MINUTE),
    before_sleep=before_sleep_log(log, logging.INFO),
    reraise=True,
)
async def _get_tokens_from_db(engine: Engine, user_id: UserID) -> dict[str, Any]:
    async with engine.acquire() as conn:
        result = await conn.execute(
            sa.select(
                [
                    tokens,
                ]
            ).where(tokens.c.user_id == user_id)
        )
        row = await result.first()
        data = dict(row) if row else {}
        return data


async def get_api_token_and_secret(
    app: web.Application, user_id: UserID
) -> tuple[str, str]:
    # FIXME: this is a temporary solution. This information should be sent in some form
    # from the client side together with the userid?
    engine = app.get(APP_DB_ENGINE_KEY, None)

    # defaults from config if any, othewise None
    api_token = app[APP_CONFIG_KEY].BF_API_KEY
    api_secret = app[APP_CONFIG_KEY].BF_API_SECRET

    if engine:
        try:
            data = await _get_tokens_from_db(engine, user_id)
        except DbApiError:
            # NOTE this shall not log as error since is a possible outcome with an alternative
            log.warning(
                "Cannot retrieve tokens for user %s in pgdb %s",
                user_id,
                engine,
                exc_info=True,
            )
        else:
            data = data.get("token_data", {})
            api_token = data.get("token_key", api_token)
            api_secret = data.get("token_secret", api_secret)

    return api_token, api_secret
