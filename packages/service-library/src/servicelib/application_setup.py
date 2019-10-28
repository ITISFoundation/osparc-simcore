import functools
import logging
from enum import Enum
from typing import Dict, Optional

from aiohttp import web

from .application_keys import APP_CONFIG_KEY

log = logging.getLogger(__name__)



class ModuleCategory(Enum):
    SYSTEM = 0
    ADDON = 1


def mark_as_module_setup(module_name: str, category: ModuleCategory,*, logger: Optional[logging.Logger]=None):
    """ Decorator that marks a function as the setup of a given module within an application

        - Marks a function as 'setup' of a given subsystem
        - Pre: Enables/disables execution of function upon 'application setup' (if addon)
        - Pre/post logging of setup

    Usage:

        from servicelib.application_setup import mark_as_module_setup

        @mark_as_module_setup('mysubsystem', ModuleCategory.SYSTEM, logger=log)
        def setup(app: web.Application):
            ...
    """
    # TODO: add module level category enum (system, plugin, addon)
    # TODO: adds subsystem dependencies dependencies: Optional[List]=None):
    # TODO: ensures runs ONLY once per application (e.g. keep id(app) )
    # TODO: resilience to failure. if this setup fails, then considering dependencies, is it fatal or app can start?

    if logger is None:
        logger = log

    section = module_name.split(".")[-1]

    def decorate(setup_func):

        # wrapper
        @functools.wraps(setup_func)
        def setup_wrapper(app: web.Application, *args, **kargs) -> bool:
            logger.debug("Setting up '%s' ...", module_name)

            if category == ModuleCategory.ADDON:
                # NOTE: only addons can be enabled/disabled
                cfg = app[APP_CONFIG_KEY][section]

                if not cfg.get("enabled", True):
                    logger.warning("'%s' setup explicitly disabled in config", module_name)
                    return False

            ok = setup_func(app, *args, **kargs)
            logger.debug("'%s' setup completed [%s]", module_name, ok)
            return ok

        # info
        def setup_metadata() -> Dict:
            return {
                'module_name': module_name
            }

        setup_wrapper.metadata = setup_metadata
        return setup_wrapper
    return decorate
