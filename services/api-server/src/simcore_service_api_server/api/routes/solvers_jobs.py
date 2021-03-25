import logging
from typing import Callable, List
from uuid import UUID

from fastapi import APIRouter, Depends

from ...models.schemas.jobs import (
    Job,
    JobInputs,
    JobOutputs,
    JobStatus,
    KeywordArguments,
)
from ...models.schemas.solvers import SolverKeyId, VersionStr
from ...modules.catalog import CatalogApi
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.authentication import get_current_user_id
from ..dependencies.services import get_api_client

logger = logging.getLogger(__name__)

router = APIRouter()


## JOBS ---------------
#
# - Similar to docker container's API design (container = job and image = solver)
# - TODO: solvers_router.post("/{solver_id}/jobs:run", response_model=JobStatus) disabled since MAG is not convinced it is necessary for now
#
# @router.get("/releases/jobs", response_model=List[Job])


@router.get(
    "/{solver_key:path}/releases/{version}/jobs",
    response_model=List[Job],
)
async def list_jobs(
    solver_key: SolverKeyId,
    version: str,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ List of all jobs in a specific released solver """
    from .jobs_faker import list_jobs_impl

    solver = await catalog_client.get_solver(user_id, solver_key, version)
    return await list_jobs_impl(solver.id, solver.version, url_for)


@router.post(
    "/{solver_key:path}/releases/{version}/jobs",
    response_model=Job,
)
async def create_job(
    solver_key: SolverKeyId,
    version: str,
    inputs: JobInputs,
    user_id: int = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Creates a job in a specific release with given inputs.

    NOTE: This operation does **not** start the job
    """
    from .jobs_faker import create_job_impl

    solver = await catalog_client.get_solver(user_id, solver_key, version)
    return await create_job_impl(solver.id, solver.version, inputs, url_for)


@router.get("/{solver_key:path}/releases/{version}/jobs/{job_id}", response_model=Job)
async def get_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ Gets job of a given solver """
    from .jobs_faker import get_job_impl

    return await get_job_impl(solver_key, version, job_id, url_for)


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}:start",
    response_model=JobStatus,
)
async def start_job(solver_key: SolverKeyId, version: VersionStr, job_id: UUID):
    from .jobs_faker import start_job_impl

    return await start_job_impl(solver_key, version, job_id)


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}:stop", response_model=Job
)
async def stop_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    from .jobs_faker import stop_job_impl

    return await stop_job_impl(solver_key, version, job_id, url_for)


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}:inspect",
    response_model=JobStatus,
)
async def inspect_job(solver_key: SolverKeyId, version: VersionStr, job_id: UUID):
    from .jobs_faker import inspect_job_impl

    return await inspect_job_impl(solver_key, version, job_id)


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}/outputs",
    response_model=JobOutputs,
)
async def get_job_outputs(solver_key: SolverKeyId, version: VersionStr, job_id: UUID):

    import aiopg
    from models_library.projects import ProjectID
    from models_library.projects_nodes_io import NodeID

    from .jobs_faker import get_job_outputs_impl

    # pylint: disable=unused-variable
    async def real_impl(
        user_id: int,
        project_id: ProjectID,
        node_uuid: NodeID,
        db_engine: aiopg.sa.Engine,
    ):

        from ...utils.solver_job_outputs import get_solver_output_results

        results: KeywordArguments = await get_solver_output_results(
            user_id=user_id,
            project_uuid=project_id,
            node_uuid=node_uuid,
            db_engine=db_engine,
        )
        return results

    return await get_job_outputs_impl(solver_key, version, job_id)
