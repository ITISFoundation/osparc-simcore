""" Main's application module for simcore_service_storage service

    Functions to create, setup and run an aiohttp application provided a configuration object
"""
import logging

from aiohttp import web

from .s3 import setup_s3
from .db import setup_db
from .rest import setup_rest
from .settings import APP_CONFIG_KEY
from .dsm import setup_dsm

import ptvsd
ptvsd.enable_attach(address=('0.0.0.0', 3000), redirect_output=True)

log = logging.getLogger(__name__)

def create(config):
    log.debug("Creating and setting up application")

    app = web.Application()
    app[APP_CONFIG_KEY] = config

    setup_db(app)   # -> postgres service
    setup_s3(app)   # -> minio service
    setup_dsm(app)  # core subsystem. Needs s3 and db setups done
    setup_rest(app) # lastly, we expose API to the world

    return app

def run(config, app=None):
    log.debug("Serving application ")
    if not app:
        app = create(config)

    web.run_app(app,
        host=config["main"]["host"],
        port=config["main"]["port"])
