#
# pylint:disable=unused-import
#

from servicelib.application_keys import (
    APP_CONFIG_KEY,
    APP_DB_ENGINE_KEY,
    APP_JSONSCHEMA_SPECS_KEY,
)

# Application storage keys
APP_SETTINGS_KEY = f"{__name__ }.app_settings"
APP_PRODUCTS_KEY = f"{__name__ }.products"


# Request storage keys
RQ_PRODUCT_KEY = f"{__name__}.product"
RQ_PRODUCT_FRONTEND_KEY = f"{__name__}.product_frontend"

# Headers keys
X_PRODUCT_NAME_HEADER = "X-Simcore-Products-Name"
