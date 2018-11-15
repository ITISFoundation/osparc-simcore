""" Main's application module for simcore_service_storage service

    Functions to create, setup and run an aiohttp application provided a configuration object
"""
import logging

from aiohttp import web

from . import s3
from .db import setup_db
from .middlewares import dsm_middleware
from .rest import setup_rest
from .session import setup_session
from .settings import APP_CONFIG_KEY

log = logging.getLogger(__name__)

def create(config):
    log.debug("Creating and setting up application")

    app = web.Application()
    app[APP_CONFIG_KEY] = config

    app.middlewares.append(dsm_middleware)

    setup_db(app)
    setup_session(app)
    setup_rest(app)
    s3.setup(app)

    return app

def run(config, app=None):
    log.debug("Serving application ")
    if not app:
        app = create(config)

    web.run_app(app,
        host=config["main"]["host"],
        port=config["main"]["port"])
