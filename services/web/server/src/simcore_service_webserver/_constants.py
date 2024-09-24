# pylint:disable=unused-import
# nopycln: file

from typing import Final

from servicelib.aiohttp.application_keys import (
    APP_AIOPG_ENGINE_KEY,
    APP_CONFIG_KEY,
    APP_FIRE_AND_FORGET_TASKS_KEY,
    APP_SETTINGS_KEY,
)
from servicelib.request_keys import RQT_USERID_KEY

# Application storage keys
APP_PRODUCTS_KEY: Final[str] = f"{__name__ }.APP_PRODUCTS_KEY"

# Request storage keys
RQ_PRODUCT_KEY: Final[str] = f"{__name__}.RQ_PRODUCT_KEY"

# main index route name = front-end
INDEX_RESOURCE_NAME: Final[str] = "get_cached_frontend_index"

# Public config per product returned in /config
APP_PUBLIC_CONFIG_PER_PRODUCT: Final[str] = f"{__name__}.APP_PUBLIC_CONFIG_PER_PRODUCT"

MSG_UNDER_DEVELOPMENT: Final[
    str
] = "Under development. Use WEBSERVER_DEV_FEATURES_ENABLED=1 to enable current implementation"


FMSG_SERVER_EXCEPTION_LOG: Final[
    # formatted message for _logger.exception(...)
    # Use these keys as guidance to provide necessary information for a good error message log
    #
    # user_msg: message seem by front-end user (should include OEC)
    # exc: handled exception
    # ctx: exception context e.g. exc.ctx()  (see OsparcErrorMixin)
    # tip: tips on why this might have happened and or possible solution
    #
    str
] = "{user_msg}.\nERROR: {exc}.\nCONTEXT: {ctx}.\nTIP: {tip}\n"


__all__: tuple[str, ...] = (
    "APP_CONFIG_KEY",
    "APP_AIOPG_ENGINE_KEY",
    "APP_FIRE_AND_FORGET_TASKS_KEY",
    "APP_SETTINGS_KEY",
    "RQT_USERID_KEY",
)
