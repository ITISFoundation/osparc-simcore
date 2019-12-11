
import logging
from typing import Tuple

import sqlalchemy as sa
from aiohttp import web
from psycopg2 import Error as DbApiError
from tenacity import retry

from servicelib.aiopg_utils import PostgresRetryPolicyUponOperation

from .models import tokens
from .settings import APP_CONFIG_KEY, APP_DB_ENGINE_KEY

log = logging.getLogger(__name__)


@retry(**PostgresRetryPolicyUponOperation(log).kwargs)
async def _get_tokens_from_db(engine, userid):
    async with engine.acquire() as conn:
        stmt = sa.select([tokens, ]).where(tokens.c.user_id == userid)
        result = await conn.execute(stmt)
        row = await result.first()
        data = dict(row) if row else {}
        return data


async def get_api_token_and_secret(request: web.Request, userid) -> Tuple[str, str]:
    # FIXME: this is a temporary solution. This information should be sent in some form
    # from the client side together with the userid?
    engine = request.app.get(APP_DB_ENGINE_KEY, None)

    # defaults from config if any, othewise None
    defaults = request.app[APP_CONFIG_KEY]["main"].get("test_datcore", {})
    api_token, api_secret = defaults.get('api_token'), defaults.get('api_secret')

    if engine:
        try:
            data = await _get_tokens_from_db(engine, userid)
        except DbApiError:
            log.exception("Cannot retrieve tokens for user %s in pgdb %s", userid, engine)
        else:
            data = data.get('token_data', {})
            api_token = data.get('token_key', api_token)
            api_secret = data.get('token_secret', api_secret)

    return api_token, api_secret
