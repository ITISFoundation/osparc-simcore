import asyncio
import logging
import typing
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any, Final, TypedDict, cast

import boto3
from aiocache import SimpleMemoryCache  # type: ignore[import-untyped]
from fastapi.applications import FastAPI
from models_library.api_schemas_datcore_adapter.datasets import (
    DatasetMetaData,
    DataType,
    FileMetaData,
)
from pydantic import ByteSize
from servicelib.logging_utils import log_context
from servicelib.utils import logged_gather
from starlette import status
from starlette.datastructures import URL
from tenacity import TryAgain, retry
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt

from ..core.settings import PennsieveSettings
from ..models.files import DatCorePackageMetaData
from ..models.user import Profile
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

logger = logging.getLogger(__name__)

Total = int
_GATHER_MAX_CONCURRENCY = 10


def _to_file_meta_data(
    package: dict[str, Any], files: list[DatCorePackageMetaData], base_path: Path
) -> FileMetaData:
    """creates a FileMetaData from a pennsieve data structure."""
    pck_name: str = package["content"]["name"]
    if "extension" in package and not pck_name.endswith(package["extension"]):
        pck_name += ".".join((pck_name, package["extension"]))

    file_size = 0
    if package["content"]["packageType"] != "Collection" and files:
        file_size = files[0].size

    return FileMetaData(
        dataset_id=package["content"]["datasetNodeId"],
        package_id=package["content"]["nodeId"],
        id=f"{package['content']['id']}",
        name=pck_name,
        path=base_path / pck_name,
        type=package["content"]["packageType"],
        size=file_size,
        created_at=package["content"]["createdAt"],
        last_modified_at=package["content"]["updatedAt"],
        data_type=(
            DataType.FOLDER
            if package["content"]["packageType"] == "Collection"
            else DataType.FILE
        ),
    )


def _compute_file_path(
    all_packages: dict[str, dict[str, Any]], pck: dict[str, Any]
) -> Path:
    file_path = Path(pck["content"]["name"])
    if "extension" in pck:
        file_path = Path(".".join((f"{file_path}", pck["extension"])))
    if parent_id := pck["content"].get("parentId"):
        file_path = (
            _compute_file_path(all_packages, all_packages[parent_id]) / file_path
        )
    return Path(file_path)


class PennsieveAuthorizationHeaders(TypedDict):
    Authorization: str


_TTL_CACHE_AUTHORIZATION_HEADERS_SECONDS: Final[int] = (
    3530  # NOTE: observed while developing this code, pennsieve authorizes 3600 seconds, so we cache a bit less
)

ExpirationTimeSecs = int


def _get_bearer_code(
    cognito_config: dict[str, Any], api_key: str, api_secret: str
) -> tuple[PennsieveAuthorizationHeaders, ExpirationTimeSecs]:
    """according to https://docs.pennsieve.io/recipes
    ..."""
    session = boto3.Session()  # NOTE: needed since boto3 client is not thread safe
    cognito_client = session.client(
        "cognito-idp",
        region_name=cognito_config["region"],
        aws_access_key_id="",
        aws_secret_access_key="",
    )
    login_response = cognito_client.initiate_auth(
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": api_key, "PASSWORD": api_secret},
        ClientId=cognito_config["tokenPool"]["appClientId"],
    )
    bearer_code = login_response["AuthenticationResult"]["AccessToken"]
    expiration_time = login_response["AuthenticationResult"]["ExpiresIn"]
    return (
        PennsieveAuthorizationHeaders(Authorization=f"Bearer {bearer_code}"),
        expiration_time,
    )


