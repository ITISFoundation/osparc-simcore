#
# pylint:disable=unused-import
#

from servicelib.aiohttp.application_keys import (
    APP_CONFIG_KEY,
    APP_DB_ENGINE_KEY,
    APP_JSONSCHEMA_SPECS_KEY,
    APP_OPENAPI_SPECS_KEY,
)
from servicelib.request_keys import RQT_USERID_KEY

# Application storage keys
APP_SETTINGS_KEY = f"{__name__ }.app_settings"
APP_PRODUCTS_KEY = f"{__name__ }.products"


# Request storage keys
RQ_PRODUCT_KEY = f"{__name__}.product"
RQ_PRODUCT_FRONTEND_KEY = f"{__name__}.product_frontend"

# Headers keys
X_PRODUCT_NAME_HEADER = "X-Simcore-Products-Name"

# main index route name = front-end
INDEX_RESOURCE_NAME = "statics.index"
