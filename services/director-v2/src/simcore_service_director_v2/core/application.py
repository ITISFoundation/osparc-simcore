import logging
from typing import Optional

from fastapi import FastAPI
from starlette.exceptions import HTTPException

from ..api.entrypoints import api_router
from ..api.errors.http_error import http_error_handler
from ..meta import api_version, api_vtag, project_name, summary
from ..modules import director_v0, docker_registry, remote_debug
from .events import create_start_app_handler, create_stop_app_handler
from .settings import AppSettings, BootModeEnum

logger = logging.getLogger(__name__)


def init_app(settings: Optional[AppSettings] = None) -> FastAPI:
    if settings is None:
        settings = AppSettings.create_from_env()

    logging.basicConfig(level=settings.loglevel)
    logging.root.setLevel(settings.loglevel)
    logger.debug(settings.json(indent=2))

    app = FastAPI(
        debug=settings.debug,
        title=project_name,
        description=summary,
        version=api_version,
        openapi_url=f"/api/{api_vtag}/openapi.json",
        docs_url="/dev/doc",
        redoc_url=None,  # default disabled
    )

    app.state.settings = settings

    if settings.boot_mode == BootModeEnum.DEBUG:
        remote_debug.setup(app)

    if settings.director_v0.enabled:
        director_v0.setup(app, settings.director_v0)

    if settings.registry.enabled:
        docker_registry.setup(app, settings.registry)

    app.add_event_handler("startup", create_start_app_handler(app))
    app.add_event_handler("shutdown", create_stop_app_handler(app))

    app.add_exception_handler(HTTPException, http_error_handler)

    app.include_router(api_router)

    return app
