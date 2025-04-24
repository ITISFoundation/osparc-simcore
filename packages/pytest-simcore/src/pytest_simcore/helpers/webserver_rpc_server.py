# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_pagination import PageOffsetInt
from models_library.rpc.webserver.projects import PageRpcProjectJobRpcGet
from models_library.rpc_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
)
from models_library.users import UserID
from pydantic import TypeAdapter, validate_call
from pytest_mock import MockType
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient


class WebserverRpcSideEffects:
    # pylint: disable=no-self-use

    @validate_call(config={"arbitrary_types_allowed": True})
    async def mark_project_as_job(
        self,
        rpc_client: RabbitMQRPCClient | MockType,
        *,
        product_name: ProductName,
        user_id: UserID,
        project_uuid: ProjectID,
        job_parent_resource_name: str,
    ) -> None:
        assert rpc_client

        assert not job_parent_resource_name.startswith("/")  # nosec
        assert "/" in job_parent_resource_name  # nosec
        assert not job_parent_resource_name.endswith("/")  # nosec

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
        # filters
        job_parent_resource_name_filter: str | None = None,
    ) -> PageRpcProjectJobRpcGet:
        assert rpc_client
        assert product_name
        assert user_id

        if job_parent_resource_name_filter:
            assert not job_parent_resource_name_filter.startswith("/")

        items = PageRpcProjectJobRpcGet.model_json_schema()["examples"]

        return PageRpcProjectJobRpcGet.create(
            items[offset, : offset + limit],
            total=len(items),
            limit=limit,
            offset=offset,
        )
