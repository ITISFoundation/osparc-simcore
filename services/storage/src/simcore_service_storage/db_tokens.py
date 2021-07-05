import logging
from typing import Tuple

import sqlalchemy as sa
from aiohttp import web
from psycopg2 import Error as DbApiError
from servicelib.aiopg_utils import PostgresRetryPolicyUponOperation
from tenacity import retry

from .constants import APP_CONFIG_KEY, APP_DB_ENGINE_KEY
from .models import tokens

log = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponOperation(log).kwargs)
async def _get_tokens_from_db(engine: sa.engine.Engine, userid: int):
    async with engine.acquire() as conn:
        result = await conn.execute(
            sa.select(
                [
                    tokens,
                ]
            ).where(tokens.c.user_id == userid)
        )
        row = await result.first()
        data = dict(row) if row else {}
        return data


async def get_api_token_and_secret(
    app: web.Application, userid: int
) -> Tuple[str, str]:
    # FIXME: this is a temporary solution. This information should be sent in some form
    # from the client side together with the userid?
    engine = app.get(APP_DB_ENGINE_KEY, None)

    # defaults from config if any, othewise None
    api_token = app[APP_CONFIG_KEY].BF_API_KEY
    api_secret = app[APP_CONFIG_KEY].BF_API_SECRET

    if engine:
        try:
            data = await _get_tokens_from_db(engine, userid)
        except DbApiError:
            # NOTE this shall not log as error since is a possible outcome with an alternative
            log.warning(
                "Cannot retrieve tokens for user %s in pgdb %s",
                userid,
                engine,
                exc_info=True,
            )
        else:
            data = data.get("token_data", {})
            api_token = data.get("token_key", api_token)
            api_secret = data.get("token_secret", api_secret)

    return api_token, api_secret
