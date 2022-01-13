#
# pylint:disable=unused-import
#

from typing import Final

# Application storage keys
APP_PRODUCTS_KEY: Final[str] = f"{__name__ }.products"


# Request storage keys
RQ_PRODUCT_KEY: Final[str] = f"{__name__}.product"
RQ_PRODUCT_FRONTEND_KEY: Final[str] = f"{__name__}.product_frontend"

# Headers keys
X_PRODUCT_NAME_HEADER: Final[str] = "X-Simcore-Products-Name"

# main index route name = front-end
INDEX_RESOURCE_NAME: Final[str] = "statics.index"
