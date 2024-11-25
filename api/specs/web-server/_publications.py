from typing import Annotated

from fastapi import APIRouter, File, status
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "publication",
    ],
)


@router.post(
    "/publications/service-submission",
    status_code=status.HTTP_204_NO_CONTENT,
)
def service_submission(
    file: Annotated[bytes, File(description="metadata.json submission file")]
):
    """
    Submits files with new service candidate
    """
    assert file  # nosec
