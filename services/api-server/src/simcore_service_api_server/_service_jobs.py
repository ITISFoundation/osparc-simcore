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
from models_library.rpc.webserver.projects import ProjectJobRpcGet
from models_library.rpc_pagination import PageLimitInt
from models_library.users import UserID
from pydantic import HttpUrl
from servicelib.logging_utils import log_context

from ._service_solvers import (
    SolverService,
)
from .exceptions.custom_errors import SolverServiceListJobsFiltersError
from .models.api_resources import RelativeResourceName
from .models.basic_types import NameValueTuple, VersionStr
from .models.schemas.jobs import Job, JobID, JobInputs, compose_resource_name
from .models.schemas.programs import Program
from .models.schemas.solvers import Solver, SolverKeyId
from .models.schemas.studies import StudyID
from .services_http.director_v2 import DirectorV2Api
from .services_http.solver_job_models_converters import (
    JobStatus,
    create_job_from_project,
    create_job_inputs_from_node_inputs,
    create_jobstatus_from_task,
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
    _director2_api: DirectorV2Api
    _storage_rest_client: StorageApi
    _directorv2_rpc_client: DirectorV2Service
    _solver_service: SolverService
    user_id: UserID
    product_name: ProductName

    async def _list_jobs(
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

    async def list_solver_jobs(
        self,
        *,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
        filter_by_solver_key: SolverKeyId | None = None,
        filter_by_solver_version: VersionStr | None = None,
        filter_any_custom_metadata: list[NameValueTuple] | None = None,
    ) -> tuple[list[Job], PageMetaInfoLimitOffset]:
        """Lists all solver jobs for a user with pagination"""

        # 1. Compose job parent resource name prefix
        collection_or_resource_ids = [
            "solvers",  # solver_id, "releases", solver_version, "jobs",
        ]
        if filter_by_solver_key:
            collection_or_resource_ids.append(filter_by_solver_key)
            if filter_by_solver_version:
                collection_or_resource_ids.append("releases")
                collection_or_resource_ids.append(filter_by_solver_version)
        elif filter_by_solver_version:
            raise SolverServiceListJobsFiltersError

        job_parent_resource_name = compose_resource_name(*collection_or_resource_ids)

        # 2. list jobs under job_parent_resource_name
        return await self._list_jobs(
            job_parent_resource_name=job_parent_resource_name,
            filter_any_custom_metadata=filter_any_custom_metadata,
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
        )

    async def list_study_jobs(
        self,
        *,
        filter_by_study_id: StudyID | None = None,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
    ) -> tuple[list[Job], PageMetaInfoLimitOffset]:
        """Lists all solver jobs for a user with pagination"""

        # 1. Compose job parent resource name prefix
        collection_or_resource_ids: list[str] = [
            "study",  # study_id, "jobs",
        ]
        if filter_by_study_id:
            collection_or_resource_ids.append(f"{filter_by_study_id}")

        job_parent_resource_name = compose_resource_name(*collection_or_resource_ids)

        # 2. list jobs under job_parent_resource_name
        return await self._list_jobs(
            job_parent_resource_name=job_parent_resource_name,
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
        )

    async def create_project_marked_as_job(
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
                storage_assets_deleted=False,
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

    async def get_job(
        self, job_parent_resource_name: RelativeResourceName, job_id: JobID
    ) -> ProjectJobRpcGet:
        """This method can be used to check that the project exists and has the correct parent resource."""
        return await self._web_rpc_client.get_project_marked_as_job(
            product_name=self.product_name,
            user_id=self.user_id,
            project_id=job_id,
            job_parent_resource_name=job_parent_resource_name,
        )

    async def delete_job_assets(
        self, job_parent_resource_name: RelativeResourceName, job_id: JobID
    ):
        """Marks job project as hidden and deletes S3 assets associated it"""
        await self._web_rest_client.patch_project(
            project_id=job_id, patch_params=ProjectPatch(hidden=True)
        )
        await self._storage_rest_client.delete_project_s3_assets(
            user_id=self.user_id, project_id=job_id
        )
        await self._web_rpc_client.mark_project_as_job(
            product_name=self.product_name,
            user_id=self.user_id,
            project_uuid=job_id,
            job_parent_resource_name=job_parent_resource_name,
            storage_assets_deleted=True,
        )

    async def create_solver_job(
        self,
        *,
        solver_key: SolverKeyId,
        version: VersionStr,
        inputs: JobInputs,
        url_for: Callable,
        hidden: bool,
        x_simcore_parent_project_uuid: ProjectID | None,
        x_simcore_parent_node_id: NodeID | None,
    ) -> Job:

        solver = await self._solver_service.get_solver(
            solver_key=solver_key,
            solver_version=version,
        )
        job, _ = await self.create_project_marked_as_job(
            project_name=None,
            description=None,
            solver_or_program=solver,
            inputs=inputs,
            url_for=url_for,
            hidden=hidden,
            parent_project_uuid=x_simcore_parent_project_uuid,
            parent_node_id=x_simcore_parent_node_id,
        )

        return job

    async def inspect_solver_job(
        self,
        *,
        solver_key: SolverKeyId,
        version: VersionStr,
        job_id: JobID,
    ):
        assert solver_key  # nosec
        assert version  # nosec
        task = await self._director2_api.get_computation(
            project_id=job_id, user_id=self.user_id
        )
        job_status: JobStatus = create_jobstatus_from_task(task)
        return job_status
