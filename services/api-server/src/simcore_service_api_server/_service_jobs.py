import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from common_library.exclude import as_dict_exclude_none
from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobGet
from models_library.api_schemas_webserver.projects import (
    ProjectCreateNew,
    ProjectGet,
    ProjectPatch,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rest_pagination import (
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.rpc_pagination import PageLimitInt
from models_library.users import UserID
from pydantic import HttpUrl
from servicelib.logging_utils import log_context

from .models.basic_types import NameValueTuple
from .models.schemas.jobs import Job, JobID, JobInputs
from .models.schemas.programs import Program
from .models.schemas.solvers import Solver
from .services_http.solver_job_models_converters import (
    create_job_from_project,
    create_job_inputs_from_node_inputs,
    create_new_project_for_job,
)
from .services_http.storage import StorageApi
from .services_http.webserver import AuthSession
from .services_rpc.director_v2 import DirectorV2Service
from .services_rpc.storage import StorageService
from .services_rpc.wb_api_server import WbApiRpcClient

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class JobService:
    _web_rest_client: AuthSession
    _web_rpc_client: WbApiRpcClient
    _storage_rpc_client: StorageService
    _storage_rest_client: StorageApi
    _directorv2_rpc_client: DirectorV2Service
    user_id: UserID
    product_name: ProductName

    async def list_jobs(
        self,
        job_parent_resource_name: str,
        *,
        filter_any_custom_metadata: list[NameValueTuple] | None = None,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
    ) -> tuple[list[Job], PageMetaInfoLimitOffset]:
        """Lists all jobs for a user with pagination based on resource name prefix"""

        pagination_kwargs = as_dict_exclude_none(
            pagination_offset=pagination_offset, pagination_limit=pagination_limit
        )

        # 1. List projects marked as jobs
        projects_page = await self._web_rpc_client.list_projects_marked_as_jobs(
            product_name=self.product_name,
            user_id=self.user_id,
            filter_by_job_parent_resource_name_prefix=job_parent_resource_name,
            filter_any_custom_metadata=filter_any_custom_metadata,
            **pagination_kwargs,
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
            new_project: ProjectGet = await self._web_rest_client.create_project(
                project_in,
                is_hidden=hidden,
                parent_project_uuid=parent_project_uuid,
                parent_node_id=parent_node_id,
            )
            await self._web_rpc_client.mark_project_as_job(
                product_name=self.product_name,
                user_id=self.user_id,
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

    async def start_log_export(
        self,
        job_id: JobID,
    ) -> AsyncJobGet:
        file_ids = await self._directorv2_rpc_client.get_computation_task_log_file_ids(
            project_id=job_id
        )
        async_job_get = await self._storage_rpc_client.start_data_export(
            paths_to_export=[
                Path(elm.file_id) for elm in file_ids if elm.file_id is not None
            ],
        )
        return async_job_get

    async def delete_project_assets(self, project_id: ProjectID):
        """Marks job project as hidden and deletes S3 assets associated it"""
        await self._web_rest_client.patch_project(
            project_id=project_id, patch_params=ProjectPatch(hidden=True)
        )
        await self._storage_rest_client.delete_project_s3_assets(
            user_id=self.user_id, project_id=project_id
        )
