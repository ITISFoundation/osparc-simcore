import logging
from pathlib import Path
from typing import Any, TypeAlias, cast

import httpx
from fastapi import FastAPI
from fastapi_pagination import Page
from models_library.api_schemas_datcore_adapter.datasets import (
    DatasetMetaData as DatCoreDatasetMetaData,
)
from models_library.api_schemas_datcore_adapter.datasets import (
    DataType as DatCoreDataType,
)
from models_library.api_schemas_datcore_adapter.datasets import (
    FileMetaData as DatCoreFileMetaData,
)
from models_library.api_schemas_datcore_adapter.datasets import PackageMetaData
from models_library.api_schemas_storage.storage_schemas import (
    DatCoreCollectionName,
    DatCoreDatasetName,
    DatCorePackageName,
)
from models_library.users import UserID
from pydantic import AnyUrl, BaseModel, NonNegativeInt, TypeAdapter
from servicelib.fastapi.client_session import get_client_session
from servicelib.utils import logged_gather

from ...constants import DATCORE_ID, DATCORE_STR, MAX_CONCURRENT_REST_CALLS
from ...core.settings import get_application_settings
from ...models import (
    DatasetMetaData,
    FileMetaData,
    GenericCursor,
    PathMetaData,
    TotalNumber,
)
from .datcore_adapter_client_utils import request, retrieve_all_pages
from .datcore_adapter_exceptions import DatcoreAdapterError
from .utils import create_fmd_from_datcore_fmd, create_fmd_from_datcore_package

_logger = logging.getLogger(__file__)


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
        await request(app, api_key, api_secret, "GET", "/user/profile")
        return True
    except DatcoreAdapterError:
        return False


