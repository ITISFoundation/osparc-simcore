""" Main's application module for simcore_service_storage service

    Functions to create, setup and run an aiohttp application provided a configuration object
"""
import json
import logging
from typing import Any, Dict, Optional

from aiohttp import web
from servicelib.application import create_safe_application
from servicelib.monitoring import setup_monitoring
from servicelib.tracing import setup_tracing

from .db import setup_db
from .dsm import setup_dsm
from .meta import WELCOME_MSG
from .rest import setup_rest
from .s3 import setup_s3

log = logging.getLogger(__name__)


def create(config: Dict[str, Any]) -> web.Application:
    log.debug(
        "Initializing app with config:\n%s",
        json.dumps(config, indent=2, sort_keys=True),
    )

    app = create_safe_application(config)

    tracing = config["tracing"]["enabled"]
    if tracing:
        setup_tracing(
            app,
            "simcore_service_storage",
            config["host"],
            config["port"],
            config["tracing"],
        )
    setup_db(app)  # -> postgres service
    setup_s3(app)  # -> minio service
    setup_dsm(app)  # core subsystem. Needs s3 and db setups done
    setup_rest(app)  # lastly, we expose API to the world

    if config.get("monitoring_enabled", False):
        setup_monitoring(app, "simcore_service_storage")

    return app


def run(config: Dict[str, Any], app: Optional[web.Application] = None):
    log.debug("Serving application ")
    if not app:
        app = create(config)

    async def welcome_banner(_app: web.Application):
        print(WELCOME_MSG, flush=True)

    app.on_startup.append(welcome_banner)

    web.run_app(app, host=config["host"], port=config["port"])
