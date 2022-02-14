import functools
import inspect
import logging
from copy import deepcopy
from datetime import datetime
from distutils.util import strtobool
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from aiohttp import web

from .application_keys import APP_CONFIG_KEY, APP_SETTINGS_KEY

log = logging.getLogger(__name__)

APP_SETUP_COMPLETED_KEY = f"{__name__ }.setup"


class _SetupFunc(Protocol):
    __name__: str

    def __call__(self, app: web.Application, *args: Any, **kwds: Any) -> bool:
        ...


class _ApplicationSettings(Protocol):
    def is_enabled(self, field_name: str) -> bool:
        ...


class ModuleCategory(Enum):
    SYSTEM = 0
    ADDON = 1


# ERRORS ------------------------------------------------------------------


class SkipModuleSetup(Exception):
    def __init__(self, *, reason) -> None:
        self.reason = reason
        super().__init__(reason)


class ApplicationSetupError(Exception):
    ...


class DependencyError(ApplicationSetupError):
    ...


# HELPERS ------------------------------------------------------------------


def _is_addon_enabled_from_config(
    cfg: Dict[str, Any], dotted_section: str, section
) -> bool:
    try:
        parts: List[str] = dotted_section.split(".")
        # navigates app_config (cfg) searching for section
        searched_config = deepcopy(cfg)
        for part in parts:
            if section and part == "enabled":
                # if section exists, no need to explicitly enable it
                return strtobool(f"{searched_config.get(part, True)}")
            searched_config = searched_config[part]

    except KeyError as ee:
        raise ApplicationSetupError(
            f"Cannot find required option '{dotted_section}' in app config's section '{ee}'"
        ) from ee
    else:
        assert isinstance(searched_config, bool)  # nosec
        return searched_config


def _get_app_settings_and_field_name(
    app: web.Application,
    arg_module_name: str,
    arg_settings_name: Optional[str],
    setup_func_name: str,
    logger: logging.Logger,
) -> Tuple[Optional[_ApplicationSettings], Optional[str]]:

    app_settings: Optional[_ApplicationSettings] = app.get(APP_SETTINGS_KEY)
    settings_field_name = arg_settings_name

    if app_settings:

        if not settings_field_name:
            # FIXME: hard-coded WEBSERVER_ temporary
            settings_field_name = f"WEBSERVER_{arg_module_name.split('.')[-1].upper()}"

        logger.debug("Checking addon's %s ", f"{settings_field_name=}")

        if not hasattr(app_settings, settings_field_name):
            raise ValueError(
                f"Invalid option {arg_settings_name=} in module's setup {setup_func_name}. "
                f"It must be a field in {app_settings.__class__}"
            )

    return app_settings, settings_field_name


# PUBLIC API ------------------------------------------------------------------


def is_setup_completed(module_name: str, app: web.Application) -> bool:
    return module_name in app[APP_SETUP_COMPLETED_KEY]


def app_module_setup(
    module_name: str,
    category: ModuleCategory,
    *,
    depends: Optional[List[str]] = None,
    config_section: Optional[str] = None,
    config_enabled: Optional[str] = None,
    settings_name: Optional[str] = None,
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
    :param settings_name: field name in the app's settings that corresponds to this module. Defaults to the name of the module with app prefix.
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

    def _decorate(setup_func: _SetupFunc):

        if "setup" not in setup_func.__name__:
            logger.warning("Rename '%s' to contain 'setup'", setup_func.__name__)

        # metadata info
        def setup_metadata() -> Dict[str, Any]:
            return {
                "module_name": module_name,
                "dependencies": depends,
                "config_section": section,
                "config_enabled": config_enabled,
            }

        # wrapper
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

            if APP_SETUP_COMPLETED_KEY not in app:
                app[APP_SETUP_COMPLETED_KEY] = []

            if category == ModuleCategory.ADDON:
                # NOTE: ONLY addons can be enabled/disabled

                # TODO: cfg will be fully replaced by app_settings section below
                cfg = app[APP_CONFIG_KEY]
                is_enabled = _is_addon_enabled_from_config(cfg, config_enabled, section)
                if not is_enabled:
                    logger.info(
                        "Skipping '%s' setup. Explicitly disabled in config",
                        module_name,
                    )
                    return False

                # NOTE: if not disabled by config, it can be disabled by settings (tmp while legacy maintained)
                app_settings, module_settings_name = _get_app_settings_and_field_name(
                    app,
                    module_name,
                    settings_name,
                    setup_func.__name__,
                    logger,
                )

                if (
                    app_settings
                    and module_settings_name
                    and not app_settings.is_enabled(module_settings_name)
                ):
                    logger.info(
                        "Skipping setup %s. %s disabled in settings",
                        f"{module_name=}",
                        f"{module_settings_name=}",
                    )
                    return False

            if depends:
                # TODO: no need to enforce. Use to deduce order instead.
                uninitialized = [
                    dep for dep in depends if not is_setup_completed(dep, app)
                ]
                if uninitialized:
                    raise DependencyError(
                        f"Cannot setup app module '{module_name}' because the "
                        f"following dependencies are still uninitialized: {uninitialized}"
                    )

            # execution of setup
            try:
                if is_setup_completed(module_name, app):
                    raise SkipModuleSetup(
                        reason=f"'{module_name}' was already initialized in {app}."
                        " Setup can only be executed once per app."
                    )

                completed = setup_func(app, *args, **kargs)

                # post-setup
                if completed is None:
                    completed = True

                if completed:  # registers completed setup
                    app[APP_SETUP_COMPLETED_KEY].append(module_name)
                else:
                    raise SkipModuleSetup(
                        reason="Undefined (setup function returned false)"
                    )

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
        _wrapper.mark_as_simcore_servicelib_setup_func = True

        return _wrapper

    return _decorate


def is_setup_function(fun: Callable) -> bool:
    # TODO: use _SetupFunc protocol to check in runtime
    return (
        inspect.isfunction(fun)
        and hasattr(fun, "mark_as_simcore_servicelib_setup_func")
        and any(
            param.annotation == web.Application
            for _, param in inspect.signature(fun).parameters.items()
        )
    )
