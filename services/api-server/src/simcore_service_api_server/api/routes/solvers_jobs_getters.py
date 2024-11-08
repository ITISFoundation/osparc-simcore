# pylint: disable=too-many-arguments

import logging
from collections import deque
from collections.abc import Callable
from typing import Annotated, Any, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from fastapi_pagination.api import create_page
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.api_schemas_webserver.resource_usage import PricingUnitGet
from models_library.api_schemas_webserver.wallets import WalletGetWithAvailableCredits
from models_library.projects_nodes_io import BaseFileLink
from models_library.users import UserID
from models_library.wallets import ZERO_CREDITS
from pydantic import NonNegativeInt
from pydantic.types import PositiveInt
from servicelib.fastapi.requests_decorators import cancel_on_disconnect
from servicelib.logging_utils import log_context

from ...exceptions.custom_errors import InsufficientCreditsError, MissingWalletError
from ...exceptions.service_errors_utils import DEFAULT_BACKEND_SERVICE_STATUS_CODES
from ...models.basic_types import LogStreamingResponse, VersionStr
from ...models.pagination import Page, PaginationParams
from ...models.schemas.errors import ErrorGet
from ...models.schemas.files import File
from ...models.schemas.jobs import (
    ArgumentTypes,
    Job,
    JobID,
    JobLog,
    JobMetadata,
    JobOutputs,
)
from ...models.schemas.solvers import SolverKeyId
from ...services.catalog import CatalogApi
from ...services.director_v2 import DirectorV2Api
from ...services.jobs import (
    get_custom_metadata,
    raise_if_job_not_associated_with_solver,
)
from ...services.log_streaming import LogDistributor, LogStreamer
from ...services.solver_job_models_converters import create_job_from_project
from ...services.solver_job_outputs import ResultsTypes, get_solver_output_results
from ...services.storage import StorageApi, to_file_api_model
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.database import Engine, get_db_engine
from ..dependencies.rabbitmq import get_log_check_timeout, get_log_distributor
from ..dependencies.services import get_api_client
from ..dependencies.webserver import AuthSession, get_webserver_session
from ._constants import FMSG_CHANGELOG_NEW_IN_VERSION
from .solvers_jobs import (
    JOBS_STATUS_CODES,
    METADATA_STATUS_CODES,
    _compose_job_resource_name,
)
from .wallets import WALLET_STATUS_CODES

_logger = logging.getLogger(__name__)

_OUTPUTS_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_402_PAYMENT_REQUIRED: {
        "description": "Payment required",
        "model": ErrorGet,
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "Job not found",
        "model": ErrorGet,
    },
    **DEFAULT_BACKEND_SERVICE_STATUS_CODES,
}

_LOGFILE_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_200_OK: {
        "content": {
            "application/octet-stream": {
                "schema": {"type": "string", "format": "binary"}
            },
            "application/zip": {"schema": {"type": "string", "format": "binary"}},
            "text/plain": {"schema": {"type": "string"}},
        },
        "description": "Returns a log file",
    },
    status.HTTP_404_NOT_FOUND: {"description": "Log not found"},
} | DEFAULT_BACKEND_SERVICE_STATUS_CODES  # type: ignore

_PRICING_UNITS_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Pricing unit not found",
        "model": ErrorGet,
    },
    **DEFAULT_BACKEND_SERVICE_STATUS_CODES,
}

_LOGSTREAM_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_200_OK: {
        "description": "Returns a JobLog or an ErrorGet",
        "model": Union[JobLog, ErrorGet],
    },
    status.HTTP_409_CONFLICT: {
        "description": "Conflict: Logs are already being streamed",
        "model": ErrorGet,
    },
    **DEFAULT_BACKEND_SERVICE_STATUS_CODES,
}

router = APIRouter()


