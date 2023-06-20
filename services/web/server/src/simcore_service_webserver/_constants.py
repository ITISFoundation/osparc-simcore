# pylint:disable=unused-import
# nopycln: file

from typing import Final

from servicelib.aiohttp.application_keys import (
    APP_CONFIG_KEY,
    APP_DB_ENGINE_KEY,
    APP_FIRE_AND_FORGET_TASKS_KEY,
    APP_OPENAPI_SPECS_KEY,
    APP_SETTINGS_KEY,
)
from servicelib.request_keys import RQT_USERID_KEY

# Application storage keys
APP_PRODUCTS_KEY: Final[str] = f"{__name__ }.APP_PRODUCTS_KEY"

# Request storage keys
RQ_PRODUCT_KEY: Final[str] = f"{__name__}.RQ_PRODUCT_KEY"

# Headers keys
X_PRODUCT_NAME_HEADER: Final[str] = "X-Simcore-Products-Name"

# main index route name = front-end
INDEX_RESOURCE_NAME: Final[str] = "statics.index"

# Public config per product returned in /config
APP_PUBLIC_CONFIG_PER_PRODUCT: Final[str] = f"{__name__}.APP_PUBLIC_CONFIG_PER_PRODUCT"

MSG_UNDER_DEVELOPMENT: Final[
    str
] = "Under development. Use WEBSERVER_DEV_FEATURES_ENABLED=1 to enable current implementation"


__all__: tuple[str, ...] = (
    "APP_CONFIG_KEY",
    "APP_DB_ENGINE_KEY",
    "APP_FIRE_AND_FORGET_TASKS_KEY",
    "APP_OPENAPI_SPECS_KEY",
    "APP_SETTINGS_KEY",
    "RQT_USERID_KEY",
)