async def list_all_datasets_files_metadatas(
    app: FastAPI, user_id: UserID, api_key: str, api_secret: str
) -> list[FileMetaData]:
    all_datasets: list[DatasetMetaData] = await list_all_datasets(
        app, api_key, api_secret
    )
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
        await request(
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


_Size: TypeAlias = NonNegativeInt
_Page: TypeAlias = NonNegativeInt


class CursorParameters(BaseModel):
    next_page: _Page
    size: _Size


def _init_pagination(
    cursor: GenericCursor | None, limit: NonNegativeInt
) -> tuple[_Page, _Size]:
    if cursor is not None:
        cursor_params = CursorParameters.model_validate_json(cursor)
        return cursor_params.next_page, cursor_params.size
    return 1, limit


def _create_next_cursor(
    total: TotalNumber, page: _Page, size: _Size
) -> GenericCursor | None:
    if total > page * size:
        return CursorParameters.model_validate(
            {"next_page": page + 1, "size": size}
        ).model_dump_json()
    return None


async def list_top_level_objects_in_dataset(
    app: FastAPI,
    *,
    user_id: UserID,
    api_key: str,
    api_secret: str,
    dataset_id: DatCoreDatasetName,
    cursor: GenericCursor | None,
    limit: NonNegativeInt,
) -> tuple[list[PathMetaData], GenericCursor | None, TotalNumber]:
    page, size = _init_pagination(cursor, limit)
    response = await request(
        app,
        api_key,
        api_secret,
        "GET",
        f"/datasets/{dataset_id}/files",
        params={"size": size, "page": page},
    )
    assert isinstance(response, dict)  # nosec
    file_metadata_page = Page[DatCoreFileMetaData](**response)
    entries = file_metadata_page.items
    total = file_metadata_page.total
    assert isinstance(total, int)  # nosec
    next_cursor = _create_next_cursor(total, page, size)

    return (
        [
            PathMetaData(
                path=Path(e.dataset_id) / e.id,
                display_path=e.path,
                location_id=DATCORE_ID,
                location=DATCORE_STR,
                bucket_name=e.dataset_id,
                project_id=None,
                node_id=None,
                user_id=user_id,
                created_at=e.created_at,
                last_modified=e.last_modified_at,
                file_meta_data=None
                if e.data_type == DatCoreDataType.FOLDER
                else create_fmd_from_datcore_fmd(user_id, e),
            )
            for e in entries
        ],
        next_cursor,
        total,
    )


async def list_top_level_objects_in_collection(
    app: FastAPI,
    *,
    user_id: UserID,
    api_key: str,
    api_secret: str,
    dataset_id: DatCoreDatasetName,
    collection_id: DatCoreCollectionName,
    cursor: GenericCursor | None,
    limit: NonNegativeInt,
) -> tuple[list[PathMetaData], GenericCursor | None, TotalNumber]:
    page, size = _init_pagination(cursor, limit)
    response = await request(
        app,
        api_key,
        api_secret,
        "GET",
        f"/datasets/{dataset_id}/files/{collection_id}",
        params={"size": size, "page": page},
    )
    assert isinstance(response, dict)  # nosec
    file_metadata_page = Page[DatCoreFileMetaData](**response)
    entries = file_metadata_page.items
    total = file_metadata_page.total
    assert isinstance(total, int)  # nosec
    next_cursor = _create_next_cursor(total, page, size)

    return (
        [
            PathMetaData(
                path=Path(e.dataset_id) / e.id,
                display_path=e.path,
                location_id=DATCORE_ID,
                location=DATCORE_STR,
                bucket_name=e.dataset_id,
                project_id=None,
                node_id=None,
                user_id=user_id,
                created_at=e.created_at,
                last_modified=e.last_modified_at,
                file_meta_data=None
                if e.data_type == DatCoreDataType.FOLDER
                else create_fmd_from_datcore_fmd(user_id, e),
            )
            for e in entries
        ],
        next_cursor,
        total,
    )


async def get_package_file_as_path(
    app: FastAPI,
    *,
    user_id: UserID,
    api_key: str,
    api_secret: str,
    dataset_id: DatCoreDatasetName,
    package_id: DatCorePackageName,
) -> PathMetaData:
    pck_files = await get_package_files(
        app,
        api_key=api_key,
        api_secret=api_secret,
        package_id=package_id,
    )

    assert len(pck_files) == 1  # nosec
    dat_core_fmd = pck_files[0]

    return PathMetaData(
        path=Path(dataset_id) / package_id,
        display_path=dat_core_fmd.display_path,
        location_id=DATCORE_ID,
        location=DATCORE_STR,
        bucket_name=dat_core_fmd.s3_bucket,
        project_id=None,
        node_id=None,
        user_id=user_id,
        created_at=dat_core_fmd.created_at,
        last_modified=dat_core_fmd.updated_at,
        file_meta_data=create_fmd_from_datcore_package(user_id, pck_files[0]),
    )


async def list_all_datasets(
    app: FastAPI, api_key: str, api_secret: str
) -> list[DatasetMetaData]:
    all_datasets: list[DatasetMetaData] = await retrieve_all_pages(
        app,
        api_key,
        api_secret,
        "GET",
        "/datasets",
        lambda d: DatasetMetaData(dataset_id=d["id"], display_name=d["display_name"]),
    )

    return all_datasets


async def list_datasets(
    app: FastAPI,
    *,
    api_key: str,
    api_secret: str,
    cursor: GenericCursor | None,
    limit: NonNegativeInt,
) -> tuple[list[DatasetMetaData], GenericCursor | None, TotalNumber]:
    page, size = _init_pagination(cursor, limit)

    response = await request(
        app,
        api_key,
        api_secret,
        "GET",
        "/datasets",
        params={"size": size, "page": page},
    )
    assert isinstance(response, dict)  # nosec
    datasets_page = Page[DatCoreDatasetMetaData](**response)
    datasets = datasets_page.items
    total = datasets_page.total

    assert isinstance(total, int)  # nosec
    next_cursor = _create_next_cursor(total, page, size)

    return (
        [
            DatasetMetaData(dataset_id=d.id, display_name=d.display_name)
            for d in datasets
        ],
        next_cursor,
        total,
    )


async def get_file_download_presigned_link(
    app: FastAPI, api_key: str, api_secret: str, file_id: str
) -> AnyUrl:
    file_download_data = cast(
        dict[str, Any],
        await request(app, api_key, api_secret, "GET", f"/files/{file_id}"),
    )
    url: AnyUrl = TypeAdapter(AnyUrl).validate_python(file_download_data["link"])
    return url


async def get_package_files(
    app: FastAPI, *, api_key: str, api_secret: str, package_id: str
) -> list[PackageMetaData]:
    return TypeAdapter(list[PackageMetaData]).validate_python(
        await request(
            app,
            api_key,
            api_secret,
            "GET",
            f"/packages/{package_id}/files",
        )
    )


async def delete_file(
    app: FastAPI, api_key: str, api_secret: str, file_id: str
) -> None:
    await request(app, api_key, api_secret, "DELETE", f"/files/{file_id}")
