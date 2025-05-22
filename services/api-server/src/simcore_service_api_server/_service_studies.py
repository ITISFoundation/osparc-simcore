from dataclasses import dataclass
from uuid import UUID

from models_library.api_schemas_webserver.projects import ProjectPatch
from models_library.api_schemas_webserver.projects_nodes import NodeOutputs
from models_library.function_services_catalog.services import file_picker
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes import InputID, InputTypes
from models_library.projects_nodes_io import NodeID
from models_library.rest_pagination import (
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.rpc_pagination import PageLimitInt
from models_library.users import UserID

from ._service_jobs import JobService
from ._service_utils import check_user_product_consistency
from .api.dependencies.webserver_http import AuthSession
from .api.dependencies.webserver_rpc import WbApiRpcClient
from .models.api_resources import compose_resource_name
from .models.schemas.jobs import Job, JobInputs
from .models.schemas.studies import StudyID
from .services_http.study_job_models_converters import (
    create_job_from_study,
    get_project_and_file_inputs_from_job_inputs,
)

DEFAULT_PAGINATION_LIMIT = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1


@dataclass(frozen=True, kw_only=True)
class StudyService:
    job_service: JobService
    user_id: UserID
    product_name: ProductName
    webserver_api: AuthSession
    wb_api_rpc: WbApiRpcClient

    def __post_init__(self):
        check_user_product_consistency(
            service_cls_name=self.__class__.__name__,
            service_provider=self.job_service,
            user_id=self.user_id,
            product_name=self.product_name,
        )

    async def list_jobs(
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
        return await self.job_service.list_jobs(
            job_parent_resource_name=job_parent_resource_name,
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
        )

    async def create_job(
        self,
        study_id: StudyID,
        job_inputs: JobInputs,
        hidden: bool = True,
        parent_project_uuid: ProjectID | None = None,
        parent_node_id: NodeID | None = None,
    ) -> Job:
        """Creates a job from a study"""
        project = await self.webserver_api.clone_project(
            project_id=study_id,
            hidden=hidden,
            parent_project_uuid=parent_project_uuid,
            parent_node_id=parent_node_id,
        )
        job = create_job_from_study(
            study_key=study_id, project=project, job_inputs=job_inputs
        )

        await self.webserver_api.patch_project(
            project_id=job.id,
            patch_params=ProjectPatch(name=job.name),  # type: ignore[arg-type]
        )

        await self.wb_api_rpc.mark_project_as_job(
            product_name=self.product_name,
            user_id=self.user_id,
            project_uuid=job.id,
            job_parent_resource_name=job.runner_name,
        )

        project_inputs = await self.webserver_api.get_project_inputs(
            project_id=project.uuid
        )

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
            await self.webserver_api.update_node_outputs(
                project_id=project.uuid,
                node_id=UUID(file_param_nodes[node_label]),
                new_node_outputs=NodeOutputs(outputs={"outFile": file_link}),
            )

        if len(new_project_inputs) > 0:
            await self.webserver_api.update_project_inputs(
                project_id=project.uuid, new_inputs=new_project_inputs
            )

        return job
