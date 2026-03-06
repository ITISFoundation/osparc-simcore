"""Guard functions for studies dispatcher access control."""

import logging

from aiohttp import web

from ..products import products_web

_logger = logging.getLogger(__name__)


def check_studies_dispatcher_enabled(request: web.Request) -> None:
    """
    Guard function to check if studies dispatcher feature is enabled for the current product.

    This guard checks the **per-product feature flag** (`product.studies_dispatcher_enabled`)
    which controls whether the dispatcher feature is available for a specific product.

    **Note**: This is orthogonal to authentication requirements:
    - This guard controls **feature availability** (on/off per product)
    - `STUDIES_ACCESS_ANONYMOUS_ALLOWED` controls **authentication requirements** (login vs anonymous)

    When a product has `studies_dispatcher_enabled=False`, the dispatcher feature is disabled
    and this guard raises HTTP 404, preventing any access to dispatcher endpoints for that product.

    **Design rationale**:
    - Product managers can enable/disable dispatcher per-product at runtime (via database)
    - Returns 404 (not error page) to indicate feature unavailability
    - Independent of whether login is required (set by STUDIES_ACCESS_ANONYMOUS_ALLOWED)

    Args:
        request: aiohttp request

    Raises:
        web.HTTPNotFound: If studies dispatcher is disabled for the current product
    """
    product = products_web.get_current_product(request)
    if not product.studies_dispatcher_enabled:
        _logger.debug("Studies dispatcher is disabled for product %s", product.name)
        raise web.HTTPNotFound(reason="Studies dispatcher is not available for this product")
