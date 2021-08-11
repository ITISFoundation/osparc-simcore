#  a repo: retrieves engine from app
# TODO: a repo: some members acquire and retrieve connection
# TODO: a repo: any validation error in a repo is due to corrupt data in db!

from aiohttp import web

from .constants import APP_DB_ENGINE_KEY


class BaseRepository:
    def __init__(self, app: web.Application):
        self.engine = app[APP_DB_ENGINE_KEY]
