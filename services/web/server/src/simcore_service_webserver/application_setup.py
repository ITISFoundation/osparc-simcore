import functools

import servicelib.aiohttp.application_setup

from .constants import APP_SETTINGS_KEY

ensure_single_setup = servicelib.aiohttp.application_setup.ensure_single_setup
app_setup_func = functools.partial(
    servicelib.aiohttp.application_setup.app_module_setup,
    app_settings_key=APP_SETTINGS_KEY,
)


__all__: tuple[str, ...] = (
    "app_setup_func",
    "ensure_single_setup",
)
