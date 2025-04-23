import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
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
    complete_file_upload,
    get_upload_links_from_s3,
)

from ..._service_job import JobService
from ..._service_programs import ProgramService
from ...models.basic_types import VersionStr
from ...models.schemas.jobs import Job, JobInputs
from ...models.schemas.programs import Program, ProgramKeyId
from ..dependencies.authentication import get_current_user_id, get_product_name

_logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/{program_key:path}/releases/{version}",
    response_model=Program,
)
async def get_program_release(
    program_key: ProgramKeyId,
    version: VersionStr,
    user_id: Annotated[int, Depends(get_current_user_id)],
    program_service: Annotated[ProgramService, Depends()],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    product_name: Annotated[str, Depends(get_product_name)],
) -> Program:
    """Gets a specific release of a solver"""
    try:
        program = await program_service.get_program(
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
    program_service: Annotated[ProgramService, Depends()],
    job_service: Annotated[JobService, Depends()],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    product_name: Annotated[str, Depends(get_product_name)],
    x_simcore_parent_project_uuid: Annotated[ProjectID | None, Header()] = None,
    x_simcore_parent_node_id: Annotated[NodeID | None, Header()] = None,
    name: Annotated[str | None, Body()] = None,
    description: Annotated[str | None, Body()] = None,
):
    """Creates a program job"""

    # ensures user has access to solver
    inputs = JobInputs(values={})
    program = await program_service.get_program(
        user_id=user_id,
        name=program_key,
        version=version,
        product_name=product_name,
    )

    job, project = await job_service.create_job(
        name=name,
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
