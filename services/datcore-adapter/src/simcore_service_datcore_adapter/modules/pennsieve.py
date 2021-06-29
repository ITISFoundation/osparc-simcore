import asyncio
import logging
from functools import lru_cache
from itertools import islice
from pathlib import Path
from pprint import pformat
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union, cast

import pennsieve
from fastapi.applications import FastAPI
from pennsieve import Pennsieve
from starlette.datastructures import URL

from ..core.settings import PennsieveSettings
from ..models.domains.user import Profile
from ..models.schemas.datasets import DatasetMetaData, DataType, FileMetaData
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

logger = logging.getLogger(__name__)


async def _get_pennsieve_client(api_key: str, api_secret: str) -> Pennsieve:
    # NOTE: each pennsieve client seems to be about 8MB. so let's keep max 32
    @lru_cache(maxsize=32)
    def create_pennsieve_client(api_key: str, api_secret: str) -> Pennsieve:
        return Pennsieve(api_token=api_key, api_secret=api_secret)

    return await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: create_pennsieve_client(api_key=api_key, api_secret=api_secret),
    )


async def _get_authorization_headers(api_key: str, api_secret: str) -> Dict[str, str]:
    ps: Pennsieve = await _get_pennsieve_client(api_key=api_key, api_secret=api_secret)
    bearer_code = ps._api.token  # pylint: disable=protected-access
    return {"Authorization": f"Bearer {bearer_code}"}


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

    async def _request(
        self,
        api_key: str,
        api_secret: str,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        response = await self.client.request(
            method,
            path,
            headers=await _get_authorization_headers(api_key, api_secret),
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def _get_dataset_packages_count(
        self, api_key: str, api_secret: str, dataset_id: str
    ) -> int:
        package_type_counts = cast(
            Dict[str, Any],
            await self._request(
                api_key, api_secret, "GET", f"/datasets/{dataset_id}/packageTypeCounts"
            ),
        )
        return sum(package_type_counts.values())

    async def _get_dataset(
        self, api_key: str, api_secret: str, dataset_id: str
    ) -> Dict[str, Any]:
        return cast(
            Dict[str, Any],
            await self._request(
                api_key,
                api_secret,
                "GET",
                f"/datasets/{dataset_id}",
                params={"includePublishedDataset": False},
            ),
        )

    async def _get_dataset_packages(
        self,
        api_key: str,
        api_secret: str,
        dataset_id: str,
        page_size: int,
        cursor: str,
    ) -> Dict[str, Any]:
        return cast(
            Dict[str, Any],
            await self._request(
                api_key,
                api_secret,
                "GET",
                f"/datasets/{dataset_id}/packages",
                params={
                    "includeSourceFiles": False,
                    "pageSize": page_size,
                    "cursor": cursor,
                },
            ),
        )

    async def _get_package(
        self, api_key: str, api_secret: str, package_id: str
    ) -> Dict[str, Any]:
        return cast(
            Dict[str, Any],
            await self._request(
                api_key,
                api_secret,
                "GET",
                f"/packages/{package_id}",
            ),
        )

    async def _get_package_files(
        self, api_key: str, api_secret: str, package_id: str
    ) -> List[Dict[str, Any]]:
        return cast(
            List[Dict[str, Any]],
            await self._request(
                api_key,
                api_secret,
                "GET",
                f"/packages/{package_id}/files",
            ),
        )

    async def get_user_profile(self, api_key: str, api_secret: str) -> Profile:
        ps: Pennsieve = await _get_pennsieve_client(
            api_key=api_key, api_secret=api_secret
        )
        return Profile(id=ps.profile.id)

    async def get_datasets(
        self, api_key: str, api_secret: str, limit: int, offset: int
    ) -> Tuple[Sequence, int]:
        dataset_page = cast(
            Dict[str, Any],
            await self._request(
                api_key,
                api_secret,
                "GET",
                "/datasets/paginated",
                params={
                    "includeBannerUrl": False,
                    "includePublishedDataset": False,
                    "limit": limit,
                    "offset": offset,
                },
            ),
        )

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
        headers = await _get_authorization_headers(api_key, api_secret)
        # get dataset or collection details
        url = (
            f"/packages/{collection_id}" if collection_id else f"/datasets/{dataset_id}"
        )
        params = (
            {"includeAncestors": False}
            if collection_id
            else {"includePublishedDataset": False}
        )
        response = await self.client.get(
            url,
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        package_details = response.json()

        return (
            [
                FileMetaData.from_pennsieve_api_package(package)
                for package in islice(
                    package_details["children"], offset, offset + limit
                )
            ],
            len(package_details["children"]),
        )

    async def list_dataset_files(
        self, api_key: str, api_secret: str, dataset_id: str
    ) -> List:
        async def _parse_dataset_items() -> List[FileMetaData]:
            file_meta_data = []
            cursor = ""
            page_size = 1000

            # get number of packages
            num_packages = await self._get_dataset_packages_count(
                api_key, api_secret, dataset_id
            )

            # get dataset details
            dataset_details = await self._get_dataset(api_key, api_secret, dataset_id)
            base_path = Path(dataset_details["content"]["name"])

            # get all data packages inside the dataset
            all_packages: Dict[str, Dict[str, Any]] = {}
            while resp := await self._get_dataset_packages(
                api_key, api_secret, dataset_id, page_size, cursor
            ):
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
        self, api_key: str, api_secret: str, package_id: str
    ) -> URL:
        files = await self._get_package_files(api_key, api_secret, package_id)

        # NOTE: this was done like this in the original dsm. we might encounter a problem when there are more than one files
        assert len(files) == 1  # nosec
        file_id = files[0]["content"]["id"]
        file_link = cast(
            Dict[str, Any],
            await self._request(
                api_key, api_secret, "GET", f"/packages/{package_id}/files/{file_id}"
            ),
        )
        return URL(file_link["url"])


def setup(app: FastAPI, settings: PennsieveSettings) -> None:
    setup_client_instance(
        app,
        PennsieveApiClient,
        api_baseurl=f"{settings.URL}",
        service_name="pennsieve.io",
        health_check_path="/health/",
    )
