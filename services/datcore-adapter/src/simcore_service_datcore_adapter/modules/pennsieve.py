import logging
from typing import List

from fastapi.applications import FastAPI
from pennsieve import Pennsieve

from ..core.settings import PennsieveSettings
from ..models.schemas.datasets import DatasetMetaData
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

logger = logging.getLogger(__name__)


class PennsieveApiClient(BaseServiceClientApi):
    async def ping(self) -> bool:
        return await self.is_responsive()

    async def get_datasets(
        self, api_key: str, api_secret: str
    ) -> List[DatasetMetaData]:
        ps = Pennsieve(api_token=api_key, api_secret=api_secret)
        pennsieve_datasets = ps.datasets()
        return [
            DatasetMetaData(id=d.id, display_name=d.name) for d in pennsieve_datasets
        ]

    async def list_dataset_files(
        self, api_key: str, api_secret: str, dataset_id: str
    ) -> List:
        ps = Pennsieve(api_token=api_key, api_secret=api_secret)
        ds = ps.get_dataset(dataset_id)
        import pdb

        pdb.set_trace()


def setup(app: FastAPI, settings: PennsieveSettings) -> None:
    setup_client_instance(
        app,
        PennsieveApiClient,
        api_baseurl=f"{settings.URL}",
        service_name="pennsieve.io",
        health_check_path="/health/",
    )
