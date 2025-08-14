import logging
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_pagination.api import create_page
from models_library.api_schemas_webserver.projects import ProjectPatch
from models_library.api_schemas_webserver.projects_nodes import NodeOutputs
from models_library.clusters import ClusterID
from models_library.function_services_catalog.services import file_picker
from models_library.projects import ProjectID
from models_library.projects_nodes import InputID, InputTypes
from models_library.projects_nodes_io import NodeID
from pydantic import HttpUrl, PositiveInt
from servicelib.logging_utils import log_context

from ..._service_studies import StudyService
from ...exceptions.backend_errors import ProjectAlreadyStartedError
from ...models.api_resources import parse_resources_ids
from ...models.pagination import Page, PaginationParams
from ...models.schemas.errors import ErrorGet
from ...models.schemas.jobs import (
    Job,
    JobID,
    JobInputs,
    JobMetadata,
    JobMetadataUpdate,
    JobOutputs,
    JobStatus,
)
from ...models.schemas.studies import JobLogsMap, Study, StudyID
from ...services_http.director_v2 import DirectorV2Api
from ...services_http.jobs import (
    get_custom_metadata,
    replace_custom_metadata,
    start_project,
    stop_project,
)
from ...services_http.solver_job_models_converters import create_jobstatus_from_task
from ...services_http.storage import StorageApi
from ...services_http.study_job_models_converters import (
    create_job_from_study,
    create_job_outputs_from_project_outputs,
    get_project_and_file_inputs_from_job_inputs,
)
from ...services_http.webserver import AuthSession
from ...services_rpc.wb_api_server import WbApiRpcClient
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.services import get_api_client, get_study_service
from ..dependencies.webserver_http import get_webserver_session
from ..dependencies.webserver_rpc import get_wb_api_rpc_client
from ._constants import (
    FMSG_CHANGELOG_CHANGED_IN_VERSION,
    FMSG_CHANGELOG_NEW_IN_VERSION,
    create_route_description,
)
from .solvers_jobs import JOBS_STATUS_CODES

_logger = logging.getLogger(__name__)


router = APIRouter()


def _compose_job_resource_name(study_key, job_id) -> str:
    """Creates a unique resource name for solver's jobs"""
    return Job.compose_resource_name(
        parent_name=Study.compose_resource_name(study_key),
        job_id=job_id,
    )


