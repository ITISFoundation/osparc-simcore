from aiohttp import web


APP_LOGIN_CONFIG = __name__ + ".config"
CFG_LOGIN_STORAGE = "STORAGE" # Needs to match login.cfg!!!


def get_storage(app: web.Application):
    return app[APP_LOGIN_CONFIG][CFG_LOGIN_STORAGE]
