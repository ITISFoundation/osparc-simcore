from aiohttp import web
from .login.decorators import login_required

@login_required
async def list_tags(request: web.Request):
  return []

@login_required
async def update_tag(request: web.Request):
  return {}

@login_required
async def delete_tag(request: web.Request):
  raise web.HTTPNoContent(content_type='application/json')