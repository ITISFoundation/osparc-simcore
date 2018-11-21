import json
import logging

import sqlalchemy as sa
from aiohttp import web

from servicelib.application_keys import (APP_CONFIG_KEY, APP_DB_ENGINE_KEY,
                                         APP_DB_SESSION_KEY)

from .db_models import users
from .login.decorators import RQT_USERID_KEY, login_required
from .utils import gravatar_hash

logger = logging.getLogger(__name__)


# my/ -----------------------------------------------------------
@login_required
async def get_my_profile(request: web.Request):
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]

    async with engine.acquire() as conn:
        stmt = sa.select([users.c.email]).where(users.c.id == uid)
        email = await conn.scalar(stmt)

    return {
        'login': email,
        'gravatar_id': gravatar_hash(email)
    }



# my/tokens/ ------------------------------------------------------
token_sample = {
    'service': 'blackfynn',
    'token_key': 'N1BP5ZSpB',
    'token_secret': 'secret'
}

@login_required
async def list_tokens(request: web.Request):
    logger.debug(request)
    token_samples = [ token_sample, ] * 3

    return token_samples

@login_required
async def create_tokens(request: web.Request):
    logger.debug(request)
    raise web.HTTPCreated(text=json.dumps(token_sample), content_type="application/json")


@login_required
async def get_token(request: web.Request):
    raise NotImplementedError("%s still not implemented" % request)


@login_required
async def update_token(request: web.Request):
    raise NotImplementedError("%s still not implemented" % request)


@login_required
async def delete_token(request: web.Request):
    raise NotImplementedError("%s still not implemented" % request)
    #raise web.HTTPNoContent()
