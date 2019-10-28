import functools
import logging
from enum import Enum
from typing import Dict, Optional, List

from aiohttp import web

from .application_keys import APP_CONFIG_KEY

log = logging.getLogger(__name__)

APP_SETUP_KEY = f"{__name__ }.setup"

class ModuleCategory(Enum):
    SYSTEM = 0
    ADDON = 1

class DependencyError(Exception):
    def __init__(self, current_module, dependency):
        msg = f"Setup for '{dependency}' needed before running current setup [{current_module}]"
        super(DependencyError, self).__init__(msg)


def mark_as_module_setup(module_name: str, category: ModuleCategory,*,
    depends: Optional[List[str]]=None,
    logger: Optional[logging.Logger]=None):
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
            logger.debug("Setting up '%s' [%s; %s] ... ", module_name, category.name, depends)

            if APP_SETUP_KEY not in app:
                app[APP_SETUP_KEY] = []

            if depends:
                for dependency in depends:
                    if dependency not in app[APP_SETUP_KEY]:
                        raise DependencyError(module_name, dependency)

            if category == ModuleCategory.ADDON:
                # NOTE: only addons can be enabled/disabled
                cfg = app[APP_CONFIG_KEY][section]

                if not cfg.get("enabled", True):
                    logger.warning("'%s' setup explicitly disabled in config", module_name)
                    return False

            ok = setup_func(app, *args, **kargs)

            if ok is None:
                ok = True

            if ok:
                app[APP_SETUP_KEY].append(module_name)

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
