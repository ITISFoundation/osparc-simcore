import logging
from typing import Final

from aiocache import cached
from fastapi import APIRouter, Depends, Header, Request
from fastapi_pagination import Page, Params
from fastapi_pagination.api import create_page, resolve_params
from fastapi_pagination.bases import RawParams
from servicelib.fastapi.requests_decorators import cancel_on_disconnect
from starlette import status

from ...models.domains.datasets import DatasetsOut, FileMetaDataOut
from ...modules.pennsieve import PennsieveApiClient
from ..dependencies.pennsieve import get_pennsieve_api_client

router = APIRouter()
log = logging.getLogger(__file__)

_MINUTE: Final[int] = 60
_PENNSIEVE_CACHING_TTL_S: Final[int] = (
    5 * _MINUTE
)  # NOTE: this caching time is arbitrary


@router.get(
    "/datasets",
    summary="list datasets",
    status_code=status.HTTP_200_OK,
    response_model=Page[DatasetsOut],
)
@cancel_on_disconnect
@cached(
    ttl=_PENNSIEVE_CACHING_TTL_S,
    key_builder=lambda f, *args, **kwargs: f"{f.__name__}_{kwargs['x_datcore_api_key']}_{kwargs['x_datcore_api_secret']}_{kwargs['params']}",
)
async def list_datasets(
    request: Request,
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
    params: Params = Depends(),
) -> Page[DatasetsOut]:
    assert request  # nosec
    raw_params: RawParams = resolve_params(params).to_raw_params()
    datasets, total = await pennsieve_client.list_datasets(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        limit=raw_params.limit,
        offset=raw_params.offset,
    )
    return create_page(items=datasets, total=total, params=params)


@router.get(
    "/datasets/{dataset_id}/files",
    summary="list top level files/folders in a dataset",
    status_code=status.HTTP_200_OK,
    response_model=Page[FileMetaDataOut],
)
@cancel_on_disconnect
@cached(
    ttl=_PENNSIEVE_CACHING_TTL_S,
    key_builder=lambda f, *args, **kwargs: f"{f.__name__}_{kwargs['x_datcore_api_key']}_{kwargs['x_datcore_api_secret']}_{kwargs['dataset_id']}_{kwargs['params']}",
)
async def list_dataset_top_level_files(
    request: Request,
    dataset_id: str,
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
    params: Params = Depends(),
) -> Page[FileMetaDataOut]:
    assert request  # nosec
    raw_params: RawParams = resolve_params(params).to_raw_params()

    file_metas, total = await pennsieve_client.list_packages_in_dataset(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        dataset_id=dataset_id,
        limit=raw_params.limit,
        offset=raw_params.offset,
    )
    return create_page(items=file_metas, total=total, params=params)


@router.get(
    "/datasets/{dataset_id}/files/{collection_id}",
    summary="list top level files/folders in a collection in a dataset",
    status_code=status.HTTP_200_OK,
    response_model=Page[FileMetaDataOut],
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
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
    params: Params = Depends(),
) -> Page[FileMetaDataOut]:
    assert request  # nosec
    raw_params: RawParams = resolve_params(params).to_raw_params()

    file_metas, total = await pennsieve_client.list_packages_in_collection(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        limit=raw_params.limit,
        offset=raw_params.offset,
        dataset_id=dataset_id,
        collection_id=collection_id,
    )
    return create_page(items=file_metas, total=total, params=params)


@router.get(
    "/datasets/{dataset_id}/files_legacy",
    summary="list all file meta data in dataset",
    status_code=status.HTTP_200_OK,
    response_model=list[FileMetaDataOut],
)
@cancel_on_disconnect
@cached(
    ttl=_PENNSIEVE_CACHING_TTL_S,
    key_builder=lambda f, *args, **kwargs: f"{f.__name__}_{kwargs['x_datcore_api_key']}_{kwargs['x_datcore_api_secret']}_{kwargs['dataset_id']}",
)
async def list_dataset_files_legacy(
    request: Request,
    dataset_id: str,
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
) -> list[FileMetaDataOut]:
    assert request  # nosec
    file_metas = await pennsieve_client.list_all_dataset_files(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        dataset_id=dataset_id,
    )
    return file_metas
