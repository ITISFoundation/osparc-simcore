from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_storage import DatasetMetaDataGet, FileMetaDataGet
from models_library.generics import Envelope
from simcore_service_storage._meta import API_VTAG
from simcore_service_storage.models import (
    FilesMetadataDatasetPathParams,
    LocationPathParams,
    StorageQueryParamsBase,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "datasets",
    ],
)


@router.get(
    "/locations/{location_id}/datasets",
    response_model=Envelope[list[DatasetMetaDataGet]],
)
async def list_datasets_metadata(
    _query: Annotated[StorageQueryParamsBase, Depends()],
    _path: Annotated[LocationPathParams, Depends()],
):
    ...


@router.get(
    "/locations/{location_id}/datasets/{dataset_id}/metadata",
    response_model=Envelope[list[FileMetaDataGet]],
)
async def list_dataset_files_metadata(
    _query: Annotated[FilesMetadataDatasetPathParams, Depends()],
    _path: Annotated[LocationPathParams, Depends()],
):
    ...
