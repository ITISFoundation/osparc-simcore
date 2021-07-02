import logging
import tempfile
from pathlib import Path
from typing import List

import aiofiles
from fastapi import APIRouter, Depends, File, Header, Request, UploadFile
from fastapi_pagination import Page, Params
from fastapi_pagination.api import create_page, resolve_params
from fastapi_pagination.bases import RawParams
from starlette import status

from ...models.domains.datasets import DatasetsOut, FileMetaDataOut
from ...modules.pennsieve import PennsieveApiClient
from ...utils.requests_decorators import cancellable_request
from ..dependencies.pennsieve import get_pennsieve_api_client

router = APIRouter()
log = logging.getLogger(__file__)


@router.get(
    "/datasets",
    summary="list datasets",
    status_code=status.HTTP_200_OK,
    response_model=Page[DatasetsOut],
)
@cancellable_request
async def list_datasets(
    _request: Request,
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
    params: Params = Depends(),
) -> Page[DatasetsOut]:
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
@cancellable_request
async def list_dataset_top_level_files(
    _request: Request,
    dataset_id: str,
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
    params: Params = Depends(),
) -> Page[FileMetaDataOut]:
    raw_params: RawParams = resolve_params(params).to_raw_params()

    file_metas, total = await pennsieve_client.list_packages_in_dataset(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        dataset_id=dataset_id,
        limit=raw_params.limit,
        offset=raw_params.offset,
    )
    return create_page(items=file_metas, total=total, params=params)


@router.post(
    "/datasets/{dataset_id}/files",
    summary="uploads a file into a dataset",
    status_code=status.HTTP_204_NO_CONTENT,
)
@cancellable_request
async def upload_file(
    _request: Request,
    dataset_id: str,
    file: UploadFile = File(...),
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
):
    # the file must be locally available to be uploaded via the pennsieve agent
    with tempfile.TemporaryDirectory() as tmp_dir:
        received_file = Path(tmp_dir) / file.filename
        async with aiofiles.open(received_file, "wb") as out_fd:
            while content := await file.read(16 * 1024):
                await out_fd.write(content)
        # now upload to pennsieve
        await pennsieve_client.upload_file(
            api_key=x_datcore_api_key,
            api_secret=x_datcore_api_secret,
            file=received_file,
            dataset_id=dataset_id,
        )


@router.get(
    "/datasets/{dataset_id}/files/{collection_id}",
    summary="list top level files/folders in a collection in a dataset",
    status_code=status.HTTP_200_OK,
    response_model=Page[FileMetaDataOut],
)
@cancellable_request
async def list_dataset_collection_files(
    _request: Request,
    dataset_id: str,
    collection_id: str,
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
    params: Params = Depends(),
) -> Page[FileMetaDataOut]:
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


@router.post(
    "/datasets/{dataset_id}/files/{collection_id}",
    summary="uploads a file into a collection",
    status_code=status.HTTP_202_ACCEPTED,
)
@cancellable_request
async def upload_file_in_collection(
    _request: Request,
    dataset_id: str,
    collection_id: str,
    file: UploadFile = File(...),
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
):
    # the file must be locally available to be uploaded via the pennsieve agent
    with tempfile.TemporaryDirectory() as tmp_dir:
        received_file = Path(tmp_dir) / file.filename
        async with aiofiles.open(received_file, "wb") as out_fd:
            while content := await file.read(16 * 1024):
                await out_fd.write(content)
        # now upload to pennsieve
        await pennsieve_client.upload_file(
            api_key=x_datcore_api_key,
            api_secret=x_datcore_api_secret,
            file=received_file,
            dataset_id=dataset_id,
            collection_id=collection_id,
        )


@router.get(
    "/datasets/{dataset_id}/files_legacy",
    summary="list all file meta data in dataset",
    status_code=status.HTTP_200_OK,
    response_model=List[FileMetaDataOut],
)
@cancellable_request
async def list_dataset_files_legacy(
    _request: Request,
    dataset_id: str,
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
) -> List[FileMetaDataOut]:
    file_metas = await pennsieve_client.list_all_dataset_files(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        dataset_id=dataset_id,
    )
    return file_metas
