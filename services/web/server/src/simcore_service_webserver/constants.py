#
# pylint:disable=unused-import
#

from servicelib.application_keys import APP_DB_ENGINE_KEY

# Application storage keys
APP_SETTINGS_KEY = f"{__name__ }.app_settings"
APP_PRODUCTS_KEY = f"{__name__ }.products"

# Request storage keys
RQ_PRODUCT_KEY = f"{__name__}.product"

# Headers keys
X_PRODUCT_NAME_HEADER = "X-Simcore-Products-Name"
X_PRODUCT_IDENTIFIER_HEADER = (
    "X-Simcore-Products-Identifier"  # could be given to the front-end
)
