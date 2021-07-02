import asyncio
import logging
from math import ceil
from typing import Any, Callable, Dict, List, Optional, Type, Union, cast

import aiohttp
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.client_session import ClientSession, get_client_session
from yarl import URL

from ..constants import DATCORE_ID, DATCORE_STR
from ..models import DatasetMetaData, FileMetaData, FileMetaDataEx
from .datcore_adapter_exceptions import (
    DatcoreAdapterClientError,
    DatcoreAdapterException,
)

log = logging.getLogger(__file__)


class _DatcoreAdapterResponseError(DatcoreAdapterException):
    """Basic exception for response errors"""

    def __init__(self, status: int, reason: str) -> None:
        self.status = status
        self.reason = reason
        super().__init__(
            msg=f"forwarded call failed with status {status}, reason {reason}"
        )


async def _request(
    app: aiohttp.web.Application,
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    json: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    datcore_adapter_settings = app[APP_CONFIG_KEY].DATCORE_ADAPTER
    url = datcore_adapter_settings.endpoint + path
    session: ClientSession = get_client_session(app)

    try:

        async with session.request(
            method,
            url,
            raise_for_status=True,
            headers={
                "x-datcore-api-key": api_key,
                "x-datcore-api-secret": api_secret,
            },
            json=json,
            params=params,
        ) as response:
            return await response.json()
    except aiohttp.ClientResponseError as exc:
        raise _DatcoreAdapterResponseError(status=exc.status, reason=f"{exc}") from exc
    except TimeoutError as exc:
        raise DatcoreAdapterClientError("datcore-adapter server timed-out") from exc
    except aiohttp.ClientError as exc:
        raise DatcoreAdapterClientError(f"unexpected client error: {exc}") from exc


async def _retrieve_all_pages(
    app: aiohttp.web.Application,
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    return_type: Type,
    return_type_creator: Callable,
):
    page = 1
    objs: List[return_type] = []
    while (
        response := cast(
            Dict[str, Any],
            await _request(
                app, api_key, api_secret, method, path, params={"page": page}
            ),
        )
    ) and response.get("items"):
        log.debug(
            "called %s [%d/%d], received %d objects",
            path,
            page,
            ceil(response.get("total", -1) / response.get("size", 1)),
            len(response.get("items", [])),
        )

        objs += [return_type_creator(d) for d in response.get("items", [])]
        page += 1
    return objs


async def check_service_health(app: aiohttp.web.Application) -> bool:
    datcore_adapter_settings = app[APP_CONFIG_KEY].DATCORE_ADAPTER
    url = datcore_adapter_settings.endpoint + "/ready"
    session: ClientSession = get_client_session(app)
    try:
        await session.get(url, raise_for_status=True)
    except (TimeoutError, aiohttp.ClientError):
        return False
    return True


async def check_user_can_connect(
    app: aiohttp.web.Application, api_key: str, api_secret: str
) -> bool:
    try:
        await _request(app, api_key, api_secret, "GET", "/user/profile")
        return True
    except DatcoreAdapterException:
        return False


async def list_all_datasets_files_metadatas(
    app: aiohttp.web.Application, api_key: str, api_secret: str
) -> List[FileMetaDataEx]:
    all_datasets: List[DatasetMetaData] = await list_datasets(app, api_key, api_secret)
    get_dataset_files_tasks = [
        list_all_files_metadatas_in_dataset(app, api_key, api_secret, d.dataset_id)
        for d in all_datasets
    ]
    results = await asyncio.gather(*get_dataset_files_tasks)
    all_files_of_all_datasets: List[FileMetaDataEx] = []
    for data in results:
        all_files_of_all_datasets += data
    return all_files_of_all_datasets


async def list_all_files_metadatas_in_dataset(
    app: aiohttp.web.Application, api_key: str, api_secret: str, dataset_id: str
) -> List[FileMetaDataEx]:
    all_files: List[Dict[str, Any]] = cast(
        List[Dict[str, Any]],
        await _request(
            app,
            api_key,
            api_secret,
            "GET",
            f"/datasets/{dataset_id}/files_legacy",
        ),
    )
    return [
        FileMetaDataEx(
            fmd=FileMetaData(
                file_uuid=d["path"],
                location_id=DATCORE_ID,
                location=DATCORE_STR,
                bucket_name=d["dataset_id"],
                object_name=d["path"],
                file_name=d["name"],
                file_id=d["package_id"],
                file_size=d["size"],
                created_at=d["created_at"],
                last_modified=d["last_modified_at"],
                display_file_path=d["name"],
            ),
        )
        for d in all_files
    ]


async def list_datasets(
    app: aiohttp.web.Application, api_key: str, api_secret: str
) -> List[DatasetMetaData]:
    all_datasets: List[DatasetMetaData] = await _retrieve_all_pages(
        app,
        api_key,
        api_secret,
        "GET",
        "/datasets",
        DatasetMetaData,
        lambda d: DatasetMetaData(d["id"], d["display_name"]),
    )

    return all_datasets


async def get_file_download_presigned_link(
    app: aiohttp.web.Application, api_key: str, api_secret: str, file_id: str
) -> URL:
    file_download_data = cast(
        Dict[str, Any],
        await _request(app, api_key, api_secret, "GET", f"/files/{file_id}"),
    )
    return file_download_data["link"]


async def delete_file(
    app: aiohttp.web.Application, api_key: str, api_secret: str, file_id: str
):
    await _request(app, api_key, api_secret, "DELETE", f"/files/{file_id}")
