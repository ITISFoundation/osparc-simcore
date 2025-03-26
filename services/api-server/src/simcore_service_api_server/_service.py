import logging
from collections.abc import Callable

from models_library.api_schemas_webserver.projects import ProjectCreateNew, ProjectGet
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import HttpUrl
from simcore_service_api_server.models.schemas.jobs import Job, JobInputs
from simcore_service_api_server.models.schemas.programs import Program
from simcore_service_api_server.models.schemas.solvers import Solver
from simcore_service_api_server.services_http.solver_job_models_converters import (
    create_job_from_project,
    create_new_project_for_job,
)
from simcore_service_api_server.services_http.webserver import AuthSession

_logger = logging.getLogger(__name__)


async def create_solver_or_program_job(
    *,
    webserver_api: AuthSession,
    solver_or_program: Solver | Program,
    inputs: JobInputs,
    parent_project_uuid: ProjectID | None,
    parent_node_id: NodeID | None,
    url_for: Callable[..., HttpUrl],
    hidden: bool
) -> Job:
    # creates NEW job as prototype
    pre_job = Job.create_job_from_solver_or_program(
        solver_or_program=solver_or_program, inputs=inputs
    )
    _logger.debug("Creating Job '%s'", pre_job.name)

    project_in: ProjectCreateNew = create_new_project_for_job(
        solver_or_program, pre_job, inputs
    )
    new_project: ProjectGet = await webserver_api.create_project(
        project_in,
        is_hidden=hidden,
        parent_project_uuid=parent_project_uuid,
        parent_node_id=parent_node_id,
    )
    assert new_project  # nosec
    assert new_project.uuid == pre_job.id  # nosec

    # for consistency, it rebuild job

    # create urls
    url = None
    runner_url = None
    outputs_url = None
    if isinstance(solver_or_program, Solver):
        url = url_for(
            "get_job",
            solver_key=solver_or_program.id,
            version=solver_or_program.version,
            job_id=pre_job.id,
        )
        runner_url = url_for(
            "get_solver_release",
            solver_key=solver_or_program.id,
            version=solver_or_program.version,
        )
        outputs_url = url_for(
            "get_job_outputs",
            solver_key=solver_or_program.id,
            version=solver_or_program.version,
            job_id=pre_job.id,
        )

    job = create_job_from_project(
        solver_key=solver_or_program.id,
        solver_version=solver_or_program.version,
        project=new_project,
        url=url,
        runner_url=runner_url,
        outputs_url=outputs_url,
    )
    assert job.id == pre_job.id  # nosec
    assert job.name == pre_job.name  # nosec
    resource_name = ""
    if isinstance(solver_or_program, Program):
        resource_name = Job.compose_resource_name(
            parent_name=Program.compose_resource_name(
                solver_or_program.id, solver_or_program.version
            ),
            job_id=job.id,
        )
    if isinstance(solver_or_program, Solver):
        resource_name = Job.compose_resource_name(
            parent_name=Solver.compose_resource_name(
                solver_or_program.id, solver_or_program.version
            ),
            job_id=job.id,
        )
    assert job.name == resource_name
    return job