@router.get(
    "/{solver_key:path}/releases/{version}/jobs",
    response_model=list[Job],
    responses=JOBS_STATUS_CODES,
)
async def list_jobs(
    solver_key: SolverKeyId,
    version: VersionStr,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    catalog_client: Annotated[CatalogApi, Depends(get_api_client(CatalogApi))],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    product_name: Annotated[str, Depends(get_product_name)],
):
    """List of jobs in a specific released solver (limited to 20 jobs)

    - DEPRECATION: This implementation and returned values are deprecated and the will be replaced by that of get_jobs_page
    - SEE `get_jobs_page` for paginated version of this function
    """

    solver = await catalog_client.get_service(
        user_id=user_id,
        name=solver_key,
        version=version,
        product_name=product_name,
    )
    _logger.debug("Listing Jobs in Solver '%s'", solver.name)

    projects_page = await webserver_api.get_projects_w_solver_page(
        solver_name=solver.name, limit=20, offset=0
    )

    jobs: deque[Job] = deque()
    for prj in projects_page.data:
        job = create_job_from_project(solver_key, version, prj, url_for)
        assert job.id == prj.uuid  # nosec
        assert job.name == prj.name  # nosec

        jobs.append(job)

    return list(jobs)


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/page",
    response_model=Page[Job],
    responses=JOBS_STATUS_CODES,
    description=(
        "List of jobs on a specific released solver (includes pagination)\n\n"
        + FMSG_CHANGELOG_NEW_IN_VERSION.format("0.7")
    ),
)
async def get_jobs_page(
    solver_key: SolverKeyId,
    version: VersionStr,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    page_params: Annotated[PaginationParams, Depends()],
    catalog_client: Annotated[CatalogApi, Depends(get_api_client(CatalogApi))],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    product_name: Annotated[str, Depends(get_product_name)],
):
    # NOTE: Different entry to keep backwards compatibility with list_jobs.
    # Eventually use a header with agent version to switch to new interface

    solver = await catalog_client.get_service(
        user_id=user_id,
        name=solver_key,
        version=version,
        product_name=product_name,
    )
    _logger.debug("Listing Jobs in Solver '%s'", solver.name)

    projects_page = await webserver_api.get_projects_w_solver_page(
        solver_name=solver.name, limit=page_params.limit, offset=page_params.offset
    )

    jobs: list[Job] = [
        create_job_from_project(solver_key, version, prj, url_for)
        for prj in projects_page.data
    ]

    return create_page(
        jobs,
        total=projects_page.meta.total,
        params=page_params,
    )


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}",
    response_model=Job,
    responses=JOBS_STATUS_CODES,
)
async def get_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    """Gets job of a given solver"""
    _logger.debug(
        "Getting Job '%s'", _compose_job_resource_name(solver_key, version, job_id)
    )

    project: ProjectGet = await webserver_api.get_project(project_id=job_id)

    job = create_job_from_project(solver_key, version, project, url_for)
    assert job.id == job_id  # nosec
    return job  # nosec


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}/outputs",
    response_model=JobOutputs,
    responses=_OUTPUTS_STATUS_CODES,
)
async def get_job_outputs(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    db_engine: Annotated[Engine, Depends(get_db_engine)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    storage_client: Annotated[StorageApi, Depends(get_api_client(StorageApi))],
):
    job_name = _compose_job_resource_name(solver_key, version, job_id)
    _logger.debug("Get Job '%s' outputs", job_name)

    project: ProjectGet = await webserver_api.get_project(project_id=job_id)
    node_ids = list(project.workbench.keys())
    assert len(node_ids) == 1  # nosec

    product_price = await webserver_api.get_product_price()
    if product_price.usd_per_credit is not None:
        wallet = await webserver_api.get_project_wallet(project_id=project.uuid)
        if wallet is None:
            raise MissingWalletError(job_id=project.uuid)
        wallet_with_credits = await webserver_api.get_wallet(wallet_id=wallet.wallet_id)
        if wallet_with_credits.available_credits <= ZERO_CREDITS:
            raise InsufficientCreditsError(
                wallet_name=wallet_with_credits.name,
                wallet_credit_amount=wallet_with_credits.available_credits,
            )

    outputs: dict[str, ResultsTypes] = await get_solver_output_results(
        user_id=user_id,
        project_uuid=job_id,
        node_uuid=UUID(node_ids[0]),
        db_engine=db_engine,
    )

    results: dict[str, ArgumentTypes] = {}
    for name, value in outputs.items():
        if isinstance(value, BaseFileLink):
            file_id: UUID = File.create_id(*value.path.split("/"))

            found = await storage_client.search_owned_files(
                user_id=user_id, file_id=file_id, limit=1
            )
            if found:
                assert len(found) == 1  # nosec
                results[name] = to_file_api_model(found[0])
            else:
                api_file: File = await storage_client.create_soft_link(
                    user_id=user_id, target_s3_path=value.path, as_file_id=file_id
                )
                results[name] = api_file
        else:
            results[name] = value

    return JobOutputs(job_id=job_id, results=results)


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}/outputs/logfile",
    response_class=RedirectResponse,
    responses=_LOGFILE_STATUS_CODES,
    description=(
        "Special extra output with persistent logs file for the solver run.\n\n"
        "**NOTE**: this is not a log stream but a predefined output that is only\n"
        "available after the job is done.\n\n"
        + FMSG_CHANGELOG_NEW_IN_VERSION.format("0.4.0")
    ),
)
async def get_job_output_logfile(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
):
    job_name = _compose_job_resource_name(solver_key, version, job_id)
    _logger.debug("Get Job '%s' outputs logfile", job_name)

    project_id = job_id

    log_link_map = await director2_api.get_computation_logs(
        user_id=user_id, project_id=project_id
    )
    logs_urls = log_link_map.log_links

    _logger.debug(
        "Found %d logfiles for %s %s: %s",
        len(logs_urls),
        f"{project_id=}",
        f"{user_id=}",
        [e.download_link for e in logs_urls],
    )

    # if more than one node? should rezip all of them??
    assert (  # nosec
        len(logs_urls) <= 1
    ), "Current version only supports one node per solver"

    for log_link in logs_urls:
        presigned_download_link = log_link.download_link
        _logger.info(
            "Redirecting '%s' to %s ...",
            f"{solver_key}/releases/{version}/jobs/{job_id}/outputs/logfile",
            presigned_download_link,
        )
        return RedirectResponse(f"{presigned_download_link}")

    # No log found !
    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail=f"Log for {solver_key}/releases/{version}/jobs/{job_id} not found."
        "Note that these logs are only available after the job is completed.",
    )


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}/metadata",
    response_model=JobMetadata,
    responses=METADATA_STATUS_CODES,
    description="Gets custom metadata from a job\n\n"
    + FMSG_CHANGELOG_NEW_IN_VERSION.format("0.7"),
)
async def get_job_custom_metadata(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    job_name = _compose_job_resource_name(solver_key, version, job_id)
    _logger.debug("Custom metadata for '%s'", job_name)

    return await get_custom_metadata(
        job_name=job_name,
        job_id=job_id,
        webserver_api=webserver_api,
        self_url=url_for(
            "get_job_custom_metadata",
            solver_key=solver_key,
            version=version,
            job_id=job_id,
        ),
    )


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}/wallet",
    response_model=WalletGetWithAvailableCredits,
    responses=WALLET_STATUS_CODES,
    description=("Get job wallet\n\n" + FMSG_CHANGELOG_NEW_IN_VERSION.format("0.7")),
)
async def get_job_wallet(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
) -> WalletGetWithAvailableCredits:
    job_name = _compose_job_resource_name(solver_key, version, job_id)
    _logger.debug("Getting wallet for job '%s'", job_name)

    if project_wallet := await webserver_api.get_project_wallet(project_id=job_id):
        return await webserver_api.get_wallet(wallet_id=project_wallet.wallet_id)
    raise MissingWalletError(job_id=job_id)


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}/pricing_unit",
    response_model=PricingUnitGet,
    responses=_PRICING_UNITS_STATUS_CODES,
    description=(
        "Get job pricing unit\n\n" + FMSG_CHANGELOG_NEW_IN_VERSION.format("0.7")
    ),
)
async def get_job_pricing_unit(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    job_name = _compose_job_resource_name(solver_key, version, job_id)
    with log_context(_logger, logging.DEBUG, "Get pricing unit"):
        _logger.debug("job: %s", job_name)
        project: ProjectGet = await webserver_api.get_project(project_id=job_id)
        raise_if_job_not_associated_with_solver(job_name, project)
        node_ids = list(project.workbench.keys())
        assert len(node_ids) == 1  # nosec
        node_id: UUID = UUID(node_ids[0])
        return await webserver_api.get_project_node_pricing_unit(
            project_id=job_id, node_id=node_id
        )


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}/logstream",
    response_class=LogStreamingResponse,
    responses=_LOGSTREAM_STATUS_CODES,
)
@cancel_on_disconnect
async def get_log_stream(
    request: Request,
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    log_distributor: Annotated[LogDistributor, Depends(get_log_distributor)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    log_check_timeout: Annotated[NonNegativeInt, Depends(get_log_check_timeout)],
):
    assert request  # nosec

    job_name = _compose_job_resource_name(solver_key, version, job_id)
    with log_context(
        _logger, logging.DEBUG, f"Streaming logs for {job_name=} and {user_id=}"
    ):
        project: ProjectGet = await webserver_api.get_project(project_id=job_id)
        raise_if_job_not_associated_with_solver(job_name, project)
        log_streamer = LogStreamer(
            user_id=user_id,
            director2_api=director2_api,
            job_id=job_id,
            log_distributor=log_distributor,
            log_check_timeout=log_check_timeout,
        )
        return LogStreamingResponse(
            log_streamer.log_generator(),
        )
