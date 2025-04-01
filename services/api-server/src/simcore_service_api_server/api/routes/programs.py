import logging
from collections.abc import Callable
from operator import attrgetter
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from httpx import HTTPStatusError
from models_library.api_schemas_storage.storage_schemas import (
    LinkType,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import ByteSize, PositiveInt, ValidationError
from servicelib.fastapi.dependencies import get_reverse_url_mapper
from simcore_sdk.node_ports_common.constants import SIMCORE_LOCATION
from simcore_sdk.node_ports_common.filemanager import (
    complete_directory_upload,
    get_upload_links_from_s3,
)
from simcore_service_api_server._service import create_solver_or_program_job
from simcore_service_api_server.api.dependencies.webserver_http import (
    get_webserver_session,
)
from simcore_service_api_server.services_http.webserver import AuthSession

from ...models.schemas.jobs import Job, JobInputs
from ...models.schemas.programs import Program, ProgramKeyId, VersionStr
from ...services_http.catalog import CatalogApi
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.services import get_api_client

_logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=list[Program])
async def list_programs(
    user_id: Annotated[int, Depends(get_current_user_id)],
    catalog_client: Annotated[CatalogApi, Depends(get_api_client(CatalogApi))],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    product_name: Annotated[str, Depends(get_product_name)],
):
    """Lists all available solvers (latest version)

    SEE get_solvers_page for paginated version of this function
    """
    programs = await catalog_client.list_programs(
        user_id=user_id, product_name=product_name
    )

    for program in programs:
        program.url = url_for(
            "get_program_release", program_key=program.id, version=program.version
        )

    return sorted(programs, key=attrgetter("id"))


@router.get(
    "/{program_key:path}/releases/{version}",
    response_model=Program,
)
async def get_program_release(
    program_key: ProgramKeyId,
    version: VersionStr,
    user_id: Annotated[int, Depends(get_current_user_id)],
    catalog_client: Annotated[CatalogApi, Depends(get_api_client(CatalogApi))],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    product_name: Annotated[str, Depends(get_product_name)],
) -> Program:
    """Gets a specific release of a solver"""
    try:
        program = await catalog_client.get_program(
            user_id=user_id,
            name=program_key,
            version=version,
            product_name=product_name,
        )

        program.url = url_for(
            "get_program_release", program_key=program.id, version=program.version
        )
        return program

    except (
        ValueError,
        IndexError,
        ValidationError,
        HTTPStatusError,
    ) as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program {program_key}:{version} not found",
        ) from err


@router.post(
    "/{program_key:path}/releases/{version}/jobs",
    response_model=Job,
    status_code=status.HTTP_201_CREATED,
)
async def create_program_job(
    program_key: ProgramKeyId,
    version: VersionStr,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    catalog_client: Annotated[CatalogApi, Depends(get_api_client(CatalogApi))],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    product_name: Annotated[str, Depends(get_product_name)],
    x_simcore_parent_project_uuid: Annotated[ProjectID | None, Header()] = None,
    x_simcore_parent_node_id: Annotated[NodeID | None, Header()] = None,
):
    """Creates a job in a specific release with given inputs.

    NOTE: This operation does **not** start the job
    """

    # ensures user has access to solver
    inputs = JobInputs(values={})
    program = await catalog_client.get_program(
        user_id=user_id,
        name=program_key,
        version=version,
        product_name=product_name,
    )

    job, project = await create_solver_or_program_job(
        webserver_api=webserver_api,
        solver_or_program=program,
        inputs=inputs,
        parent_project_uuid=x_simcore_parent_project_uuid,
        parent_node_id=x_simcore_parent_node_id,
        url_for=url_for,
        hidden=False,
    )
    # create workspace directory so files can be uploaded to it
    assert len(project.workbench) > 0  # nosec
    node_id = next(iter(project.workbench))

    _, file_upload_schema = await get_upload_links_from_s3(
        user_id=user_id,
        store_name=None,
        store_id=SIMCORE_LOCATION,
        s3_object=f"{project.uuid}/{node_id}/workspace",
        link_type=LinkType.PRESIGNED,
        client_session=None,
        file_size=ByteSize(0),
        is_directory=True,
        sha256_checksum=None,
    )
    await complete_directory_upload(
        uploaded_parts=[],
        upload_completion_link=file_upload_schema.links.complete_upload,
    )
    return job
