"""
   Submodule to interact with K-Core's scicrunch API (https://scicrunch.org/api/)
"""
import logging
from typing import Any, MutableMapping

from pydantic import ValidationError

from .scicrunch_api import SciCrunchAPI
from .scicrunch_config import SciCrunchSettings

logger = logging.getLogger(__name__)


def setup_scicrunch(app: MutableMapping[str, Any]):
    try:
        cfg = SciCrunchSettings()
        api = SciCrunchAPI.acquire_instance(app, cfg)
        assert api == SciCrunchAPI.get_instance(app)  # nosec
    except ValidationError as err:
        logger.warning(
            "Failed to setup interface with K-Core. This functionality will not be available: %s",
            err,
        )
