# pylint: disable=too-many-arguments
import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from fastapi_pagination import create_page
from httpx import HTTPStatusError
from models_library.api_schemas_storage.storage_schemas import LinkType
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import ByteSize, PositiveInt, StringConstraints, ValidationError
from servicelib.fastapi.dependencies import get_reverse_url_mapper
from simcore_sdk.node_ports_common.constants import SIMCORE_LOCATION
from simcore_sdk.node_ports_common.filemanager import (
    complete_file_upload,
    get_upload_links_from_s3,
)

from ..._service_jobs import JobService
from ..._service_programs import ProgramService
from ...api.routes._constants import (
    DEFAULT_MAX_STRING_LENGTH,
    FMSG_CHANGELOG_NEW_IN_VERSION,
    create_route_description,
)
from ...models.basic_types import VersionStr
from ...models.pagination import Page, PaginationParams
from ...models.schemas.jobs import Job, JobInputs
from ...models.schemas.programs import Program, ProgramKeyId
from ..dependencies.authentication import get_current_user_id
from ..dependencies.services import get_job_service, get_program_service

_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=Page[Program],
    description=create_route_description(
        base="Lists the latest of all available programs",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.9"),
        ],
    ),
    include_in_schema=False,  # TO BE RELEASED in 0.9
)
async def list_programs(
    program_service: Annotated[ProgramService, Depends(get_program_service)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    page_params: Annotated[PaginationParams, Depends()],
):
    programs, page_meta = await program_service.list_latest_programs(
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
    )
    page_params.limit = page_meta.limit
    page_params.offset = page_meta.offset

    for program in programs:
        program.url = url_for(
            "get_program_release", program_key=program.id, version=program.version
        )

    return create_page(
        programs,
        total=page_meta.total,
        params=page_params,
    )


@router.get(
    "/{program_key:path}/releases",
    response_model=Page[Program],
    description=create_route_description(
        base="Lists the latest of all available programs",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.9"),
        ],
    ),
    include_in_schema=False,  # TO BE RELEASED in 0.9
)
async def list_program_history(
    program_key: ProgramKeyId,
    program_service: Annotated[ProgramService, Depends(get_program_service)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    page_params: Annotated[PaginationParams, Depends()],
):
    programs, page_meta = await program_service.list_program_history(
        program_key=program_key,
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
    )
    page_params.limit = page_meta.limit
    page_params.offset = page_meta.offset

    for program in programs:
        program.url = url_for(
            "get_program_release", program_key=program.id, version=program.version
        )

    return create_page(
        programs,
        total=page_meta.total,
        params=page_params,
    )


@router.get(
    "/{program_key:path}/releases/{version}",
    response_model=Program,
)
async def get_program_release(
    program_key: ProgramKeyId,
    version: VersionStr,
    program_service: Annotated[ProgramService, Depends(get_program_service)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
) -> Program:
    """Gets a specific release of a solver"""
    try:
        program = await program_service.get_program(
            name=program_key,
            version=version,
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
    program_service: Annotated[ProgramService, Depends(get_program_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    x_simcore_parent_project_uuid: Annotated[ProjectID | None, Header()] = None,
    x_simcore_parent_node_id: Annotated[NodeID | None, Header()] = None,
    name: Annotated[
        str | None, StringConstraints(max_length=DEFAULT_MAX_STRING_LENGTH), Body()
    ] = None,
    description: Annotated[
        str | None, StringConstraints(max_length=DEFAULT_MAX_STRING_LENGTH), Body()
    ] = None,
):
    """Creates a program job"""

    # ensures user has access to solver
    inputs = JobInputs(values={})
    program = await program_service.get_program(
        name=program_key,
        version=version,
    )

    job, project = await job_service.create_job(
        project_name=name,
        description=description,
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
    await complete_file_upload(
        uploaded_parts=[],
        upload_completion_link=file_upload_schema.links.complete_upload,
        is_directory=True,
    )
    return job
