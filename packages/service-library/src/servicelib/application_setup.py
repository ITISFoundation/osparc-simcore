import functools
import inspect
import logging
from enum import Enum
from typing import Dict, List, Optional, Callable

from aiohttp import web

from .application_keys import APP_CONFIG_KEY

log = logging.getLogger(__name__)

APP_SETUP_KEY = f"{__name__ }.setup"


class ModuleCategory(Enum):
    SYSTEM = 0
    ADDON = 1


class ApplicationSetupError(Exception):
    pass


class DependencyError(ApplicationSetupError):
    pass


def app_module_setup(
    module_name: str,
    category: ModuleCategory,
    *,
    depends: Optional[List[str]] = None,
    config_section: str = None,
    config_enabled: str = None,
    logger: Optional[logging.Logger] = None,
) -> Callable:
    """ Decorator that marks a function as 'a setup function' for a given module in an application

        - Marks a function as 'setup' of a given module in an application
        - Ensures setup executed ONLY ONCE per app
        - Addon modules:
            - toggles run using 'enabled' entry in config file
        - logs execution

    See packages/service-library/tests/test_application_setup.py

    :param module_name: typically __name__ 
    :param depends: list of module_names that must be called first, defaults to None
    :param config_section: explicit configuration section, defaults to None (i.e. the name of the module, or last entry of the name if dotted)
    :param config_enabled: option in config to enable, defaults to None which is '$(module-section).enabled' (config_section and config_enabled are mutually exclusive)
    :raises DependencyError
    :raises ApplicationSetupError
    :return: False if setup was skipped
    :rtype: bool

    :Example:
        from servicelib.application_setup import app_module_setup

        @app_module_setup('mysubsystem', ModuleCategory.SYSTEM, logger=log)
        def setup(app: web.Application):
            ...
    """
    # TODO: resilience to failure. if this setup fails, then considering dependencies, is it fatal or app can start?

    module_name = module_name.replace(".__init__", "")
    depends = depends or []

    if config_section and config_enabled:
        raise ValueError("Can only set config_section or config_enabled but not both")

    section = config_section or module_name.split(".")[-1]
    if config_enabled is None:
        config_enabled = f"{section}.enabled"
    else:
        # if passes config_enabled, invalidates info on section
        section = None

    logger = logger or log

    def decorate(setup_func):

        if "setup" not in setup_func.__name__:
            logger.warning("Rename '%s' to contain 'setup'", setup_func.__name__)

        # metadata info
        def setup_metadata() -> Dict:
            return {
                "module_name": module_name,
                "dependencies": depends,
                "config_section": section,
                "config_enabled": config_enabled,
            }

        # wrapper
        @functools.wraps(setup_func)
        def setup_wrapper(app: web.Application, *args, **kargs) -> bool:
            # pre-setup
            logger.debug(
                "Setting up '%s' [%s; %s] ... ", module_name, category.name, depends
            )

            if APP_SETUP_KEY not in app:
                app[APP_SETUP_KEY] = []

            if category == ModuleCategory.ADDON:
                # NOTE: ONLY addons can be enabled/disabled
                # TODO: sometimes section is optional, check in config schema
                cfg = app[APP_CONFIG_KEY]

                def _get(cfg_, parts):
                    for part in parts:
                        if (
                            section and part == "enabled"
                        ):  # if section exists, no need to explicitly enable it
                            cfg_ = cfg_.get(part, True)
                        else:
                            cfg_ = cfg_[part]
                    return cfg_

                try:
                    is_enabled = _get(cfg, config_enabled.split("."))
                except KeyError as ee:
                    raise ApplicationSetupError(
                        f"Cannot find '{config_enabled}' in app config at [ {ee} ]"
                    )

                if not is_enabled:
                    logger.info(
                        "Skipping '%s' setup. Explicitly disabled in config",
                        module_name,
                    )
                    return False

            if depends:
                uninitialized = [
                    dep for dep in depends if dep not in app[APP_SETUP_KEY]
                ]
                if uninitialized:
                    msg = f"The following '{module_name}'' dependencies are still uninitialized: {uninitialized}"
                    log.error(msg)
                    raise DependencyError(msg)

            if module_name in app[APP_SETUP_KEY]:
                msg = f"'{module_name}' was already initialized in {app}. Setup can only be executed once per app."
                logger.error(msg)
                raise ApplicationSetupError(msg)

            # execution of setup
            ok = setup_func(app, *args, **kargs)

            # post-setup
            if ok is None:
                ok = True

            if ok:
                app[APP_SETUP_KEY].append(module_name)

            logger.debug("'%s' setup completed [%s]", module_name, ok)
            return ok

        setup_wrapper.metadata = setup_metadata
        setup_wrapper.MARK = "setup"

        return setup_wrapper

    return decorate


def is_setup_function(fun):
    return (
        inspect.isfunction(fun)
        and hasattr(fun, "MARK")
        and fun.MARK == "setup"
        and any(
            param.annotation == web.Application
            for name, param in inspect.signature(fun).parameters.items()
        )
    )
