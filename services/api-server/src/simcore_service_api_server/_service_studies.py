from models_library.products import ProductName
from models_library.projects_nodes import Node
from models_library.rest_pagination import (
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.rpc_pagination import PageLimitInt
from models_library.users import UserID
from simcore_service_api_server.models.schemas.studies import StudyID

from .models.api_resources import compose_resource_name
from .models.schemas.jobs import Job, JobInputs
from .services_http.solver_job_models_converters import (
    create_job_inputs_from_node_inputs,
)
from .services_rpc.wb_api_server import WbApiRpcClient

DEFAULT_PAGINATION_LIMIT = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1


class StudiesService:
    _webserver_client: WbApiRpcClient

    def __init__(
        self,
        webserver_client: WbApiRpcClient,
    ):
        self._webserver_client = webserver_client

    async def list_jobs(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        # filters
        study_id: StudyID | None = None,
        # pagination
        offset: PageOffsetInt = 0,
        limit: PageLimitInt = DEFAULT_PAGINATION_LIMIT,
    ) -> tuple[list[Job], PageMetaInfoLimitOffset]:
        """Lists all solver jobs for a user with pagination"""

        # 1. Compose job parent resource name prefix
        collection_or_resource_ids: list[str] = [
            "study",  # study_id, "jobs",
        ]
        if study_id:
            collection_or_resource_ids.append(f"{study_id}")

        job_parent_resource_name_prefix = compose_resource_name(
            *collection_or_resource_ids
        )

        # 2. List projects marked as jobs
        projects_page = await self._webserver_client.list_projects_marked_as_jobs(
            product_name=product_name,
            user_id=user_id,
            offset=offset,
            limit=limit,
            job_parent_resource_name_prefix=job_parent_resource_name_prefix,
        )

        # 3. Convert projects to jobs
        jobs: list[Job] = []
        for project_job in projects_page.data:

            assert (  # nosec
                len(project_job.workbench) == 1
            ), "Expected only one solver node in workbench"

            solver_node: Node = next(iter(project_job.workbench.values()))
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
