import logging
from typing import List

from fastapi import APIRouter, Depends, Header
from fastapi_pagination import Page, Params, paginate
from starlette import status

from ...models.domains.datasets import DatasetsOut, FileMetaDataOut
from ...models.schemas.datasets import DatasetMetaData
from ...modules.pennsieve import PennsieveApiClient
from ..dependencies.pennsieve import get_pennsieve_api_client

router = APIRouter()
log = logging.getLogger(__file__)


@router.get(
    "/datasets",
    summary="list datasets",
    status_code=status.HTTP_200_OK,
    response_model=Page[DatasetsOut],
)
async def list_datasets(
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
    params: Params = Depends(),
) -> Page[DatasetsOut]:
    datasets: List[DatasetMetaData] = await pennsieve_client.get_datasets(
        api_key=x_datcore_api_key, api_secret=x_datcore_api_secret
    )
    return paginate(datasets, params)


# @router.get(
#     "/datasets/{dataset_id}",
#     summary="get dataset",
#     status_code=status.HTTP_200_OK,
#     response_model=DatasetsOut,
# )
# async def list_datasets(
#     x_datcore_api_key: str = Header(..., description="Datcore API Key"),
#     x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
#     pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
# ) -> Page[DatasetsOut]:
#     datasets: List[DatasetMetaData] = await pennsieve_client.get_datasets(
#         api_key=x_datcore_api_key, api_secret=x_datcore_api_secret
#     )
#     return datasets


@router.get(
    "/datasets/{dataset_id}/files",
    summary="list all file meta data in dataset",
    status_code=status.HTTP_200_OK,
    response_model=Page[FileMetaDataOut],
)
async def list_dataset_files(
    dataset_id: str,
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
    params: Params = Depends(),
) -> Page[FileMetaDataOut]:
    file_metas = await pennsieve_client.list_dataset_files(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        dataset_id=dataset_id,
    )
    return paginate(file_metas, params)


@router.get(
    "/datasets/{dataset_id}/files_legacy",
    summary="list all file meta data in dataset",
    status_code=status.HTTP_200_OK,
    response_model=List[FileMetaDataOut],
)
async def list_dataset_files_legacy(
    dataset_id: str,
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
) -> List[FileMetaDataOut]:
    file_metas = await pennsieve_client.list_dataset_files(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        dataset_id=dataset_id,
    )
    return file_metas
