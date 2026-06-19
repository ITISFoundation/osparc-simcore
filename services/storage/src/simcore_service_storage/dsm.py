import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager

from .datcore_dsm import DatCoreDataManager, create_datcore_data_manager
from .dsm_factory import DataManagerProvider
from .exceptions.errors import ConfigurationError
from .simcore_s3_dsm import SimcoreS3DataManager, create_simcore_s3_data_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _dsm_provider_lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Lifespan context manager for DSM provider."""
    app.state.dsm_provider = None

    try:
        dsm_provider = DataManagerProvider(app=app)
        dsm_provider.register_builder(
            SimcoreS3DataManager.get_location_id(),
            create_simcore_s3_data_manager,
            SimcoreS3DataManager,
        )
        dsm_provider.register_builder(
            DatCoreDataManager.get_location_id(),
            create_datcore_data_manager,
            DatCoreDataManager,
        )
        app.state.dsm_provider = dsm_provider

        yield
    finally:
        pass


def configure_dsm_provider(app_lifespan: LifespanManager) -> None:
    """Configure DSM provider lifespan."""
    app_lifespan.add(_dsm_provider_lifespan)


def get_dsm_provider(app: FastAPI) -> DataManagerProvider:
    if not hasattr(app.state, "dsm_provider"):
        raise ConfigurationError(msg="DSM provider not available. Please check the configuration.")
    return cast(DataManagerProvider, app.state.dsm_provider)
