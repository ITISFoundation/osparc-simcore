import functools
import inspect
import logging
import warnings
from copy import deepcopy
from datetime import datetime
from distutils.util import strtobool
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

from aiohttp import web

from .application_keys import APP_CONFIG_KEY, APP_SETTINGS_KEY

log = logging.getLogger(__name__)


APP_SETUP_KEY = f"{__name__ }.setup"


class _SetupFunc(Protocol):
    __name__: str

    def __call__(self, app: web.Application, *args: Any, **kwds: Any) -> bool:
        ...


class ModuleCategory(Enum):
    SYSTEM = 0
    ADDON = 1


class SkipModuleSetup(Exception):
    def __init__(self, *, reason) -> None:
        self.reason = reason
        super().__init__(reason)


class ApplicationSetupError(Exception):
    pass


class DependencyError(ApplicationSetupError):
    pass


def check_addon_enabled(
    app: web.Application, config_enabled: str, is_option_in_section: bool
) -> bool:
    """ONLY addons can be enabled/disabled"""
    # TODO: sometimes section is optional, check in config schema

    def _get_value(config: Dict[str, Any], dotted_key: str) -> bool:
        """Returns value in nested-dict config"""
        sub_config = deepcopy(config)
        for part in dotted_key.split("."):
            if is_option_in_section and part == "enabled":
                # if section exists, no need to explicitly enable it
                return strtobool(f"{sub_config.get(part, True)}")
            sub_config = sub_config[part]
        assert isinstance(sub_config, bool)  # nosec
        return sub_config

    # ----

    try:
        # NEW APPROACH: settings-library settings classes
        settings = app[APP_SETTINGS_KEY]
        is_enabled = bool(getattr(settings, config_enabled))

    except (KeyError, AttributeError):
        # LEGACY: trafaret config dicts
        warnings.warn(
            "dict configs are replaced settings-library settings",
            DeprecationWarning,
            stacklevel=2,
        )
        cfg = app[APP_CONFIG_KEY]

        try:
            is_enabled = _get_value(config=cfg, dotted_key=config_enabled)
        except KeyError as ee:
            raise ApplicationSetupError(
                f"Cannot find required option '{config_enabled}' in app config's section '{ee}'"
            ) from ee

    return is_enabled


def app_module_setup(
    module_name: str,
    category: ModuleCategory,
    *,
    depends: Optional[List[str]] = None,
    config_section: str = None,
    config_enabled: str = None,
    logger: logging.Logger = log,
) -> Callable:
    """Decorator that marks a function as 'a setup function' for a given module in an application

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
    :return: True if setup was completed or False if setup was skipped
    :rtype: bool

    :Example:
        from servicelib.aiohttp.application_setup import app_module_setup

        @app_module_setup('mysubsystem', ModuleCategory.SYSTEM, logger=log)
        def setup(app: web.Application):
            ...
    """
    # TODO: resilience to failure. if this setup fails, then considering dependencies, is it fatal or app can start?
    # TODO: enforce signature as def setup(app: web.Application, **kwargs) -> web.Application

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

    def _decorator(setup_func: _SetupFunc):

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

        @functools.wraps(setup_func)
        def _wrapper(app: web.Application, *args, **kargs) -> bool:
            # pre-setup
            head_msg = f"Setup of {module_name}"
            started = datetime.now()
            logger.info(
                "%s (%s, %s) started ... ",
                head_msg,
                f"{category.name=}",
                f"{depends}",
            )

            if APP_SETUP_KEY not in app:
                app[APP_SETUP_KEY] = []

            if category == ModuleCategory.ADDON:
                is_enabled = check_addon_enabled(
                    app, config_enabled, is_option_in_section=section is not None
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
                    msg = f"Cannot setup app module '{module_name}' because the following dependencies are still uninitialized: {uninitialized}"
                    log.error(msg)
                    raise DependencyError(msg)

            if module_name in app[APP_SETUP_KEY]:
                msg = f"'{module_name}' was already initialized in {app}. Setup can only be executed once per app."
                logger.error(msg)
                raise ApplicationSetupError(msg)

            # execution of setup
            try:
                completed = setup_func(app, *args, **kargs)

                # post-setup
                if completed is None:
                    completed = True

                if completed:
                    app[APP_SETUP_KEY].append(module_name)
                else:
                    raise SkipModuleSetup(reason="Undefined")

            except SkipModuleSetup as exc:
                logger.warning("Skipping '%s' setup: %s", module_name, exc.reason)
                completed = False

            elapsed = datetime.now() - started
            logger.info(
                "%s %s [Elapsed: %3.1f secs]",
                head_msg,
                "completed" if completed else "skipped",
                elapsed.total_seconds(),
            )
            return completed

        _wrapper.metadata = setup_metadata
        _wrapper.MARK = "setup"

        return _wrapper

    return _decorator


def is_setup_function(fun):
    return (
        inspect.isfunction(fun)
        and getattr(fun, "MARK", None) == "setup"
        and any(
            param.annotation == web.Application
            for _, param in inspect.signature(fun).parameters.items()
        )
    )
