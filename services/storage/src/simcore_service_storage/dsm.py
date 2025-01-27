import logging

from fastapi import FastAPI

from .constants import APP_DSM_KEY
from .datcore_dsm import DatCoreDataManager, create_datcore_data_manager
from .dsm_factory import DataManagerProvider
from .simcore_s3_dsm import SimcoreS3DataManager, create_simcore_s3_data_manager

logger = logging.getLogger(__name__)


def setup_dsm(app: FastAPI):
    async def _cleanup_context(app: FastAPI):
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
        app[APP_DSM_KEY] = dsm_provider

        yield

        logger.info("Shuting down %s", f"{dsm_provider=}")

    # ------

    app.cleanup_ctx.append(_cleanup_context)


def get_dsm_provider(app: FastAPI) -> DataManagerProvider:
    dsm_provider: DataManagerProvider = app[APP_DSM_KEY]
    return dsm_provider
