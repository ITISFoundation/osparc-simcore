from aiohttp import web

from .application_keys import APP_CONFIG_KEY
from .director_config import CONFIG_SECTION_NAME


def setup(app: web.Application):

    assert CONFIG_SECTION_NAME in app[APP_CONFIG_KEY]


    # TODO: implement!!!
