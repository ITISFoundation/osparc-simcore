import logging

from fastapi import APIRouter, Depends, Header
from pydantic import AnyUrl, parse_obj_as
from starlette import status

from ...models.domains.files import FileDownloadOut
from ...modules.pennsieve import PennsieveApiClient
from ..dependencies.pennsieve import get_pennsieve_api_client

router = APIRouter()
log = logging.getLogger(__file__)


@router.get(
    "/files/{file_id}",
    summary="returns a pre-signed download link for the file",
    status_code=status.HTTP_200_OK,
    response_model=FileDownloadOut,
)
async def download_file(
    file_id: str,
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
) -> FileDownloadOut:
    presigned_download_link = await pennsieve_client.get_presigned_download_link(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        package_id=file_id,
    )
    return FileDownloadOut(link=parse_obj_as(AnyUrl, f"{presigned_download_link}"))


@router.delete(
    "/files/{file_id}", summary="deletes a file", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_file(
    file_id: str,
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
):
    await pennsieve_client.delete_object(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        obj_id=file_id,
    )
