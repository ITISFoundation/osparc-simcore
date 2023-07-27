""" Helper script to generate OAS automatically NIH-sparc portal API section
"""

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from fastapi import APIRouter, FastAPI, status
from fastapi.responses import RedirectResponse
from models_library.projects import ProjectID
from models_library.services import ServiceKey, ServiceKeyVersion
from pydantic import HttpUrl, PositiveInt

router = APIRouter(
    prefix="",  # NOTE: no API vtag!
    tags=[
        "nih-sparc",
    ],
)


@router.get(
    "/view",
    response_class=RedirectResponse,
    response_description="Opens osparc and starts viewer for selected data",
    status_code=status.HTTP_302_FOUND,
    operation_id="get_redirection_to_viewer",
)
async def get_redirection_to_viewer(
    file_type: str,
    viewer_key: ServiceKey,
    viewer_version: ServiceKeyVersion,
    file_size: PositiveInt,
    download_link: HttpUrl,
    file_name: str | None = "unknown",
):
    """Opens a viewer in osparc for data in the NIH-sparc portal"""


@router.get(
    "/study/{id}",
    response_class=RedirectResponse,
    response_description="Opens osparc and opens a copy of publised study",
    status_code=status.HTTP_302_FOUND,
    operation_id="get_redirection_to_study_page",
)
async def get_redirection_to_study_page(id: ProjectID):
    """Opens a study published in osparc"""


if __name__ == "__main__":
    from _common import CURRENT_DIR, create_and_save_openapi_specs

    create_and_save_openapi_specs(
        FastAPI(routes=router.routes), CURRENT_DIR.parent / "openapi-nih-sparc.yaml"
    )
