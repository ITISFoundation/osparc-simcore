# pylint:disable=unused-import

from sys import version
from typing import Final

from common_library.user_messages import user_message
from servicelib.aiohttp.application_keys import (
    APP_AIOPG_ENGINE_KEY,
    APP_CONFIG_KEY,
    APP_FIRE_AND_FORGET_TASKS_KEY,
    APP_SETTINGS_KEY,
)
from servicelib.request_keys import RQT_USERID_KEY

# Application storage keys
APP_PRODUCTS_KEY: Final[str] = f"{__name__ }.APP_PRODUCTS_KEY"

# Public config per product returned in /config
APP_PUBLIC_CONFIG_PER_PRODUCT: Final[str] = f"{__name__}.APP_PUBLIC_CONFIG_PER_PRODUCT"

FRONTEND_APPS_AVAILABLE = frozenset(
    # These are the apps built right now by static-webserver/client
    {
        "osparc",
        "s4l",
        "s4lacad",
        "s4ldesktop",
        "s4ldesktopacad",
        "s4lengine",
        "s4llite",
        "tiplite",
        "tis",
    }
)
FRONTEND_APP_DEFAULT = "osparc"

assert FRONTEND_APP_DEFAULT in FRONTEND_APPS_AVAILABLE  # nosec


# main index route name = front-end
INDEX_RESOURCE_NAME: Final[str] = "get_cached_frontend_index"

MSG_UNDER_DEVELOPMENT: Final[str] = user_message(
    "Under development. Use WEBSERVER_DEV_FEATURES_ENABLED=1 to enable current implementation"
)

# Request storage keys
RQ_PRODUCT_KEY: Final[str] = f"{__name__}.RQ_PRODUCT_KEY"


MSG_TRY_AGAIN_OR_SUPPORT: Final[str] = user_message(
    "Please try again shortly. If the issue persists, contact support.", _version=1
)

__all__: tuple[str, ...] = (
    "APP_AIOPG_ENGINE_KEY",
    "APP_CONFIG_KEY",
    "APP_FIRE_AND_FORGET_TASKS_KEY",
    "APP_SETTINGS_KEY",
    "FRONTEND_APPS_AVAILABLE",
    "FRONTEND_APP_DEFAULT",
    "RQT_USERID_KEY",
)

# nopycln: file
