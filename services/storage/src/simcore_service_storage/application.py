""" Main's application module for simcore_service_storage service

    Functions to create, setup and run an aiohttp application provided a configuration object
"""
import logging

from aiohttp import web
from servicelib.monitoring import setup_monitoring
from servicelib.client_session import persistent_client_session

from .db import setup_db
from .dsm import setup_dsm
from .rest import setup_rest
from .s3 import setup_s3
from .settings import APP_CONFIG_KEY

log = logging.getLogger(__name__)




def create(config):
    log.debug("Creating and setting up application")

    app = web.Application()
    app[APP_CONFIG_KEY] = config

    setup_db(app)   # -> postgres service
    setup_s3(app)   # -> minio service
    setup_dsm(app)  # core subsystem. Needs s3 and db setups done
    setup_rest(app) # lastly, we expose API to the world

    monitoring = config["main"]["monitoring_enabled"]
    if monitoring:
        setup_monitoring(app, "simcore_service_storage")

    app.cleanup_ctx.append(persistent_client_session)

    return app

def run(config, app=None):
    log.debug("Serving application ")
    if not app:
        app = create(config)

    web.run_app(app,
        host=config["main"]["host"],
        port=config["main"]["port"])
