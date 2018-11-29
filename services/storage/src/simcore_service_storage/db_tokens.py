
from typing import Tuple

import sqlalchemy as sa
from aiohttp import web

from .settings import APP_DB_ENGINE_KEY, APP_CONFIG_KEY

# FIXME: this is a temporary solution DO NOT USE. This table needs to be in sync
# with services/web/server/src/simcore_service_webserver/db_models.py
_metadata = sa.MetaData()
_tokens = sa.Table("tokens", _metadata,
    sa.Column("token_id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("user_id", sa.BigInteger, nullable=False),
    sa.Column("token_service", sa.String, nullable=False),
    sa.Column("token_data", sa.JSON, nullable=False),
)


async def get_api_token_and_secret(request: web.Request, userid) -> Tuple[str, str]:
    # FIXME: this is a temporary solution. This information should be sent in some form
    # from the client side together with the userid?
    engine = request.app.get(APP_DB_ENGINE_KEY, None)
    data = {}
    if engine:
        async with engine.acquire() as conn:
            stmt = sa.select([_tokens, ]).where(_tokens.c.user_id==userid)
            result = await conn.execute(stmt)
            row = await result.first()
            data =  dict(row) if row else {}

    defaults = request.app[APP_CONFIG_KEY]["main"].get("test_datacore", {})

    api_token = data.get('token_data', {}).get('token_key', defaults.get('api_token'))
    api_secret = data.get('token_data',{}).get('token_secret', defaults.get('api_secret'))

    return api_token, api_secret
