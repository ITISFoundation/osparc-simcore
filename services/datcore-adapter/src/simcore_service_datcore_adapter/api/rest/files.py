import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from pydantic import AnyUrl, TypeAdapter
from servicelib.fastapi.requests_decorators import cancel_on_disconnect
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
@cancel_on_disconnect
async def download_file(
    request: Request,
    file_id: str,
    x_datcore_api_key: Annotated[str, Header(..., description="Datcore API Key")],
    x_datcore_api_secret: Annotated[str, Header(..., description="Datcore API Secret")],
    pennsieve_client: Annotated[PennsieveApiClient, Depends(get_pennsieve_api_client)],
) -> FileDownloadOut:
    assert request  # nosec
    presigned_download_link = await pennsieve_client.get_presigned_download_link(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        package_id=file_id,
    )
    return FileDownloadOut(
        link=TypeAdapter(AnyUrl).validate_python(f"{presigned_download_link}")
    )


@router.delete(
    "/files/{file_id}", summary="deletes a file", status_code=status.HTTP_204_NO_CONTENT
)
@cancel_on_disconnect
async def delete_file(
    request: Request,
    file_id: str,
    x_datcore_api_key: Annotated[str, Header(..., description="Datcore API Key")],
    x_datcore_api_secret: Annotated[str, Header(..., description="Datcore API Secret")],
    pennsieve_client: Annotated[PennsieveApiClient, Depends(get_pennsieve_api_client)],
):
    assert request  # nosec
    await pennsieve_client.delete_object(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        obj_id=file_id,
    )


@router.get(
    "/packages/{package_id}/files",
    summary="returns a package (i.e. a file)",
    status_code=status.HTTP_200_OK,
    response_model=list[dict[str, Any]],
)
@cancel_on_disconnect
async def get_package(
    request: Request,
    package_id: str,
    x_datcore_api_key: Annotated[str, Header(..., description="Datcore API Key")],
    x_datcore_api_secret: Annotated[str, Header(..., description="Datcore API Secret")],
    pennsieve_client: Annotated[PennsieveApiClient, Depends(get_pennsieve_api_client)],
) -> list[dict[str, Any]]:
    assert request  # nosec
    return await pennsieve_client.get_package_files(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
        package_id=package_id,
        limit=1,
        offset=0,
    )
