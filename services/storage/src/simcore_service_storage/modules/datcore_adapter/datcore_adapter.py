import logging
from collections.abc import Callable
from math import ceil
from typing import Any, TypeVar, cast

import httpx
from fastapi import FastAPI
from models_library.api_schemas_storage import DatCoreDatasetName
from models_library.users import UserID
from pydantic import AnyUrl, TypeAdapter
from servicelib.fastapi.client_session import get_client_session
from servicelib.utils import logged_gather

from ...constants import DATCORE_ID, DATCORE_STR, MAX_CONCURRENT_REST_CALLS
from ...core.settings import get_application_settings
from ...models import DatasetMetaData, FileMetaData
from .datcore_adapter_exceptions import (
    DatcoreAdapterClientError,
    DatcoreAdapterError,
    DatcoreAdapterTimeoutError,
)

_logger = logging.getLogger(__file__)


class _DatcoreAdapterResponseError(DatcoreAdapterError):
    """Basic exception for response errors"""

    def __init__(self, status: int, reason: str) -> None:
        self.status = status
        self.reason = reason
        super().__init__(
            msg=f"forwarded call failed with status {status}, reason {reason}"
        )


async def _request(
    app: FastAPI,
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    **request_kwargs,
) -> dict[str, Any] | list[dict[str, Any]]:
    datcore_adapter_settings = get_application_settings(app).DATCORE_ADAPTER
    url = datcore_adapter_settings.endpoint + path
    session = get_client_session(app)

    try:
        if request_kwargs is None:
            request_kwargs = {}
        response = await session.request(
            method,
            url,
            headers={
                "x-datcore-api-key": api_key,
                "x-datcore-api-secret": api_secret,
            },
            json=json,
            params=params,
            **request_kwargs,
        )
        response.raise_for_status()
        response_data = response.json()
        assert isinstance(response_data, dict | list)  # nosec
        return response_data

    except httpx.HTTPStatusError as exc:
        raise _DatcoreAdapterResponseError(
            status=exc.response.status_code, reason=f"{exc}"
        ) from exc

    except TimeoutError as exc:
        msg = f"datcore-adapter server timed-out: {exc}"
        raise DatcoreAdapterTimeoutError(msg) from exc

    except httpx.RequestError as exc:
        msg = f"unexpected request error: {exc}"
        raise DatcoreAdapterClientError(msg) from exc


_T = TypeVar("_T")


async def _retrieve_all_pages(
    app: FastAPI,
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    return_type_creator: Callable[..., _T],
) -> list[_T]:
    page = 1
    objs = []
    while (
        response := cast(
            dict[str, Any],
            await _request(
                app, api_key, api_secret, method, path, params={"page": page}
            ),
        )
    ) and response.get("items"):
        _logger.debug(
            "called %s [%d/%d], received %d objects",
            path,
            page,
            ceil(response.get("total", -1) / response.get("size", 1)),
            len(response.get("items", [])),
        )

        objs += [return_type_creator(d) for d in response.get("items", [])]
        page += 1
    return objs


async def check_service_health(app: FastAPI) -> bool:
    datcore_adapter_settings = get_application_settings(app).DATCORE_ADAPTER
    url = datcore_adapter_settings.endpoint + "/ready"
    session = get_client_session(app)
    try:
        response = await session.get(url)
        response.raise_for_status()
    except (TimeoutError, httpx.HTTPStatusError):
        return False
    return True


async def check_user_can_connect(app: FastAPI, api_key: str, api_secret: str) -> bool:
    if not api_key or not api_secret:
        # no need to ask, datcore is an authenticated service
        return False

    try:
        await _request(app, api_key, api_secret, "GET", "/user/profile")
        return True
    except DatcoreAdapterError:
        return False


async def list_all_datasets_files_metadatas(
    app: FastAPI, user_id: UserID, api_key: str, api_secret: str
) -> list[FileMetaData]:
    all_datasets: list[DatasetMetaData] = await list_datasets(app, api_key, api_secret)
    results = await logged_gather(
        *(
            list_all_files_metadatas_in_dataset(
                app,
                user_id,
                api_key,
                api_secret,
                cast(DatCoreDatasetName, d.dataset_id),
            )
            for d in all_datasets
        ),
        log=_logger,
        max_concurrency=MAX_CONCURRENT_REST_CALLS,
    )
    all_files_of_all_datasets: list[FileMetaData] = []
    for data in results:
        all_files_of_all_datasets += data
    return all_files_of_all_datasets


_LIST_ALL_DATASETS_TIMEOUT_S = 60


async def list_all_files_metadatas_in_dataset(
    app: FastAPI,
    user_id: UserID,
    api_key: str,
    api_secret: str,
    dataset_id: DatCoreDatasetName,
) -> list[FileMetaData]:
    all_files: list[dict[str, Any]] = cast(
        list[dict[str, Any]],
        await _request(
            app,
            api_key,
            api_secret,
            "GET",
            f"/datasets/{dataset_id}/files_legacy",
            timeout=_LIST_ALL_DATASETS_TIMEOUT_S,
        ),
    )
    return [
        FileMetaData.model_construct(
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
            project_id=None,
            node_id=None,
            user_id=user_id,
            is_soft_link=False,
        )
        for d in all_files
    ]


async def list_datasets(
    app: FastAPI, api_key: str, api_secret: str
) -> list[DatasetMetaData]:
    all_datasets: list[DatasetMetaData] = await _retrieve_all_pages(
        app,
        api_key,
        api_secret,
        "GET",
        "/datasets",
        lambda d: DatasetMetaData(dataset_id=d["id"], display_name=d["display_name"]),
    )

    return all_datasets


async def get_file_download_presigned_link(
    app: FastAPI, api_key: str, api_secret: str, file_id: str
) -> AnyUrl:
    file_download_data = cast(
        dict[str, Any],
        await _request(app, api_key, api_secret, "GET", f"/files/{file_id}"),
    )
    url: AnyUrl = TypeAdapter(AnyUrl).validate_python(file_download_data["link"])
    return url


async def get_package_files(
    app: FastAPI, api_key: str, api_secret: str, package_id: str
) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        await _request(
            app,
            api_key,
            api_secret,
            "GET",
            f"/packages/{package_id}/files",
        ),
    )


async def delete_file(
    app: FastAPI, api_key: str, api_secret: str, file_id: str
) -> None:
    await _request(app, api_key, api_secret, "DELETE", f"/files/{file_id}")
