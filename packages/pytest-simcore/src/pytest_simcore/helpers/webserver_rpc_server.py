# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import TypeAdapter, validate_call
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient


class WebserverRpcSideEffects:
    # pylint: disable=no-self-use

    @validate_call(config=dict(arbitrary_types_allowed=True))
    async def mark_project_as_job(
        self,
        rpc_client: RabbitMQRPCClient,
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