@dataclass
class PennsieveApiClient(BaseServiceClientApi):
    """The client uses the internal httpx-based client to call the REST API asynchronously"""

    _bearer_cache = SimpleMemoryCache()

    async def _get_authorization_headers(
        self, api_key: str, api_secret: str
    ) -> PennsieveAuthorizationHeaders:
        """returns the authorization bearer code as described
        in the pennsieve recipe
        https://docs.pennsieve.io/recipes

        with fixes coming from the python pennsieve library to
        correct the issue in the above mentioned recipe
        """
        # get Pennsieve cognito configuration
        if pennsieve_header := await self._bearer_cache.get(f"{api_key}_{api_secret}"):
            return typing.cast(PennsieveAuthorizationHeaders, pennsieve_header)

        with log_context(
            logger, logging.DEBUG, msg="getting new authorization headers"
        ):
            response = await self.client.get("/authentication/cognito-config")
            response.raise_for_status()
            cognito_config = response.json()
            (
                pennsieve_header,
                expiration_time,
            ) = await asyncio.get_event_loop().run_in_executor(
                None, _get_bearer_code, cognito_config, api_key, api_secret
            )

        await self._bearer_cache.set(
            f"{api_key}_{api_secret}", pennsieve_header, ttl=expiration_time - 30
        )

        return typing.cast(PennsieveAuthorizationHeaders, pennsieve_header)

    @retry(
        stop=stop_after_attempt(2),
        retry=retry_if_exception_type(TryAgain),
        before_sleep=before_sleep_log(logger=logger, log_level=logging.WARNING),
    )
    async def _request(
        self,
        api_key: str,
        api_secret: str,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        response = await self.client.request(
            method,
            path,
            headers=cast(
                dict[str, str],
                await self._get_authorization_headers(api_key, api_secret),
            ),
            params=params,
            json=json,
        )
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            # NOTE: the cached bearer code might be expired
            await self._bearer_cache.delete(f"{api_key}_{api_secret}")
            raise TryAgain
        response.raise_for_status()
        return response.json()

    async def _get_dataset_packages_count(
        self, api_key: str, api_secret: str, dataset_id: str
    ) -> Total:
        package_type_counts = cast(
            dict[str, Any],
            await self._request(
                api_key, api_secret, "GET", f"/datasets/{dataset_id}/packageTypeCounts"
            ),
        )
        return sum(package_type_counts.values())

    async def _get_dataset(
        self, api_key: str, api_secret: str, dataset_id: str
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
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
        cursor: str | None,
    ) -> dict[str, Any]:
        packages = cast(
            dict[str, Any],
            await self._request(
                api_key,
                api_secret,
                "GET",
                f"/datasets/{dataset_id}/packages",
                params={
                    "includeSourceFiles": False,
                    "pageSize": page_size,
                    "cursor": cursor if cursor is not None else "",
                },
            ),
        )
        packages["packages"] = [
            f for f in packages["packages"] if f["content"]["state"] != "DELETED"
        ]
        return packages

    async def _get_package(
        self, api_key: str, api_secret: str, package_id: str
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await self._request(
                api_key,
                api_secret,
                "GET",
                f"/packages/{package_id}",
                params={"includeAncestors": True},
            ),
        )

    async def get_package_files(
        self,
        *,
        api_key: str,
        api_secret: str,
        package_id: str,
        limit: int,
        offset: int,
        fill_path: bool,
    ) -> list[DatCorePackageMetaData]:
        raw_data = await self._request(
            api_key,
            api_secret,
            "GET",
            f"/packages/{package_id}/files",
            params={"limit": limit, "offset": offset},
        )
        path = display_path = Path()
        if fill_path:
            package_info = await self._get_package(api_key, api_secret, package_id)
            dataset_id = package_info["content"]["datasetId"]
            dataset = await self._get_dataset(api_key, api_secret, dataset_id)

            path = (
                Path(dataset_id)
                / Path(
                    "/".join(
                        ancestor["content"]["id"]
                        for ancestor in package_info.get("ancestors", [])
                    )
                )
                / Path(package_info["content"]["name"])
            )
            display_path = (
                Path(dataset["content"]["name"])
                / Path(
                    "/".join(
                        ancestor["content"]["name"]
                        for ancestor in package_info.get("ancestors", [])
                    )
                )
                / Path(package_info["content"]["name"])
            )

        return [
            DatCorePackageMetaData(**_["content"], path=path, display_path=display_path)
            for _ in raw_data
        ]

    async def _get_pck_id_files(
        self, api_key: str, api_secret: str, pck_id: str, pck: dict[str, Any]
    ) -> tuple[str, list[DatCorePackageMetaData]]:
        return (
            pck_id,
            await self.get_package_files(
                api_key=api_key,
                api_secret=api_secret,
                package_id=pck["content"]["nodeId"],
                limit=1,
                offset=0,
                fill_path=False,
            ),
        )

    async def get_user_profile(self, api_key: str, api_secret: str) -> Profile:
        """returns the user profile id"""
        pennsieve_user = cast(
            dict[str, Any], await self._request(api_key, api_secret, "GET", "/user/")
        )

        return Profile(id=pennsieve_user["id"])

    async def list_datasets(
        self, api_key: str, api_secret: str, limit: int, offset: int
    ) -> tuple[list[DatasetMetaData], Total]:
        """returns all the datasets a user has access to"""
        dataset_page = cast(
            dict[str, Any],
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
                    size=(
                        ByteSize(sz)
                        if (sz := d.get("storage", 0)) > 0  # NOSONAR
                        else None
                    ),
                )
                for d in dataset_page["datasets"]
            ],
            dataset_page["totalCount"],
        )

    async def get_dataset(
        self, api_key: str, api_secret: str, dataset_id: str
    ) -> DatasetMetaData:
        dataset_pck = await self._get_dataset(api_key, api_secret, dataset_id)
        return DatasetMetaData(
            id=dataset_pck["content"]["id"],
            display_name=dataset_pck["content"]["name"],
            size=(
                ByteSize(dataset_pck["storage"]) if dataset_pck["storage"] > 0 else None
            ),
        )

    async def list_packages_in_dataset(
        self,
        api_key: str,
        api_secret: str,
        dataset_id: str,
        limit: int,
        offset: int,
    ) -> tuple[list, Total]:
        dataset_pck = await self._get_dataset(api_key, api_secret, dataset_id)
        # get the information about the files
        package_files_tasks = [
            self._get_pck_id_files(api_key, api_secret, pck["content"]["id"], pck)
            for pck in islice(dataset_pck["children"], offset, offset + limit)
            if pck["content"]["packageType"] != "Collection"
        ]
        package_files: dict[str, list[DatCorePackageMetaData]] = dict(
            await logged_gather(
                *package_files_tasks,
                log=logger,
                max_concurrency=_GATHER_MAX_CONCURRENCY,
            )
        )
        return (
            [
                _to_file_meta_data(
                    pck,
                    (
                        package_files[pck["content"]["id"]]
                        if pck["content"]["packageType"] != "Collection"
                        else []
                    ),
                    base_path=Path(dataset_pck["content"]["name"]),
                )
                for pck in islice(dataset_pck["children"], offset, offset + limit)
            ],
            len(dataset_pck["children"]),
        )

    async def list_packages_in_collection(
        self,
        api_key: str,
        api_secret: str,
        dataset_id: str,
        collection_id: str,
        limit: int,
        offset: int,
    ) -> tuple[list, Total]:
        dataset = await self._get_dataset(api_key, api_secret, dataset_id)
        collection_pck = await self._get_package(api_key, api_secret, collection_id)
        # compute base path ancestors are ordered
        base_path = Path(dataset["content"]["name"]) / (
            Path(
                "/".join(
                    ancestor_pck["content"]["name"]
                    for ancestor_pck in collection_pck["ancestors"]
                )
            )
            / collection_pck["content"]["name"]
        )
        # get the information about the files
        package_files_tasks = [
            self._get_pck_id_files(api_key, api_secret, pck["content"]["id"], pck)
            for pck in islice(collection_pck["children"], offset, offset + limit)
            if pck["content"]["packageType"] != "Collection"
        ]
        package_files = dict(
            await logged_gather(
                *package_files_tasks,
                log=logger,
                max_concurrency=_GATHER_MAX_CONCURRENCY,
            )
        )

        return (
            [
                _to_file_meta_data(
                    pck,
                    (
                        package_files[pck["content"]["id"]]
                        if pck["content"]["packageType"] != "Collection"
                        else []
                    ),
                    base_path=base_path,
                )
                for pck in islice(collection_pck["children"], offset, offset + limit)
            ],
            len(collection_pck["children"]),
        )

    async def list_all_dataset_files(
        self, api_key: str, api_secret: str, dataset_id: str
    ) -> list[FileMetaData]:
        """returns ALL the files belonging to the dataset, can be slow if there are a lot of files"""

        file_meta_data: list[FileMetaData] = []
        cursor: str | None = ""
        PAGE_SIZE = 1000

        num_packages, dataset_details = await logged_gather(
            self._get_dataset_packages_count(api_key, api_secret, dataset_id),
            self._get_dataset(api_key, api_secret, dataset_id),
            log=logger,
        )
        base_path = Path(dataset_details["content"]["name"])

        # get all data packages inside the dataset
        all_packages: dict[str, dict[str, Any]] = {}
        while resp := await self._get_dataset_packages(
            api_key, api_secret, dataset_id, PAGE_SIZE, cursor
        ):
            cursor = resp.get("cursor")
            assert isinstance(cursor, str | None)  # nosec
            all_packages.update(
                {p["content"]["id"]: p for p in resp.get("packages", [])}
            )
            logger.debug(
                "received dataset packages [%s/%s], cursor: %s",
                len(all_packages),
                num_packages,
                cursor,
            )

            if cursor is None:
                # the whole collection is there now
                break

        # get the information about the files
        package_files_tasks = [
            self._get_pck_id_files(api_key, api_secret, pck_id, pck_data)
            for pck_id, pck_data in all_packages.items()
            if pck_data["content"]["packageType"] != "Collection"
        ]
        with log_context(
            logger=logger,
            level=logging.DEBUG,
            msg=f"fetching {len(package_files_tasks)} file information",
        ):
            package_files = dict(
                await logged_gather(
                    *package_files_tasks,
                    log=logger,
                    max_concurrency=_GATHER_MAX_CONCURRENCY,
                )
            )
        with log_context(
            logger=logger,
            level=logging.DEBUG,
            msg=f"fetching {len(all_packages) - len(package_files_tasks)} collection information",
        ):
            for package_id, package in all_packages.items():
                if package["content"]["packageType"] == "Collection":
                    continue

                file_path = base_path / _compute_file_path(all_packages, package)

                file_meta_data.append(
                    _to_file_meta_data(
                        package, package_files[package_id], file_path.parent
                    )
                )

        return file_meta_data

    async def get_presigned_download_link(
        self, api_key: str, api_secret: str, package_id: str
    ) -> URL:
        """returns the presigned download link of the first file in the package"""
        files = await self.get_package_files(
            api_key=api_key,
            api_secret=api_secret,
            package_id=package_id,
            limit=1,
            offset=0,
            fill_path=False,
        )
        # NOTE: this was done like this in the original dsm. we might encounter a problem when there are more than one files
        assert len(files) == 1  # nosec
        file_id = files[0].id
        file_link = cast(
            dict[str, Any],
            await self._request(
                api_key, api_secret, "GET", f"/packages/{package_id}/files/{file_id}"
            ),
        )
        return URL(file_link["url"])

    async def delete_object(self, api_key: str, api_secret: str, obj_id: str) -> None:
        """deletes the file in datcore"""
        await self._request(
            api_key, api_secret, "POST", "/data/delete", json={"things": [obj_id]}
        )


def setup(app: FastAPI, settings: PennsieveSettings) -> None:
    setup_client_instance(
        app,
        PennsieveApiClient,
        api_baseurl=f"{settings.PENNSIEVE_API_URL}",
        api_general_timeout=settings.PENNSIEVE_API_GENERAL_TIMEOUT,
        service_name="pennsieve.io",
        health_check_path="/health/",
        health_check_timeout=settings.PENNSIEVE_HEALTCHCHECK_TIMEOUT,
    )
