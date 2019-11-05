""" resource manager subsystem

    Takes care of managing user generated resources such as:

    - interactive services
    - generated data

"""
import logging

from aiohttp import web

from servicelib.application_setup import ModuleCategory, app_module_setup

logger = logging.getLogger(__name__)

MODULE_NAME = __name__.split(".")[-1]
ROUTE_NAME = MODULE_NAME
module_name = module_name = __name__.replace(".__init__", "")

@app_module_setup(module_name, ModuleCategory.SYSTEM,
    logger=logger)
def setup(app: web.Application):
    """Sets up resource manager subsystem in the application (a la aiohttp)

    """



# alias
setup_resource_manager = setup

__all__ = (
    'setup_resource_manager'
)
