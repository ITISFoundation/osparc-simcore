import functools

import servicelib.aiohttp.application_setup
from servicelib.aiohttp.application_setup import ModuleCategory, ensure_single_setup

from .constants import APP_SETTINGS_KEY

# models
assert ModuleCategory  # nosec


# decorators
assert callable(ensure_single_setup)  # nosec

app_setup_func = functools.partial(
    servicelib.aiohttp.application_setup.app_module_setup,
    app_settings_key=APP_SETTINGS_KEY,
)

__all__: tuple[str, ...] = (
    "ModuleCategory",
    "app_setup_func",
    "ensure_single_setup",
)
