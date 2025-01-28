import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from models_library.api_schemas_storage import DatasetMetaDataGet, FileMetaDataGet
from models_library.generics import Envelope
from models_library.projects_nodes_io import LocationID

from ...dsm import get_dsm_provider
from ...models import FilesMetadataDatasetQueryParams, StorageQueryParamsBase

_logger = logging.getLogger(__name__)

router = APIRouter(
    tags=[
        "datasets",
    ],
)


@router.get(
    "/locations/{location_id}/datasets",
    response_model=Envelope[list[DatasetMetaDataGet]],
)
async def list_datasets_metadata(
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    location_id: LocationID,
    request: Request,
) -> Envelope[list[DatasetMetaDataGet]]:
    dsm = get_dsm_provider(request.app).get(location_id)
    data = await dsm.list_datasets(query_params.user_id)
    return Envelope[list[DatasetMetaDataGet]](
        data=[DatasetMetaDataGet(**d.model_dump()) for d in data]
    )


@router.get(
    "/locations/{location_id}/datasets/{dataset_id}/metadata",
    response_model=Envelope[list[FileMetaDataGet]],
)
async def list_dataset_files_metadata(
    query_params: Annotated[FilesMetadataDatasetQueryParams, Depends()],
    location_id: LocationID,
    dataset_id: str,
    request: Request,
) -> Envelope[list[FileMetaDataGet]]:
    dsm = get_dsm_provider(request.app).get(location_id)
    data = await dsm.list_files_in_dataset(
        user_id=query_params.user_id,
        dataset_id=dataset_id,
        expand_dirs=query_params.expand_dirs,
    )
    return Envelope[list[FileMetaDataGet]](
        data=[FileMetaDataGet(**d.model_dump()) for d in data]
    )
