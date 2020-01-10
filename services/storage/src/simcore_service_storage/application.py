""" Main's application module for simcore_service_storage service

    Functions to create, setup and run an aiohttp application provided a configuration object
"""
import json
import logging
from typing import Dict

from aiohttp import web

from servicelib.application import create_safe_application
from servicelib.monitoring import setup_monitoring
from servicelib.tracing import setup_tracing

from .db import setup_db
from .dsm import setup_dsm
from .rest import setup_rest
from .s3 import setup_s3

log = logging.getLogger(__name__)


def create(config: Dict) -> web.Application:
    log.debug("Initializing app with config:\n%s",
        json.dumps(config, indent=2, sort_keys=True))

    app = create_safe_application(config)

    tracing = config["tracing"]["enabled"]
    if tracing:
        setup_tracing(app, "simcore_service_storage", 
                        config["main"]["host"], config["main"]["port"], config["tracing"])
    setup_db(app)   # -> postgres service
    setup_s3(app)   # -> minio service
    setup_dsm(app)  # core subsystem. Needs s3 and db setups done
    setup_rest(app) # lastly, we expose API to the world

    if config["main"].get("monitoring_enabled", False):
        setup_monitoring(app, "simcore_service_storage")

    return app

def run(config, app=None):
    log.debug("Serving application ")
    if not app:
        app = create(config)

    web.run_app(app,
        host=config["main"]["host"],
        port=config["main"]["port"])
