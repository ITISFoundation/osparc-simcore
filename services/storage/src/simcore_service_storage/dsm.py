import logging
from typing import cast

from fastapi import FastAPI

from .datcore_dsm import DatCoreDataManager, create_datcore_data_manager
from .dsm_factory import DataManagerProvider
from .exceptions.errors import ConfigurationError
from .simcore_s3_dsm import SimcoreS3DataManager, create_simcore_s3_data_manager

logger = logging.getLogger(__name__)


def setup_dsm(app: FastAPI):
    async def _on_startup(app: FastAPI) -> None:
        dsm_provider = DataManagerProvider(app)
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

    async def _on_shutdown() -> None:
        if app.state.dsm_provider:
            # nothing to do
            ...

    # ------

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


def get_dsm_provider(app: FastAPI) -> DataManagerProvider:
    if not app.state.dsm_provider:
        raise ConfigurationError(
            msg="DSM provider not available. Please check the configuration."
        )
    return cast(DataManagerProvider, app.state.dsm_provider)
