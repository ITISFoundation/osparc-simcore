from aiohttp import web
from .security import login_required, authorized_userid # TODO: change this by login.

# my/
#@login_required
async def get_my_profile(request: web.Request):
    _uid= await authorized_userid(request)
    raise NotImplementedError("%s still not implemented" % request)


# my/tokens/
@login_required
async def list_tokens(request: web.Request):
    raise NotImplementedError("%s still not implemented" % request)

@login_required
async def create_tokens(request: web.Request):
    raise NotImplementedError("%s still not implemented" % request)

@login_required
async def get_token(request: web.Request):
    raise NotImplementedError("%s still not implemented" % request)

@login_required
async def update_token(request: web.Request):
    raise NotImplementedError("%s still not implemented" % request)

@login_required
async def delete_token(request: web.Request):
    raise NotImplementedError("%s still not implemented" % request)
