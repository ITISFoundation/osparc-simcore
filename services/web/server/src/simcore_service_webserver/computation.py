"""
    computation module is the main entry-point for computational backend

"""
import logging

from aiohttp import web
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.rest_routing import iter_path_operations, map_handlers_with_operations

from . import computation_handlers
from .computation_comp_tasks_listening_task import setup as setup_comp_tasks_listener
from .computation_config import CONFIG_SECTION_NAME
from .computation_config import create_settings as create_computation_settings
from .computation_subscribe import subscribe
from .rest_config import APP_OPENAPI_SPECS_KEY

log = logging.getLogger(__file__)


@app_module_setup(
    __name__, ModuleCategory.ADDON, config_section=CONFIG_SECTION_NAME, logger=log
)
def setup_computation(app: web.Application):
    # create settings and injects in app
    create_computation_settings(app)

    # subscribe to rabbit upon startup
    # TODO: Define connection policies (e.g. {on-startup}, lazy). Could be defined in config-file
    app.on_startup.append(subscribe)

    # TODO: add function to "unsubscribe"
    # app.on_cleanup.append(unsubscribe)

    if not APP_OPENAPI_SPECS_KEY in app:
        log.warning(
            "rest submodule not initialised? computation routes will not be defined!"
        )
        return

    specs = app[APP_OPENAPI_SPECS_KEY]
    # routes = map_handlers_with_operations(
    #     {
    #         # "start_pipeline": computation_handlers.start_pipeline,
    #         # "stop_pipeline": computation_handlers.stop_pipeline,
    #     },
    #     filter(lambda o: "stop_pipeline" in o[2], iter_path_operations(specs)),
    #     strict=True,
    # )
    # app.router.add_routes(routes)
    setup_comp_tasks_listener(app)


__all__ = "setup_computation"
