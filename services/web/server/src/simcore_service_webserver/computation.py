"""
    computation module is the main entry-point for computational backend

"""
import logging

from aiohttp import web
from servicelib.application_setup import ModuleCategory, app_module_setup

from .computation_comp_tasks_listening_task import setup as setup_comp_tasks_listener
from .computation_config import CONFIG_SECTION_NAME
from .computation_config import create_settings as create_computation_settings
from .computation_subscribe import subscribe

log = logging.getLogger(__file__)


@app_module_setup(
    __name__, ModuleCategory.ADDON, config_section=CONFIG_SECTION_NAME, logger=log
)
def setup_computation(app: web.Application):
    # create settings and injects in app
    create_computation_settings(app)

    # subscribe to rabbit upon startup
    app.on_startup.append(subscribe)

    # setup comp_task listener
    setup_comp_tasks_listener(app)


__all__ = "setup_computation"
