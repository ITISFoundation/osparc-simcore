import logging
from typing import List

from fastapi import APIRouter, Depends, Header
from starlette import status

from ...models.domains.datasets import DatasetsOut
from ...models.schemas.datasets import DatasetMetaData
from ...modules.pennsieve import PennsieveApiClient
from ..dependencies.pennsieve import get_pennsieve_api_client

router = APIRouter()
log = logging.getLogger(__file__)


@router.get(
    "/datasets",
    summary="list top level datasets",
    status_code=status.HTTP_200_OK,
    response_model=List[DatasetsOut],
)
async def list_datasets(
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
) -> List[DatasetsOut]:
    datasets: List[DatasetMetaData] = await pennsieve_client.get_datasets(
        api_key=x_datcore_api_key, api_secret=x_datcore_api_secret
    )
    return datasets
