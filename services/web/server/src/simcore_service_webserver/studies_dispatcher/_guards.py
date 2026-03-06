"""Guard functions for studies dispatcher access control."""

import logging

from aiohttp import web

from ..products import products_web

_logger = logging.getLogger(__name__)


def check_studies_dispatcher_enabled(request: web.Request) -> None:
    """
    Guard function to check if studies dispatcher is enabled for the current product.

    The dispatcher feature is controlled at two levels:
    1. **Global**: `STUDIES_ACCESS_ANONYMOUS_ALLOWED` environment variable (startup)
    2. **Per-Product**: `product.studies_dispatcher_enabled` database column (runtime)

    When `studies_dispatcher_enabled=False` for a product, accessing dispatcher endpoints
    returns HTTP 404 directly (not an error redirect), preventing any access regardless
    of the global setting.

    **Access Control Layer**:
    - Global setting can be OFF but product flag ON → dispatcher disabled (global wins)
    - Global setting can be ON but product flag OFF → dispatcher disabled (product wins)
    - Both must be ON for feature to work

    This design allows independent control:
    - Infrastructure teams set global policy
    - Product managers enable/disable per-product at runtime
    - No startup warnings needed (permissive model)

    Args:
        request: aiohttp request

    Raises:
        web.HTTPNotFound: If studies dispatcher is disabled for the current product
    """
    product = products_web.get_current_product(request)
    if not product.studies_dispatcher_enabled:
        _logger.debug("Studies dispatcher is disabled for product %s", product.name)
        raise web.HTTPNotFound(reason="Studies dispatcher is not available for this product")
