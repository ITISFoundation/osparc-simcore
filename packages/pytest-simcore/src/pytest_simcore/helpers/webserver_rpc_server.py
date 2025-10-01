# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_pagination import PageOffsetInt
from models_library.rpc.webserver.projects import (
    ListProjectsMarkedAsJobRpcFilters,
    PageRpcProjectJobRpcGet,
    ProjectJobRpcGet,
)
from models_library.rpc_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
)
from models_library.users import UserID
from pydantic import TypeAdapter, validate_call
from pytest_mock import MockType
from servicelib.rabbitmq import RabbitMQRPCClient


class WebserverRpcSideEffects:
    # pylint: disable=no-self-use

    def __init__(self, fake_project_job_rpc_get: ProjectJobRpcGet):
        self.fake_project_job_rpc_get = fake_project_job_rpc_get

    @validate_call(config={"arbitrary_types_allowed": True})
    async def mark_project_as_job(
        self,
        rpc_client: RabbitMQRPCClient | MockType,
        *,
        product_name: ProductName,
        user_id: UserID,
        project_uuid: ProjectID,
        job_parent_resource_name: str,
        storage_assets_deleted: bool,
    ) -> None:
        assert rpc_client

        assert not job_parent_resource_name.startswith("/")  # nosec
        assert "/" in job_parent_resource_name  # nosec
        assert not job_parent_resource_name.endswith("/")  # nosec
        assert isinstance(storage_assets_deleted, bool)

        assert product_name
        assert user_id

        TypeAdapter(ProjectID).validate_python(project_uuid)

    @validate_call(config={"arbitrary_types_allowed": True})
    async def list_projects_marked_as_jobs(
        self,
        rpc_client: RabbitMQRPCClient | MockType,
        *,
        product_name: ProductName,
        user_id: UserID,
        # pagination
        offset: PageOffsetInt = 0,
        limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        filters: ListProjectsMarkedAsJobRpcFilters | None = None,
    ) -> PageRpcProjectJobRpcGet:
        assert rpc_client
        assert product_name
        assert user_id

        if filters and filters.job_parent_resource_name_prefix:
            assert not filters.job_parent_resource_name_prefix.startswith("/")
            assert not filters.job_parent_resource_name_prefix.endswith("%")
            assert not filters.job_parent_resource_name_prefix.startswith("%")

        items = [
            item
            for item in ProjectJobRpcGet.model_json_schema()["examples"]
            if filters is None
            or filters.job_parent_resource_name_prefix is None
            or item.get("job_parent_resource_name").startswith(
                filters.job_parent_resource_name_prefix
            )
        ]

        return PageRpcProjectJobRpcGet.create(
            items[offset : offset + limit],
            total=len(items),
            limit=limit,
            offset=offset,
        )

    @validate_call(config={"arbitrary_types_allowed": True})
    async def get_project_marked_as_job(
        self,
        rpc_client: RabbitMQRPCClient | MockType,
        *,
        product_name: ProductName,
        user_id: UserID,
        project_uuid: ProjectID,
        job_parent_resource_name: str,
    ) -> ProjectJobRpcGet:
        assert rpc_client
        assert product_name
        assert user_id
        assert project_uuid
        assert job_parent_resource_name

        # Return a valid example from the schema
        _data = self.fake_project_job_rpc_get.model_dump()
        _data["uuid"] = str(project_uuid)
        _data["job_parent_resource_name"] = job_parent_resource_name
        return ProjectJobRpcGet.model_validate(_data)
