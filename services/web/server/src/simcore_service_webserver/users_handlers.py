import json
import random

from aiohttp import web

from .security import authorized_userid  # TODO: change this by login.
from .security import login_required


# my/
#@login_required
async def get_my_profile(request: web.Request):
    _uid= await authorized_userid(request)

    sample = {
        'login': 'pcrespov@foo.com',
        'gravatar_id': str(_uid)
    }
    return sample


# my/tokens/
token_sample = {
    'service': 'blackfynn',
    'token_key': 'N1BP5ZSpB',
    'token_secret': 'secret'
}

#@login_required
async def list_tokens(request: web.Request):
    token_samples = [ token_sample, ] * 3
    return token_samples

@login_required
async def create_tokens(request: web.Request):
    raise web.HTTPCreated(text=json.dumps(token_sample), content_type="application/json")


#@login_required
async def get_token(request: web.Request):
    return token_sample

@login_required
async def update_token(request: web.Request):
    raise NotImplementedError("%s still not implemented" % request)


@login_required
async def delete_token(request: web.Request):
    raise NotImplementedError("%s still not implemented" % request)

    #raise web.HTTPNoContent()
