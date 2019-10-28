import functools
import inspect
import logging
from enum import Enum
from typing import Dict, List, Optional

from aiohttp import web

from .application_keys import APP_CONFIG_KEY

log = logging.getLogger(__name__)

APP_SETUP_KEY = f"{__name__ }.setup"

class ModuleCategory(Enum):
    SYSTEM = 0
    ADDON = 1

class AppSetupBaseError(Exception):
    pass

class DependencyError(AppSetupBaseError):
    pass

def mark_as_module_setup(module_name: str, category: ModuleCategory,*,
        depends: Optional[List[str]]=None,
        config_section: str=None,
        logger: Optional[logging.Logger]=None
    ) -> bool:
    """ Decorator that marks a function as 'a setup function' for a given module in an application

        - Marks a function as 'setup' of a given module in an application
        - Ensures setup executed ONLY ONCE per app
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
    :param config_section: explicit configuration section, defaults to None (i.e. the name of the module, or last entry of the name if dotted)
    :type config_section: str, optional
    :param logger: [description], defaults to None
    :type logger: Optional[logging.Logger], optional
    :raises DependencyError: [description]
    :raises AppSetupBaseError: [description]
    :return: False if setup was skipped
    :rtype: bool
    """

    # TODO: adds subsystem dependencies dependencies: Optional[List]=None):
    # TODO: ensures runs ONLY once per application (e.g. keep id(app) )
    # TODO: resilience to failure. if this setup fails, then considering dependencies, is it fatal or app can start?

    if logger is None:
        logger = log
    depends = depends or []
    section = config_section or module_name.split(".")[-1]

    def decorate(setup_func):

        if "setup" not in setup_func.__name__:
            logger.warning("Rename '%s' to contain 'setup'", setup_func.__name__)

        # wrapper
        @functools.wraps(setup_func)
        def setup_wrapper(app: web.Application, *args, **kargs) -> bool:
            # pre-setup
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
                uninitialized = [dep for dep in depends if dep not in app[APP_SETUP_KEY]]
                if uninitialized:
                    msg = f"The following '{module_name}'' dependencies are still uninitialized: {uninitialized}"
                    log.error(msg)
                    raise DependencyError(msg)

            if module_name in app[APP_SETUP_KEY]:
                msg = f"'{module_name}' was already initialized in {app}. Setup can only be executed once per app."
                logger.error(msg)
                raise AppSetupBaseError(msg)

            # execution of setup
            ok = setup_func(app, *args, **kargs)

            # post-setup
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
        setup_wrapper.MARK = 'setup'

        return setup_wrapper
    return decorate


def is_setup_function(fun):
    return inspect.isfunction(fun) and \
        hasattr(fun, 'MARK') and fun.MARK == 'setup' and \
        any(param.annotation == web.Application
            for name, param in inspect.signature(fun).parameters.items())
