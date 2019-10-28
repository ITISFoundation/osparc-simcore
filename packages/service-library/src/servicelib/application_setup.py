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
        logger: Optional[logging.Logger]=None
    ) -> bool:
    """ Decorator that marks a function as 'a setup function' for a given module in an application

        - Marks a function as 'setup' of a given module in an application
        - Addon modules:
            - toggles run using 'enabled' entry in config file
        - logs execution

    Usage:
        from servicelib.application_setup import mark_as_module_setup

        @mark_as_module_setup('mysubsystem', ModuleCategory.SYSTEM, logger=log)
        def setup(app: web.Application):
            ...

    See packages/service-library/tests/test_application_setup.py

    :param module_name: [description]
    :type module_name: str
    :param category: [description]
    :type category: ModuleCategory
    :param depends: [description], defaults to None
    :type depends: Optional[List[str]], optional
    :param logger: [description], defaults to None
    :type logger: Optional[logging.Logger], optional
    :raises DependencyError: [description]
    :return: False if setup was skipped
    :rtype: bool
    """
    # TODO: adds subsystem dependencies dependencies: Optional[List]=None):
    # TODO: ensures runs ONLY once per application (e.g. keep id(app) )
    # TODO: resilience to failure. if this setup fails, then considering dependencies, is it fatal or app can start?

    if logger is None:
        logger = log

    depends = depends or []

    section = module_name.split(".")[-1]

    def decorate(setup_func):

        # wrapper
        @functools.wraps(setup_func)
        def setup_wrapper(app: web.Application, *args, **kargs) -> bool:
            logger.debug("Setting up '%s' [%s; %s] ... ", module_name, category.name, depends)

            if APP_SETUP_KEY not in app:
                app[APP_SETUP_KEY] = []

            if category == ModuleCategory.ADDON:
                # NOTE: only addons can be enabled/disabled
                cfg = app[APP_CONFIG_KEY][section]

                if not cfg.get("enabled", True):
                    logger.info("Skipping '%s' setup. Explicitly disabled in config", module_name)
                    return False

            if depends:
                for dependency in depends:
                    if dependency not in app[APP_SETUP_KEY]:
                        raise DependencyError(module_name, dependency)

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
                'module_name': module_name,
                'dependencies': depends
            }

        setup_wrapper.metadata = setup_metadata
        return setup_wrapper
    return decorate
