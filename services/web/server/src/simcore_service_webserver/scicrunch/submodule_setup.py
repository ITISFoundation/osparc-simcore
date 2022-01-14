"""
    Notice that this is used as a submodule of groups'a app module
"""
import logging
from typing import Any, MutableMapping, Optional

from pydantic import ValidationError

from ._settings import SciCrunchSettings
from .service_client import SciCrunch

logger = logging.getLogger(__name__)


def setup_scicrunch_submodule(
    app: MutableMapping[str, Any], *, cfg: Optional[SciCrunchSettings] = None
):
    try:
        cfg = SciCrunchSettings()
        api = SciCrunch.acquire_instance(app, cfg)
        assert api == SciCrunch.get_instance(app)  # nosec

    except ValidationError as err:
        logger.warning(
            "Failed to setup interface with K-Core. This functionality will not be available: %s",
            err,
        )