@router.get(
    "/{study_id:uuid}/jobs",
    response_model=Page[Job],
    description=create_route_description(
        base="List of all jobs created for a given study (paginated)",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.10-rc1"),
        ],
    ),
    include_in_schema=False,  # TO BE RELEASED in 0.10-rc1
)
async def list_study_jobs(
    study_id: StudyID,
    page_params: Annotated[PaginationParams, Depends()],
    study_service: Annotated[StudyService, Depends(get_study_service)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    msg = f"list study jobs study_id={study_id!r} with pagination={page_params!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    _logger.debug(msg)

    jobs, meta = await study_service.list_jobs(
        filter_by_study_id=study_id,
        pagination_offset=page_params.offset,
        pagination_limit=page_params.limit,
    )

    for job in jobs:
        study_id_str, job_id = parse_resources_ids(job.resource_name)
        assert study_id_str == f"{study_id}"
        _update_study_job_urls(
            job=job, study_id=study_id, job_id=job_id, url_for=url_for
        )

    return create_page(
        jobs,
        total=meta.total,
        params=page_params,
    )


@router.post(
    "/{study_id:uuid}/jobs",
    response_model=Job,
)
async def create_study_job(
    study_id: StudyID,
    job_inputs: JobInputs,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    product_name: Annotated[str, Depends(get_product_name)],
    hidden: Annotated[bool, Query()] = True,  # noqa: FBT002
    x_simcore_parent_project_uuid: Annotated[ProjectID | None, Header()] = None,
    x_simcore_parent_node_id: Annotated[NodeID | None, Header()] = None,
) -> Job:
    """
    hidden -- if True (default) hides project from UI
    """
    project = await webserver_api.clone_project(
        project_id=study_id,
        hidden=hidden,
        parent_project_uuid=x_simcore_parent_project_uuid,
        parent_node_id=x_simcore_parent_node_id,
    )
    job = create_job_from_study(
        study_key=study_id, project=project, job_inputs=job_inputs
    )
    job.url = url_for(
        "get_study_job",
        study_id=study_id,
        job_id=job.id,
    )
    job.runner_url = url_for("get_study", study_id=study_id)
    job.outputs_url = url_for(
        "get_study_job_outputs",
        study_id=study_id,
        job_id=job.id,
    )

    await webserver_api.patch_project(
        project_id=job.id,
        patch_params=ProjectPatch(name=job.name),
    )

    await wb_api_rpc.mark_project_as_job(
        product_name=product_name,
        user_id=user_id,
        project_uuid=job.id,
        job_parent_resource_name=job.runner_name,
        storage_data_deleted=False,
    )

    project_inputs = await webserver_api.get_project_inputs(project_id=project.uuid)

    file_param_nodes = {}
    for node_id, node in project.workbench.items():
        if (
            node.key == file_picker.META.key
            and node.outputs is not None
            and len(node.outputs) == 0
        ):
            file_param_nodes[node.label] = node_id

    file_inputs: dict[InputID, InputTypes] = {}

    (
        new_project_inputs,
        new_project_file_inputs,
    ) = get_project_and_file_inputs_from_job_inputs(
        project_inputs, file_inputs, job_inputs
    )

    for node_label, file_link in new_project_file_inputs.items():
        await webserver_api.update_node_outputs(
            project_id=project.uuid,
            node_id=UUID(file_param_nodes[node_label]),
            new_node_outputs=NodeOutputs(outputs={"outFile": file_link}),
        )

    if len(new_project_inputs) > 0:
        await webserver_api.update_project_inputs(
            project_id=project.uuid, new_inputs=new_project_inputs
        )

    assert job.name == _compose_job_resource_name(study_id, job.id)

    return job


@router.get(
    "/{study_id:uuid}/jobs/{job_id:uuid}",
    response_model=Job,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    description=create_route_description(
        base="Gets a jobs for a given study",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.10-rc1"),
        ],
    ),
    include_in_schema=False,  # TO BE RELEASED in 0.10-rc1
)
async def get_study_job(
    study_id: StudyID,
    job_id: JobID,
    study_service: Annotated[StudyService, Depends(get_study_service)],
):
    assert study_service  # nosec
    msg = f"get study job study_id={study_id!r} job_id={job_id!r}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    raise NotImplementedError(msg)


@router.delete(
    "/{study_id:uuid}/jobs/{job_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorGet}},
)
async def delete_study_job(
    study_id: StudyID,
    job_id: JobID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    """Deletes an existing study job"""
    job_name = _compose_job_resource_name(study_id, job_id)
    with log_context(_logger, logging.DEBUG, f"Deleting Job '{job_name}'"):
        await webserver_api.delete_project(project_id=job_id)


@router.post(
    "/{study_id:uuid}/jobs/{job_id:uuid}:start",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobStatus,
    responses=JOBS_STATUS_CODES
    | {
        status.HTTP_200_OK: {
            "description": "Job already started",
            "model": JobStatus,
        },
        status.HTTP_406_NOT_ACCEPTABLE: {
            "description": "Cluster not found",
            "model": ErrorGet,
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Configuration error",
            "model": ErrorGet,
        },
    },
    description=create_route_description(
        changelog=[
            FMSG_CHANGELOG_CHANGED_IN_VERSION.format(
                "0.6",
                "Now responds with a 202 when successfully starting a computation",
            ),
        ]
    ),
)
async def start_study_job(
    request: Request,
    study_id: StudyID,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    cluster_id: Annotated[  # pylint: disable=unused-argument  # noqa: ARG001
        ClusterID | None,
        Query(
            description=create_route_description(
                changelog=[
                    FMSG_CHANGELOG_CHANGED_IN_VERSION.format(
                        "0.7", "query parameter `cluster_id` deprecated"
                    ),
                ]
            ),
            deprecated=True,
        ),
    ] = None,
):
    job_name = _compose_job_resource_name(study_id, job_id)
    with log_context(_logger, logging.DEBUG, f"Starting Job '{job_name}'"):
        try:
            await start_project(
                request=request,
                job_id=job_id,
                expected_job_name=job_name,
                webserver_api=webserver_api,
            )
        except ProjectAlreadyStartedError:
            job_status: JobStatus = await inspect_study_job(
                study_id=study_id,
                job_id=job_id,
                user_id=user_id,
                director2_api=director2_api,
            )
            return JSONResponse(
                content=jsonable_encoder(job_status), status_code=status.HTTP_200_OK
            )
        return await inspect_study_job(
            study_id=study_id,
            job_id=job_id,
            user_id=user_id,
            director2_api=director2_api,
        )


@router.post(
    "/{study_id:uuid}/jobs/{job_id:uuid}:stop",
    response_model=JobStatus,
)
async def stop_study_job(
    study_id: StudyID,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
):
    job_name = _compose_job_resource_name(study_id, job_id)
    with log_context(_logger, logging.DEBUG, f"Stopping Job '{job_name}'"):
        return await stop_project(
            job_id=job_id, user_id=user_id, director2_api=director2_api
        )


@router.post(
    "/{study_id}/jobs/{job_id}:inspect",
    response_model=JobStatus,
)
async def inspect_study_job(
    study_id: StudyID,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
) -> JobStatus:
    job_name = _compose_job_resource_name(study_id, job_id)
    _logger.debug("Inspecting Job '%s'", job_name)

    task = await director2_api.get_computation(project_id=job_id, user_id=user_id)
    job_status: JobStatus = create_jobstatus_from_task(task)
    return job_status


@router.post(
    "/{study_id}/jobs/{job_id}/outputs",
    response_model=JobOutputs,
)
async def get_study_job_outputs(
    study_id: StudyID,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    storage_client: Annotated[StorageApi, Depends(get_api_client(StorageApi))],
):
    job_name = _compose_job_resource_name(study_id, job_id)
    _logger.debug("Getting Job Outputs for '%s'", job_name)

    project_outputs = await webserver_api.get_project_outputs(project_id=job_id)
    job_outputs: JobOutputs = await create_job_outputs_from_project_outputs(
        job_id, project_outputs, user_id, storage_client
    )

    return job_outputs


@router.get(
    "/{study_id}/jobs/{job_id}/outputs/log-links",
    response_model=JobLogsMap,
    status_code=status.HTTP_200_OK,
    summary="Get download links for study job log files",
)
async def get_study_job_output_logfile(
    study_id: StudyID,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
):
    with log_context(
        logger=_logger,
        level=logging.DEBUG,
        msg=f"get study job output logfile study_id={study_id!r} job_id={job_id!r}.",
    ):
        return await director2_api.get_computation_logs(
            user_id=user_id, project_id=job_id
        )


@router.get(
    "/{study_id}/jobs/{job_id}/metadata",
    response_model=JobMetadata,
    description=(
        "Get custom metadata from a study's job\n\n"
        + FMSG_CHANGELOG_NEW_IN_VERSION.format("0.7")
    ),
)
async def get_study_job_custom_metadata(
    study_id: StudyID,
    job_id: JobID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    job_name = _compose_job_resource_name(study_id, job_id)
    msg = f"Gets metadata attached to study_id={study_id!r} job_id={job_id!r}.\njob_name={job_name!r}.\nSEE https://github.com/ITISFoundation/osparc-simcore/issues/4313"
    _logger.debug(msg)

    return await get_custom_metadata(
        job_name=job_name,
        job_id=job_id,
        webserver_api=webserver_api,
        self_url=url_for(
            "get_study_job_custom_metadata",
            study_id=study_id,
            job_id=job_id,
        ),
    )


@router.put(
    "/{study_id}/jobs/{job_id}/metadata",
    response_model=JobMetadata,
    description=(
        "Changes custom metadata of a study's job\n\n"
        + FMSG_CHANGELOG_NEW_IN_VERSION.format("0.7")
    ),
)
async def replace_study_job_custom_metadata(
    study_id: StudyID,
    job_id: JobID,
    replace: JobMetadataUpdate,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    job_name = _compose_job_resource_name(study_id, job_id)

    msg = f"Attaches metadata={replace.metadata!r} to study_id={study_id!r} job_id={job_id!r}.\njob_name={job_name!r}.\nSEE https://github.com/ITISFoundation/osparc-simcore/issues/4313"
    _logger.debug(msg)

    return await replace_custom_metadata(
        job_name=job_name,
        job_id=job_id,
        update=replace,
        webserver_api=webserver_api,
        self_url=url_for(
            "replace_study_job_custom_metadata",
            study_id=study_id,
            job_id=job_id,
        ),
    )


def _update_study_job_urls(
    *,
    job: Job,
    study_id: StudyID,
    job_id: JobID | str,
    url_for: Callable[..., HttpUrl],
) -> Job:
    job.url = url_for(
        get_study_job.__name__,
        study_id=study_id,
        job_id=job_id,
    )

    job.runner_url = url_for(
        "get_study",
        study_id=study_id,
    )

    job.outputs_url = url_for(
        get_study_job_outputs.__name__,
        study_id=study_id,
        job_id=job_id,
    )

    return job
