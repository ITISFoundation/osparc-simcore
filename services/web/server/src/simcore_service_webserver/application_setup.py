import functools
from typing import TypeAlias

import servicelib.aiohttp.application_setup

from .application_keys import APP_SETTINGS_APPKEY

# models
ModuleCategory: TypeAlias = servicelib.aiohttp.application_setup.ModuleCategory


# free-functions
is_setup_completed = servicelib.aiohttp.application_setup.is_setup_completed

# decorators
ensure_single_setup = servicelib.aiohttp.application_setup.ensure_single_setup

app_setup_func = functools.partial(
    servicelib.aiohttp.application_setup.app_module_setup,
    app_settings_key=APP_SETTINGS_APPKEY,
)

__all__: tuple[str, ...] = (
    "ModuleCategory",
    "app_setup_func",
    "ensure_single_setup",
    "is_setup_completed",
)
