
import logging
from typing import Tuple

import sqlalchemy as sa
from aiohttp import web
from psycopg2 import Error as DbApiError
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_random

from .settings import APP_CONFIG_KEY, APP_DB_ENGINE_KEY

log = logging.getLogger(__name__)

RETRY_WAIT_SECS = {"min":1, "max":3}
RETRY_COUNT = 3

# FIXME: this is a temporary solution DO NOT USE. This table needs to be in sync
# with services/web/server/src/simcore_service_webserver/db_models.py
_metadata = sa.MetaData()
_tokens = sa.Table("tokens", _metadata,
    sa.Column("token_id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("user_id", sa.BigInteger, nullable=False),
    sa.Column("token_service", sa.String, nullable=False),
    sa.Column("token_data", sa.JSON, nullable=False),
)


@retry(wait=wait_random(**RETRY_WAIT_SECS),
       stop=stop_after_attempt(RETRY_COUNT),
       before_sleep=before_sleep_log(log, logging.INFO),
       reraise=True)
async def _get_tokens_from_db(engine, userid):
    async with engine.acquire() as conn:
        stmt = sa.select([_tokens, ]).where(_tokens.c.user_id == userid)
        result = await conn.execute(stmt)
        row = await result.first()
        data = dict(row) if row else {}
        return data


async def get_api_token_and_secret(request: web.Request, userid) -> Tuple[str, str]:
    # FIXME: this is a temporary solution. This information should be sent in some form
    # from the client side together with the userid?
    engine = request.app.get(APP_DB_ENGINE_KEY, None)

    # defaults from config if any, othewise None
    defaults = request.app[APP_CONFIG_KEY]["main"].get("test_datacore", {})
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
