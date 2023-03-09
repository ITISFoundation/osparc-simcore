import logging

from fastapi import FastAPI
from servicelib.fastapi.openapi import (
    get_common_oas_options,
    override_fastapi_openapi_method,
)
from servicelib.logging_utils import config_all_loggers

from .._meta import (
    API_VTAG,
    APP_FINISHED_BANNER_MSG,
    APP_NAME,
    APP_STARTED_BANNER_MSG,
    SUMMARY,
    VERSION,
)
from ..modules import rabbitmq, task_monitor
from ._routes import router
from .settings import ApplicationSettings

logger = logging.getLogger(__name__)


def _setup_logger(settings: ApplicationSettings):
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/3148
    logging.basicConfig(level=settings.LOGLEVEL.value)  # NOSONAR
    logging.root.setLevel(settings.LOGLEVEL.value)
    config_all_loggers()


def create_app() -> FastAPI:
    # SETTINGS
    settings = ApplicationSettings.create_from_envs()
    _setup_logger(settings)
    logger.debug(settings.json(indent=2))

    assert settings.SC_BOOT_MODE  # nosec
    app = FastAPI(
        debug=settings.SC_BOOT_MODE.is_devel_mode(),
        title=APP_NAME,
        description=SUMMARY,
        version=f"{VERSION}",
        openapi_url=f"/api/{API_VTAG}/openapi.json",
        **get_common_oas_options(settings.SC_BOOT_MODE.is_devel_mode()),
    )
    override_fastapi_openapi_method(app)
    app.state.settings = settings

    # ROUTERS
    app.include_router(router)

    # SUBMODULES
    task_monitor.setup(app)
    rabbitmq.setup(app)

    async def _on_startup() -> None:
        print(APP_STARTED_BANNER_MSG, flush=True)

    async def _on_shutdown() -> None:
        print(APP_FINISHED_BANNER_MSG, flush=True)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app
