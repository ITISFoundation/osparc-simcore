from aiohttp import web


APP_LOGIN_CONFIG = __name__ + ".config"
CFG_LOGIN_STORAGE = __name__ + ".storage"


def get_storage(app: web.Application):
    return app[APP_LOGIN_CONFIG]['STORAGE']
