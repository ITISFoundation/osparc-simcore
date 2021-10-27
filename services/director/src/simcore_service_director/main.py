#!/usr/bin/env python3
import logging

from aiohttp import web

# NOTE: notice that servicelib is frozen to c8669fb52659b684514fefa4f3b4599f57f276a0
# pylint: disable=no-name-in-module
from servicelib.client_session import persistent_client_session
from simcore_service_director import registry_cache_task, resources
from simcore_service_director.monitoring import setup_app_monitoring
from simcore_service_director.rest import routing

from .registry_proxy import setup_registry

log = logging.getLogger(__name__)


def setup_app() -> web.Application:
    api_spec_path = resources.get_path(resources.RESOURCE_OPEN_API)
    app = routing.create_web_app(api_spec_path.parent, api_spec_path.name)

    # NOTE: ensure client session is context is run first, then any further get_client_sesions will be correctly closed
    app.cleanup_ctx.append(persistent_client_session)
    app.cleanup_ctx.append(setup_registry)

    registry_cache_task.setup(app)

    setup_app_monitoring(app, "simcore_service_director")

    # NOTE: removed tracing from director. Users old version of servicelib and
    # in any case this service will be completely replaced

    return app


def main() -> None:
    app = setup_app()
    web.run_app(app, port=8080)


if __name__ == "__main__":
    main()
