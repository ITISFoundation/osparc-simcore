import logging
from pathlib import Path
from typing import Any, Dict, List

import pennsieve
from fastapi.applications import FastAPI
from pennsieve import Pennsieve

from ..core.settings import PennsieveSettings
from ..models.schemas.datasets import DatasetMetaData, FileMetaData
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

        async def _parse_dataset_items(
            dataset: pennsieve.models.Dataset, base_path: Path
        ) -> List[FileMetaData]:
            file_meta_data = []
            cursor = ""
            page_size = 1000
            # NOTE: this trick allows to bypass all the python parsing/slowing down of the interface
            # info given by Joost from Datcore
            ds_api = dataset._api.datasets  # pylint: disable=protected-access

            all_packages: Dict[str, Dict[str, Any]] = {}

            while resp := ds_api._get(  # pylint: disable=protected-access
                ds_api._uri(  # pylint: disable=protected-access
                    f"/{dataset_id}/packages?includeSourceFiles=false&pageSize={page_size}&cursor={cursor}"
                )
            ):
                cursor = resp.get("cursor")
                all_packages.update(
                    {p["content"]["id"]: p for p in resp.get("packages", [])}
                )
                if cursor is None:
                    # the whole collection is there now
                    break

            def _get_file_path(pck: Dict[str, Any]) -> Path:
                file_path = Path(pck["content"]["name"])
                if "extension" in pck:
                    file_path = ".".join([f"{file_path}", pck["extension"]])
                if parent_id := pck["content"].get("parentId"):
                    file_path = _get_file_path(all_packages[parent_id]) / file_path
                return file_path

            for package_id, package in all_packages.items():
                if package["content"]["packageType"] == "Collection":
                    continue

                file_path = base_path / _get_file_path(package)

                file_meta_data.append(
                    FileMetaData(
                        dataset_id=ds.id,
                        package_id=package["content"]["nodeId"],
                        id=package_id,
                        name=file_path.name,
                        path=file_path,
                        type=package["content"]["packageType"],
                        size=-1,  # no size available in this mode
                        created_at=package["content"]["createdAt"],
                        last_modified_at=package["content"]["updatedAt"],
                    )
                )

            return file_meta_data

        dataset_files = await _parse_dataset_items(ds, Path(ds.name))
        return dataset_files


def setup(app: FastAPI, settings: PennsieveSettings) -> None:
    setup_client_instance(
        app,
        PennsieveApiClient,
        api_baseurl=f"{settings.URL}",
        service_name="pennsieve.io",
        health_check_path="/health/",
    )
