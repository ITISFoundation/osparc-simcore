import asyncio
import logging
from functools import lru_cache
from itertools import islice
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pennsieve
from fastapi.applications import FastAPI
from pennsieve import Pennsieve
from starlette.datastructures import URL

from ..core.settings import PennsieveSettings
from ..models.domains.user import Profile
from ..models.schemas.datasets import DatasetMetaData, DataType, FileMetaData
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

logger = logging.getLogger(__name__)

# NOTE: each pennsieve client seems to be about 8MB. so let's keep max 32
@lru_cache(maxsize=32)
def create_pennsieve_client(api_key: str, api_secret: str) -> Pennsieve:
    return Pennsieve(api_token=api_key, api_secret=api_secret)


def _compute_file_path(all_packages: List[Dict[str, Any]], pck: Dict[str, Any]) -> Path:
    file_path = Path(pck["content"]["name"])
    if "extension" in pck:
        file_path = ".".join([f"{file_path}", pck["extension"]])
    if parent_id := pck["content"].get("parentId"):
        file_path = (
            _compute_file_path(all_packages, all_packages[parent_id]) / file_path
        )
    return Path(file_path)


class PennsieveApiClient(BaseServiceClientApi):
    """The client uses a combination of the pennsieve official API client to authenticate,
    then uses the internal httpx-based client to call the REST API asynchronously"""

    # NOTE: this trick allows to bypass all the python parsing/slowing down of the interface
    # info given by Joost from Datcore
    async def _get_client(self, api_key: str, api_secret: str) -> Pennsieve:
        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: create_pennsieve_client(api_key=api_key, api_secret=api_secret),
        )

    async def _get_authorization_bearer_header(
        self, api_key: str, api_secret: str
    ) -> Dict[str, str]:
        ps: Pennsieve = await self._get_client(api_key=api_key, api_secret=api_secret)
        bearer_code = ps._api.token  # pylint: disable=protected-access
        return {"Authorization": f"Bearer {bearer_code}"}

    async def get_user_profile(self, api_key: str, api_secret: str) -> Profile:
        ps: Pennsieve = await self._get_client(api_key=api_key, api_secret=api_secret)
        return Profile(id=ps.profile.id)

    async def get_datasets(
        self, api_key: str, api_secret: str, limit: int, offset: int
    ) -> Tuple[Sequence, int]:
        response = await self.client.get(
            "/datasets/paginated",
            headers=await self._get_authorization_bearer_header(api_key, api_secret),
            params={
                "includeBannerUrl": False,
                "includePublishedDataset": False,
                "limit": limit,
                "offset": offset,
            },
        )
        dataset_page = response.json()

        return (
            [
                DatasetMetaData(
                    id=d["content"]["id"],
                    display_name=d["content"]["name"],
                )
                for d in dataset_page["datasets"]
            ],
            dataset_page["totalCount"],
        )

    async def get_dataset_files(
        self,
        api_key: str,
        api_secret: str,
        dataset_id: str,
        limit: int,
        offset: int,
        collection_id: Optional[str] = None,
    ) -> Tuple[Sequence, int]:
        headers = await self._get_authorization_bearer_header(api_key, api_secret)
        # get dataset details
        response = await self.client.get(
            f"/datasets/{dataset_id}",
            headers=headers,
            params={"includePublishedDataset": False},
        )
        response.raise_for_status()
        dataset_details = response.json()
        dataset_details["children"]
        logger.warning(dataset_details["children"])

        ps: Pennsieve = await self._get_client(api_key=api_key, api_secret=api_secret)
        ds: pennsieve.models.BaseCollection = ps.get_dataset(dataset_id)
        if collection_id:
            ds = ps.get(collection_id)

        return (
            [
                FileMetaData.from_pennsieve_package(ps, package)
                for package in islice(ds, offset, offset + limit)
            ],
            len(ds.items),
        )

    async def list_dataset_files(
        self, api_key: str, api_secret: str, dataset_id: str
    ) -> List:
        headers = await self._get_authorization_bearer_header(api_key, api_secret)

        async def _parse_dataset_items() -> List[FileMetaData]:
            file_meta_data = []
            cursor = ""
            page_size = 1000

            # get number of packages
            response = await self.client.get(
                f"/datasets/{dataset_id}/packageTypeCounts", headers=headers
            )
            response.raise_for_status()
            num_packages = sum(response.json().values())

            # get dataset details
            response = await self.client.get(
                f"/datasets/{dataset_id}",
                headers=headers,
                params={"includePublishedDataset": False},
            )
            response.raise_for_status()
            dataset_details = response.json()
            base_path = Path(dataset_details["content"]["name"])

            # get all data packages inside the dataset
            all_packages: Dict[str, Dict[str, Any]] = {}
            while resp := await self.client.get(
                f"/datasets/{dataset_id}/packages",
                params={
                    "includeSourceFiles": False,
                    "pageSize": page_size,
                    "cursor": cursor,
                },
                headers=headers,
            ):
                resp.raise_for_status()
                resp = resp.json()
                cursor = resp.get("cursor")
                all_packages.update(
                    {p["content"]["id"]: p for p in resp.get("packages", [])}
                )
                logger.warning(
                    "received packages [%s/%s]", len(all_packages), num_packages
                )
                if cursor is None:
                    # the whole collection is there now
                    break

            # get the information about the files
            for package_id, package in all_packages.items():
                if package["content"]["packageType"] == "Collection":
                    continue

                file_path = base_path / _compute_file_path(all_packages, package)

                file_meta_data.append(
                    FileMetaData(
                        dataset_id=package["content"]["datasetNodeId"],
                        package_id=package["content"]["nodeId"],
                        id=package_id,
                        name=file_path.name,
                        path=file_path,
                        type=package["content"]["packageType"],
                        size=-1,  # no size available in this mode
                        created_at=package["content"]["createdAt"],
                        last_modified_at=package["content"]["updatedAt"],
                        data_type=DataType.FILE,
                    )
                )

            return file_meta_data

        dataset_files = await _parse_dataset_items()
        return dataset_files

    async def get_presigned_download_link(
        self, api_key: str, api_secret: str, file_id: str
    ) -> URL:
        ps: Pennsieve = await self._get_client(api_key=api_key, api_secret=api_secret)
        dp: pennsieve.models.DataPackage = ps.get(file_id)
        assert len(dp.files) == 1  # nosec
        file: pennsieve.models.File = dp.files[0]

        return URL(file.url)


def setup(app: FastAPI, settings: PennsieveSettings) -> None:
    setup_client_instance(
        app,
        PennsieveApiClient,
        api_baseurl=f"{settings.URL}",
        service_name="pennsieve.io",
        health_check_path="/health/",
    )
