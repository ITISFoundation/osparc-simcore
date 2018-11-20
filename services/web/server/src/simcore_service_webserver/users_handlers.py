import json
import logging

from aiohttp import web

from .login.decorators import RQT_USERID_KEY, login_required

logger = logging.getLogger(__name__)


# my/ -----------------------------------------------------------
@login_required
async def get_my_profile(request: web.Request):
    _uid= request[RQT_USERID_KEY]

    sample = {
        'login': 'pcrespov@foo.com',
        'gravatar_id': str(_uid)
    }
    return sample


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
