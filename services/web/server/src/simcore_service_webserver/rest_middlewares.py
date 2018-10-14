
# TODO: envelope and jsonify all exceptions and responses!
from aiohttp import web


@web.middleware
async def process_responses(app: web.Application, handler):
    raise NotImplementedError("")
