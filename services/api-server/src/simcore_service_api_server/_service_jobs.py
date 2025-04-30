import logging
from collections.abc import Callable

from models_library.api_schemas_webserver.projects import ProjectCreateNew, ProjectGet
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rest_pagination import (
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.rpc_pagination import PageLimitInt
from models_library.users import UserID
from pydantic import HttpUrl
from servicelib.logging_utils import log_context

from .exceptions.custom_errors import ServiceConfigurationError
from .models.schemas.jobs import Job, JobInputs
from .models.schemas.programs import Program
from .models.schemas.solvers import Solver
from .services_http.solver_job_models_converters import (
    create_job_from_project,
    create_job_inputs_from_node_inputs,
    create_new_project_for_job,
)
from .services_http.webserver import AuthSession
from .services_rpc.wb_api_server import WbApiRpcClient

_logger = logging.getLogger(__name__)


class JobService:
    # clients
    _web_rest_api: AuthSession
    _web_rpc_api: WbApiRpcClient
    # context
    _user_id: UserID
    _product_name: ProductName

    def __init__(
        self,
        *,
        web_rest_api: AuthSession,
        web_rpc_api: WbApiRpcClient,
        user_id: UserID,
        product_name: ProductName,
    ):
        self._web_rest_api = web_rest_api
        self._web_rpc_api = web_rpc_api
        self._user_id = user_id
        self._product_name = product_name

    async def list_jobs_by_resource_prefix(
        self,
        *,
        job_parent_resource_name_prefix: str,
        offset: PageOffsetInt = 0,
        limit: PageLimitInt = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1,
    ) -> tuple[list[Job], PageMetaInfoLimitOffset]:
        """Lists all jobs for a user with pagination based on resource name prefix"""

        # 1. List projects marked as jobs
        projects_page = await self._web_rpc_api.list_projects_marked_as_jobs(
            product_name=self._product_name,
            user_id=self._user_id,
            offset=offset,
            limit=limit,
            job_parent_resource_name_prefix=job_parent_resource_name_prefix,
        )

        # 2. Convert projects to jobs
        jobs: list[Job] = []
        for project_job in projects_page.data:
            assert (  # nosec
                len(project_job.workbench) == 1
            ), "Expected only one solver node in workbench"

            solver_node = next(iter(project_job.workbench.values()))
            job_inputs: JobInputs = create_job_inputs_from_node_inputs(
                inputs=solver_node.inputs or {}
            )
            assert project_job.job_parent_resource_name  # nosec

            jobs.append(
                Job(
                    id=project_job.uuid,
                    name=Job.compose_resource_name(
                        project_job.job_parent_resource_name, project_job.uuid
                    ),
                    inputs_checksum=job_inputs.compute_checksum(),
                    created_at=project_job.created_at,
                    runner_name=project_job.job_parent_resource_name,
                    url=None,
                    runner_url=None,
                    outputs_url=None,
                )
            )

        return jobs, projects_page.meta

    async def create_job(
        self,
        *,
        solver_or_program: Solver | Program,
        inputs: JobInputs,
        parent_project_uuid: ProjectID | None,
        parent_node_id: NodeID | None,
        url_for: Callable[..., HttpUrl],
        hidden: bool,
        project_name: str | None,
        description: str | None,
    ) -> tuple[Job, ProjectGet]:
        """If no project_name is provided, the job name is used as project name"""

        # creates NEW job as prototype

        pre_job = Job.create_job_from_solver_or_program(
            solver_or_program_name=solver_or_program.name, inputs=inputs
        )
        with log_context(
            logger=_logger, level=logging.DEBUG, msg=f"Creating job {pre_job.name}"
        ):
            project_in: ProjectCreateNew = create_new_project_for_job(
                solver_or_program=solver_or_program,
                job=pre_job,
                inputs=inputs,
                description=description,
                project_name=project_name,
            )
            new_project: ProjectGet = await self._web_rest_api.create_project(
                project_in,
                is_hidden=hidden,
                parent_project_uuid=parent_project_uuid,
                parent_node_id=parent_node_id,
            )
            await self._web_rpc_api.mark_project_as_job(
                product_name=self._product_name,
                user_id=self._user_id,
                project_uuid=new_project.uuid,
                job_parent_resource_name=pre_job.runner_name,
            )

        assert new_project  # nosec
        assert new_project.uuid == pre_job.id  # nosec

        # for consistency, it rebuild job
        job = create_job_from_project(
            solver_or_program=solver_or_program, project=new_project, url_for=url_for
        )
        assert job.id == pre_job.id  # nosec
        assert job.name == pre_job.name  # nosec
        assert job.name == Job.compose_resource_name(
            parent_name=solver_or_program.resource_name,
            job_id=job.id,
        )
        return job, new_project

    @property
    def user_id(self) -> UserID:
        return self._user_id

    @property
    def product_name(self) -> ProductName:
        return self._product_name


def check_user_product_consistency(
    service_cls_name: str,
    job_service: JobService,
    user_id: UserID,
    product_name: ProductName,
) -> None:
    if user_id != job_service.user_id:
        msg = f"User ID {user_id} does not match job service user ID {job_service.user_id}"
        raise ServiceConfigurationError(
            service_cls_name=service_cls_name, detail_msg=msg
        )
    if product_name != job_service.product_name:
        msg = f"Product name {product_name} does not match job service product name {job_service.product_name}"
        raise ServiceConfigurationError(
            service_cls_name=service_cls_name, detail_msg=msg
        )
