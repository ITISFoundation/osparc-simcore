import logging
from typing import Annotated, Final, TypeAlias, TypeVar

from aiocache import cached  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi_pagination import Page, Params
from fastapi_pagination.api import create_page, resolve_params
from fastapi_pagination.bases import RawParams
from fastapi_pagination.customization import CustomizedPage, UseParamsFields
from models_library.api_schemas_datcore_adapter.datasets import (
    DatasetMetaData,
    FileMetaData,
)
from models_library.api_schemas_storage.storage_schemas import (
    DEFAULT_NUMBER_OF_PATHS_PER_PAGE,
    MAX_NUMBER_OF_PATHS_PER_PAGE,
)
from servicelib.fastapi.requests_decorators import cancel_on_disconnect
from starlette import status

from ...modules.pennsieve import PennsieveApiClient
from ..dependencies.pennsieve import get_pennsieve_api_client

router = APIRouter()
log = logging.getLogger(__file__)

_MINUTE: Final[int] = 60
_PENNSIEVE_CACHING_TTL_S: Final[int] = (
    5 * _MINUTE
)  # NOTE: this caching time is arbitrary


_T = TypeVar("_T")
_CustomPage = CustomizedPage[
    Page[_T],
    UseParamsFields(
        size=Query(
            DEFAULT_NUMBER_OF_PATHS_PER_PAGE, ge=1, le=MAX_NUMBER_OF_PATHS_PER_PAGE
        ),
    ),
]

_CustomizedPageParams: TypeAlias = _CustomPage.__params_type__  # type: ignore


@router.get(
    "/datasets",
    summary="list datasets",
    status_code=status.HTTP_200_OK,
    response_model=_CustomPage[DatasetMetaData],
)
@cancel_on_disconnect
@cached(
    ttl=_PENNSIEVE_CACHING_TTL_S,
    key_builder=lambda f, *args, **kwargs: f"{f.__name__}_{kwargs['x_datcore_api_key']}_{kwargs['x_datcore_api_secret']}_{kwargs['params']}",
)
async def list_datasets(
    request: Request,
    x_datcore_api_key: Annotated[str, Header(..., description="Datcore API Key")],
    x_datcore_api_secret: Annotated[str, Header(..., description="Datcore API Secret")],
    pennsieve_client: Annotated[PennsieveApiClient, Depends(get_pennsieve_api_client)],
    page_params: Annotated[_CustomizedPageParams, Depends()],
):
    assert request  # nosec
    assert page_params.limit is not None  # nosec
    assert page_params.offset is not None  # nosec
    datasets, total = await pennsieve_client.list_datasets(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        limit=page_params.limit,
        offset=page_params.offset,
    )
    return create_page(datasets, total=total, params=page_params)


@router.get(
    "/datasets/{dataset_id}",
    status_code=status.HTTP_200_OK,
    response_model=DatasetMetaData,
)
@cancel_on_disconnect
async def get_dataset(
    request: Request,
    x_datcore_api_key: Annotated[str, Header(..., description="Datcore API Key")],
    x_datcore_api_secret: Annotated[str, Header(..., description="Datcore API Secret")],
    pennsieve_client: Annotated[PennsieveApiClient, Depends(get_pennsieve_api_client)],
    params: Annotated[Params, Depends()],
    dataset_id: str,
) -> DatasetMetaData:
    assert request  # nosec
    raw_params: RawParams = resolve_params(params).to_raw_params()
    assert raw_params.limit is not None  # nosec
    assert raw_params.offset is not None  # nosec
    return await pennsieve_client.get_dataset(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        dataset_id=dataset_id,
    )


@router.get(
    "/datasets/{dataset_id}/files",
    summary="list top level files/folders in a dataset",
    status_code=status.HTTP_200_OK,
    response_model=_CustomPage[FileMetaData],
)
@cancel_on_disconnect
@cached(
    ttl=_PENNSIEVE_CACHING_TTL_S,
    key_builder=lambda f, *args, **kwargs: f"{f.__name__}_{kwargs['x_datcore_api_key']}_{kwargs['x_datcore_api_secret']}_{kwargs['dataset_id']}_{kwargs['params']}",
)
async def list_dataset_top_level_files(
    request: Request,
    dataset_id: str,
    x_datcore_api_key: Annotated[str, Header(..., description="Datcore API Key")],
    x_datcore_api_secret: Annotated[str, Header(..., description="Datcore API Secret")],
    pennsieve_client: Annotated[PennsieveApiClient, Depends(get_pennsieve_api_client)],
    page_params: Annotated[_CustomizedPageParams, Depends()],
):
    assert request  # nosec

    assert page_params.limit is not None  # nosec
    assert page_params.offset is not None  # nosec
    file_metas, total = await pennsieve_client.list_packages_in_dataset(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        dataset_id=dataset_id,
        limit=page_params.limit,
        offset=page_params.offset,
    )
    return create_page(file_metas, total=total, params=page_params)


@router.get(
    "/datasets/{dataset_id}/files/{collection_id}",
    summary="list top level files/folders in a collection in a dataset",
    status_code=status.HTTP_200_OK,
    response_model=_CustomPage[FileMetaData],
)
@cancel_on_disconnect
@cached(
    ttl=_PENNSIEVE_CACHING_TTL_S,
    key_builder=lambda f, *args, **kwargs: f"{f.__name__}_{kwargs['x_datcore_api_key']}_{kwargs['x_datcore_api_secret']}_{kwargs['dataset_id']}_{kwargs['collection_id']}_{kwargs['params']}",
)
async def list_dataset_collection_files(
    request: Request,
    dataset_id: str,
    collection_id: str,
    x_datcore_api_key: Annotated[str, Header(..., description="Datcore API Key")],
    x_datcore_api_secret: Annotated[str, Header(..., description="Datcore API Secret")],
    pennsieve_client: Annotated[PennsieveApiClient, Depends(get_pennsieve_api_client)],
    page_params: Annotated[_CustomizedPageParams, Depends()],
):
    assert request  # nosec
    assert page_params.limit is not None  # nosec
    assert page_params.offset is not None  # nosec
    file_metas, total = await pennsieve_client.list_packages_in_collection(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        limit=page_params.limit,
        offset=page_params.offset,
        dataset_id=dataset_id,
        collection_id=collection_id,
    )
    return create_page(file_metas, total=total, params=page_params)


@router.get(
    "/datasets/{dataset_id}/files_legacy",
    summary="list all file meta data in dataset",
    status_code=status.HTTP_200_OK,
    response_model=list[FileMetaData],
)
@cancel_on_disconnect
@cached(
    ttl=_PENNSIEVE_CACHING_TTL_S,
    key_builder=lambda f, *args, **kwargs: f"{f.__name__}_{kwargs['x_datcore_api_key']}_{kwargs['x_datcore_api_secret']}_{kwargs['dataset_id']}",
)
async def list_dataset_files_legacy(
    request: Request,
    dataset_id: str,
    x_datcore_api_key: Annotated[str, Header(..., description="Datcore API Key")],
    x_datcore_api_secret: Annotated[str, Header(..., description="Datcore API Secret")],
    pennsieve_client: Annotated[PennsieveApiClient, Depends(get_pennsieve_api_client)],
) -> list[FileMetaData]:
    assert request  # nosec
    return await pennsieve_client.list_all_dataset_files(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        dataset_id=dataset_id,
    )
